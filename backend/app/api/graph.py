"""
å›¾è°±ç›¸å…³APIè·¯ç”±
é‡‡ç”¨é¡¹ç›®ä¸Šä¸‹æ–‡æœºåˆ¶ï¼ŒæœåŠ¡ç«¯æŒä¹…åŒ–çŠ¶æ€
"""

import os
import traceback
import threading
from flask import request, jsonify

from . import graph_bp
from ..config import Config
from ..services.ontology_generator import OntologyGenerator
from ..services.graph_builder import GraphBuilderService
from ..services.text_processor import TextProcessor
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..utils.locale import t, get_locale, set_locale
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager, ProjectStatus

# èŽ·å–æ—¥å¿—å™¨
logger = get_logger('posiedon.api')


def allowed_file(filename: str) -> bool:
    """æ£€æŸ¥æ–‡ä»¶æ‰©å±•åæ˜¯å¦å…è®¸"""
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


# ============== é¡¹ç›®ç®¡ç†æŽ¥å£ ==============

@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """
    èŽ·å–é¡¹ç›®è¯¦æƒ…
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": t('api.projectNotFound', id=project_id)
        }), 404

    return jsonify({
        "success": True,
        "data": project.to_dict()
    })


@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    """
    åˆ—å‡ºæ‰€æœ‰é¡¹ç›®
    """
    limit = request.args.get('limit', 50, type=int)
    projects = ProjectManager.list_projects(limit=limit)
    
    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in projects],
        "count": len(projects)
    })


@graph_bp.route('/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """
    åˆ é™¤é¡¹ç›®
    """
    success = ProjectManager.delete_project(project_id)
    
    if not success:
        return jsonify({
            "success": False,
            "error": t('api.projectDeleteFailed', id=project_id)
        }), 404

    return jsonify({
        "success": True,
        "message": t('api.projectDeleted', id=project_id)
    })


@graph_bp.route('/project/<project_id>/reset', methods=['POST'])
def reset_project(project_id: str):
    """
    é‡ç½®é¡¹ç›®çŠ¶æ€ï¼ˆç”¨äºŽé‡æ–°æž„å»ºå›¾è°±ï¼‰
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": t('api.projectNotFound', id=project_id)
        }), 404

    # é‡ç½®åˆ°æœ¬ä½“å·²ç”ŸæˆçŠ¶æ€
    if project.ontology:
        project.status = ProjectStatus.ONTOLOGY_GENERATED
    else:
        project.status = ProjectStatus.CREATED
    
    project.graph_id = None
    project.graph_build_task_id = None
    project.error = None
    ProjectManager.save_project(project)
    
    return jsonify({
        "success": True,
        "message": t('api.projectReset', id=project_id),
        "data": project.to_dict()
    })


# ============== æŽ¥å£1ï¼šä¸Šä¼ æ–‡ä»¶å¹¶ç”Ÿæˆæœ¬ä½“ ==============

@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """
    æŽ¥å£1ï¼šä¸Šä¼ æ–‡ä»¶ï¼Œåˆ†æžç”Ÿæˆæœ¬ä½“å®šä¹‰
    
    è¯·æ±‚æ–¹å¼ï¼šmultipart/form-data
    
    å‚æ•°ï¼š
        files: ä¸Šä¼ çš„æ–‡ä»¶ï¼ˆPDF/MD/TXTï¼‰ï¼Œå¯å¤šä¸ª
        simulation_requirement: æ¨¡æ‹Ÿéœ€æ±‚æè¿°ï¼ˆå¿…å¡«ï¼‰
        project_name: é¡¹ç›®åç§°ï¼ˆå¯é€‰ï¼‰
        additional_context: é¢å¤–è¯´æ˜Žï¼ˆå¯é€‰ï¼‰
        
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "ontology": {
                    "entity_types": [...],
                    "edge_types": [...],
                    "analysis_summary": "..."
                },
                "files": [...],
                "total_text_length": 12345
            }
        }
    """
    try:
        logger.info("=== å¼€å§‹ç”Ÿæˆæœ¬ä½“å®šä¹‰ ===")
        
        # èŽ·å–å‚æ•°
        simulation_requirement = request.form.get('simulation_requirement', '')
        project_name = request.form.get('project_name', 'Unnamed Project')
        additional_context = request.form.get('additional_context', '')
        
        logger.debug(f"é¡¹ç›®åç§°: {project_name}")
        logger.debug(f"æ¨¡æ‹Ÿéœ€æ±‚: {simulation_requirement[:100]}...")
        
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationRequirement')
            }), 400
        
        # èŽ·å–ä¸Šä¼ çš„æ–‡ä»¶
        uploaded_files = request.files.getlist('files')
        if not uploaded_files or all(not f.filename for f in uploaded_files):
            return jsonify({
                "success": False,
                "error": t('api.requireFileUpload')
            }), 400
        
        # åˆ›å»ºé¡¹ç›®
        project = ProjectManager.create_project(name=project_name)
        project.simulation_requirement = simulation_requirement
        logger.info(f"åˆ›å»ºé¡¹ç›®: {project.project_id}")
        
        # ä¿å­˜æ–‡ä»¶å¹¶æå–æ–‡æœ¬
        document_texts = []
        all_text = ""
        
        for file in uploaded_files:
            if file and file.filename and allowed_file(file.filename):
                # ä¿å­˜æ–‡ä»¶åˆ°é¡¹ç›®ç›®å½•
                file_info = ProjectManager.save_file_to_project(
                    project.project_id, 
                    file, 
                    file.filename
                )
                project.files.append({
                    "filename": file_info["original_filename"],
                    "size": file_info["size"]
                })
                
                # æå–æ–‡æœ¬
                text = FileParser.extract_text(file_info["path"])
                text = TextProcessor.preprocess_text(text)
                document_texts.append(text)
                all_text += f"\n\n=== {file_info['original_filename']} ===\n{text}"
        
        if not document_texts:
            ProjectManager.delete_project(project.project_id)
            return jsonify({
                "success": False,
                "error": t('api.noDocProcessed')
            }), 400
        
        # ä¿å­˜æå–çš„æ–‡æœ¬
        project.total_text_length = len(all_text)
        ProjectManager.save_extracted_text(project.project_id, all_text)
        logger.info(f"æ–‡æœ¬æå–å®Œæˆï¼Œå…± {len(all_text)} å­—ç¬¦")
        
        # ç”Ÿæˆæœ¬ä½“
        logger.info("è°ƒç”¨ LLM ç”Ÿæˆæœ¬ä½“å®šä¹‰...")
        generator = OntologyGenerator()
        ontology = generator.generate(
            document_texts=document_texts,
            simulation_requirement=simulation_requirement,
            additional_context=additional_context if additional_context else None
        )
        
        # ä¿å­˜æœ¬ä½“åˆ°é¡¹ç›®
        entity_count = len(ontology.get("entity_types", []))
        edge_count = len(ontology.get("edge_types", []))
        logger.info(f"æœ¬ä½“ç”Ÿæˆå®Œæˆ: {entity_count} ä¸ªå®žä½“ç±»åž‹, {edge_count} ä¸ªå…³ç³»ç±»åž‹")
        
        project.ontology = {
            "entity_types": ontology.get("entity_types", []),
            "edge_types": ontology.get("edge_types", [])
        }
        project.analysis_summary = ontology.get("analysis_summary", "")
        project.status = ProjectStatus.ONTOLOGY_GENERATED
        ProjectManager.save_project(project)
        logger.info(f"=== æœ¬ä½“ç”Ÿæˆå®Œæˆ === é¡¹ç›®ID: {project.project_id}")
        
        return jsonify({
            "success": True,
            "data": {
                "project_id": project.project_id,
                "project_name": project.name,
                "ontology": project.ontology,
                "analysis_summary": project.analysis_summary,
                "files": project.files,
                "total_text_length": project.total_text_length
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== æŽ¥å£2ï¼šæž„å»ºå›¾è°± ==============

@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """
    æŽ¥å£2ï¼šæ ¹æ®project_idæž„å»ºå›¾è°±
    
    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "project_id": "proj_xxxx",  // å¿…å¡«ï¼Œæ¥è‡ªæŽ¥å£1
            "graph_name": "å›¾è°±åç§°",    // å¯é€‰
            "chunk_size": 500,          // å¯é€‰ï¼Œé»˜è®¤500
            "chunk_overlap": 50         // å¯é€‰ï¼Œé»˜è®¤50
        }
        
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "task_id": "task_xxxx",
                "message": "å›¾è°±æž„å»ºä»»åŠ¡å·²å¯åŠ¨"
            }
        }
    """
    try:
        logger.info("=== å¼€å§‹æž„å»ºå›¾è°± ===")
        
        # æ£€æŸ¥é…ç½®
        errors = []
        if not Config.ZEP_API_KEY:
            errors.append(t('api.zepApiKeyMissing'))
        if errors:
            logger.error(f"é…ç½®é”™è¯¯: {errors}")
            return jsonify({
                "success": False,
                "error": t('api.configError', details="; ".join(errors))
            }), 500
        
        # è§£æžè¯·æ±‚
        data = request.get_json() or {}
        project_id = data.get('project_id')
        logger.debug(f"è¯·æ±‚å‚æ•°: project_id={project_id}")
        
        if not project_id:
            return jsonify({
                "success": False,
                "error": t('api.requireProjectId')
            }), 400
        
        # èŽ·å–é¡¹ç›®
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=project_id)
            }), 404

        # æ£€æŸ¥é¡¹ç›®çŠ¶æ€
        force = data.get('force', False)  # å¼ºåˆ¶é‡æ–°æž„å»º
        
        if project.status == ProjectStatus.CREATED:
            return jsonify({
                "success": False,
                "error": t('api.ontologyNotGenerated')
            }), 400
        
        if project.status == ProjectStatus.GRAPH_BUILDING and not force:
            return jsonify({
                "success": False,
                "error": t('api.graphBuilding'),
                "task_id": project.graph_build_task_id
            }), 400
        
        # å¦‚æžœå¼ºåˆ¶é‡å»ºï¼Œé‡ç½®çŠ¶æ€
        if force and project.status in [ProjectStatus.GRAPH_BUILDING, ProjectStatus.FAILED, ProjectStatus.GRAPH_COMPLETED]:
            project.status = ProjectStatus.ONTOLOGY_GENERATED
            project.graph_id = None
            project.graph_build_task_id = None
            project.error = None
        
        # èŽ·å–é…ç½®
        graph_name = data.get('graph_name', project.name or 'Posiedon Graph')
        chunk_size = data.get('chunk_size', project.chunk_size or Config.DEFAULT_CHUNK_SIZE)
        chunk_overlap = data.get('chunk_overlap', project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP)
        
        # æ›´æ–°é¡¹ç›®é…ç½®
        project.chunk_size = chunk_size
        project.chunk_overlap = chunk_overlap
        
        # èŽ·å–æå–çš„æ–‡æœ¬
        text = ProjectManager.get_extracted_text(project_id)
        if not text:
            return jsonify({
                "success": False,
                "error": t('api.textNotFound')
            }), 400
        
        # èŽ·å–æœ¬ä½“
        ontology = project.ontology
        if not ontology:
            return jsonify({
                "success": False,
                "error": t('api.ontologyNotFound')
            }), 400
        
        # åˆ›å»ºå¼‚æ­¥ä»»åŠ¡
        task_manager = TaskManager()
        task_id = task_manager.create_task(f"æž„å»ºå›¾è°±: {graph_name}")
        logger.info(f"åˆ›å»ºå›¾è°±æž„å»ºä»»åŠ¡: task_id={task_id}, project_id={project_id}")
        
        # æ›´æ–°é¡¹ç›®çŠ¶æ€
        project.status = ProjectStatus.GRAPH_BUILDING
        project.graph_build_task_id = task_id
        ProjectManager.save_project(project)
        
        # Capture locale before spawning background thread
        current_locale = get_locale()

        # å¯åŠ¨åŽå°ä»»åŠ¡
        def build_task():
            set_locale(current_locale)
            build_logger = get_logger('posiedon.build')
            try:
                build_logger.info(f"[{task_id}] å¼€å§‹æž„å»ºå›¾è°±...")
                task_manager.update_task(
                    task_id, 
                    status=TaskStatus.PROCESSING,
                    message=t('progress.initGraphService')
                )
                
                # åˆ›å»ºå›¾è°±æž„å»ºæœåŠ¡
                builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
                
                # åˆ†å—
                task_manager.update_task(
                    task_id,
                    message=t('progress.textChunking'),
                    progress=5
                )
                chunks = TextProcessor.split_text(
                    text, 
                    chunk_size=chunk_size, 
                    overlap=chunk_overlap
                )
                total_chunks = len(chunks)
                
                # åˆ›å»ºå›¾è°±
                task_manager.update_task(
                    task_id,
                    message=t('progress.creatingZepGraph'),
                    progress=10
                )
                graph_id = builder.create_graph(name=graph_name)
                
                # æ›´æ–°é¡¹ç›®çš„graph_id
                project.graph_id = graph_id
                ProjectManager.save_project(project)
                
                # è®¾ç½®æœ¬ä½“
                task_manager.update_task(
                    task_id,
                    message=t('progress.settingOntology'),
                    progress=15
                )
                builder.set_ontology(graph_id, ontology)
                
                # æ·»åŠ æ–‡æœ¬ï¼ˆprogress_callback ç­¾åæ˜¯ (msg, progress_ratio)ï¼‰
                def add_progress_callback(msg, progress_ratio):
                    progress = 15 + int(progress_ratio * 40)  # 15% - 55%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )
                
                task_manager.update_task(
                    task_id,
                    message=t('progress.addingChunks', count=total_chunks),
                    progress=15
                )
                
                episode_uuids = builder.add_text_batches(
                    graph_id, 
                    chunks,
                    batch_size=3,
                    progress_callback=add_progress_callback
                )
                
                # ç­‰å¾…Zepå¤„ç†å®Œæˆï¼ˆæŸ¥è¯¢æ¯ä¸ªepisodeçš„processedçŠ¶æ€ï¼‰
                task_manager.update_task(
                    task_id,
                    message=t('progress.waitingZepProcess'),
                    progress=55
                )
                
                def wait_progress_callback(msg, progress_ratio):
                    progress = 55 + int(progress_ratio * 35)  # 55% - 90%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )
                
                builder._wait_for_episodes(episode_uuids, wait_progress_callback)
                
                # èŽ·å–å›¾è°±æ•°æ®
                task_manager.update_task(
                    task_id,
                    message=t('progress.fetchingGraphData'),
                    progress=95
                )
                graph_data = builder.get_graph_data(graph_id)
                
                # æ›´æ–°é¡¹ç›®çŠ¶æ€
                project.status = ProjectStatus.GRAPH_COMPLETED
                ProjectManager.save_project(project)
                
                node_count = graph_data.get("node_count", 0)
                edge_count = graph_data.get("edge_count", 0)
                build_logger.info(f"[{task_id}] å›¾è°±æž„å»ºå®Œæˆ: graph_id={graph_id}, èŠ‚ç‚¹={node_count}, è¾¹={edge_count}")
                
                # å®Œæˆ
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    message=t('progress.graphBuildComplete'),
                    progress=100,
                    result={
                        "project_id": project_id,
                        "graph_id": graph_id,
                        "node_count": node_count,
                        "edge_count": edge_count,
                        "chunk_count": total_chunks
                    }
                )
                
            except Exception as e:
                # æ›´æ–°é¡¹ç›®çŠ¶æ€ä¸ºå¤±è´¥
                build_logger.error(f"[{task_id}] å›¾è°±æž„å»ºå¤±è´¥: {str(e)}")
                build_logger.debug(traceback.format_exc())
                
                project.status = ProjectStatus.FAILED
                project.error = str(e)
                ProjectManager.save_project(project)
                
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    message=t('progress.buildFailed', error=str(e)),
                    error=traceback.format_exc()
                )
        
        # å¯åŠ¨åŽå°çº¿ç¨‹
        thread = threading.Thread(target=build_task, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "task_id": task_id,
                "message": t('api.graphBuildStarted', taskId=task_id)
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== ä»»åŠ¡æŸ¥è¯¢æŽ¥å£ ==============

@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """
    æŸ¥è¯¢ä»»åŠ¡çŠ¶æ€
    """
    task = TaskManager().get_task(task_id)
    
    if not task:
        return jsonify({
            "success": False,
            "error": t('api.taskNotFound', id=task_id)
        }), 404
    
    return jsonify({
        "success": True,
        "data": task.to_dict()
    })


@graph_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """
    åˆ—å‡ºæ‰€æœ‰ä»»åŠ¡
    """
    tasks = TaskManager().list_tasks()
    
    return jsonify({
        "success": True,
        "data": [t.to_dict() for t in tasks],
        "count": len(tasks)
    })


# ============== å›¾è°±æ•°æ®æŽ¥å£ ==============

@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    """
    èŽ·å–å›¾è°±æ•°æ®ï¼ˆèŠ‚ç‚¹å’Œè¾¹ï¼‰
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": t('api.zepApiKeyMissing')
            }), 500
        
        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        graph_data = builder.get_graph_data(graph_id)
        
        return jsonify({
            "success": True,
            "data": graph_data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@graph_bp.route('/delete/<graph_id>', methods=['DELETE'])
def delete_graph(graph_id: str):
    """
    åˆ é™¤Zepå›¾è°±
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": t('api.zepApiKeyMissing')
            }), 500
        
        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        builder.delete_graph(graph_id)
        
        return jsonify({
            "success": True,
            "message": t('api.graphDeleted', id=graph_id)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

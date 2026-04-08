"""
Report APIè·¯ç”±
æä¾›æ¨¡æ‹ŸæŠ¥å‘Šç”Ÿæˆã€èŽ·å–ã€å¯¹è¯ç­‰æŽ¥å£
"""

import os
import traceback
import threading
from flask import request, jsonify, send_file

from . import report_bp
from ..config import Config
from ..services.report_agent import ReportAgent, ReportManager, ReportStatus
from ..services.simulation_manager import SimulationManager
from ..models.project import ProjectManager
from ..models.task import TaskManager, TaskStatus
from ..utils.logger import get_logger
from ..utils.locale import t, get_locale, set_locale

logger = get_logger('posiedon.api.report')


# ============== æŠ¥å‘Šç”ŸæˆæŽ¥å£ ==============

@report_bp.route('/generate', methods=['POST'])
def generate_report():
    """
    ç”Ÿæˆæ¨¡æ‹Ÿåˆ†æžæŠ¥å‘Šï¼ˆå¼‚æ­¥ä»»åŠ¡ï¼‰
    
    è¿™æ˜¯ä¸€ä¸ªè€—æ—¶æ“ä½œï¼ŒæŽ¥å£ä¼šç«‹å³è¿”å›žtask_idï¼Œ
    ä½¿ç”¨ GET /api/report/generate/status æŸ¥è¯¢è¿›åº¦
    
    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "simulation_id": "sim_xxxx",    // å¿…å¡«ï¼Œæ¨¡æ‹ŸID
            "force_regenerate": false        // å¯é€‰ï¼Œå¼ºåˆ¶é‡æ–°ç”Ÿæˆ
        }
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "task_id": "task_xxxx",
                "status": "generating",
                "message": "æŠ¥å‘Šç”Ÿæˆä»»åŠ¡å·²å¯åŠ¨"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        force_regenerate = data.get('force_regenerate', False)
        
        # èŽ·å–æ¨¡æ‹Ÿä¿¡æ¯
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404

        # æ£€æŸ¥æ˜¯å¦å·²æœ‰æŠ¥å‘Š
        if not force_regenerate:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": existing_report.report_id,
                        "status": "completed",
                        "message": t('api.reportAlreadyExists'),
                        "already_generated": True
                    }
                })
        
        # èŽ·å–é¡¹ç›®ä¿¡æ¯
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=state.project_id)
            }), 404
        
        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": t('api.missingGraphIdEnsure')
            }), 400
        
        simulation_requirement = project.simulation_requirement
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": t('api.missingSimRequirement')
            }), 400
        
        # æå‰ç”Ÿæˆ report_idï¼Œä»¥ä¾¿ç«‹å³è¿”å›žç»™å‰ç«¯
        import uuid
        report_id = f"report_{uuid.uuid4().hex[:12]}"
        
        # åˆ›å»ºå¼‚æ­¥ä»»åŠ¡
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="report_generate",
            metadata={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "report_id": report_id
            }
        )
        
        # Capture locale before spawning background thread
        current_locale = get_locale()

        # å®šä¹‰åŽå°ä»»åŠ¡
        def run_generate():
            set_locale(current_locale)
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message=t('api.initReportAgent')
                )
                
                # åˆ›å»ºReport Agent
                agent = ReportAgent(
                    graph_id=graph_id,
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement
                )
                
                # è¿›åº¦å›žè°ƒ
                def progress_callback(stage, progress, message):
                    task_manager.update_task(
                        task_id,
                        progress=progress,
                        message=f"[{stage}] {message}"
                    )
                
                # ç”ŸæˆæŠ¥å‘Šï¼ˆä¼ å…¥é¢„å…ˆç”Ÿæˆçš„ report_idï¼‰
                report = agent.generate_report(
                    progress_callback=progress_callback,
                    report_id=report_id
                )
                
                # ä¿å­˜æŠ¥å‘Š
                ReportManager.save_report(report)
                
                if report.status == ReportStatus.COMPLETED:
                    task_manager.complete_task(
                        task_id,
                        result={
                            "report_id": report.report_id,
                            "simulation_id": simulation_id,
                            "status": "completed"
                        }
                    )
                else:
                    task_manager.fail_task(task_id, report.error or t('api.reportGenerateFailed'))
                
            except Exception as e:
                logger.error(f"æŠ¥å‘Šç”Ÿæˆå¤±è´¥: {str(e)}")
                task_manager.fail_task(task_id, str(e))
        
        # å¯åŠ¨åŽå°çº¿ç¨‹
        thread = threading.Thread(target=run_generate, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "report_id": report_id,
                "task_id": task_id,
                "status": "generating",
                "message": t('api.reportGenerateStarted'),
                "already_generated": False
            }
        })
        
    except Exception as e:
        logger.error(f"å¯åŠ¨æŠ¥å‘Šç”Ÿæˆä»»åŠ¡å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/generate/status', methods=['POST'])
def get_generate_status():
    """
    æŸ¥è¯¢æŠ¥å‘Šç”Ÿæˆä»»åŠ¡è¿›åº¦
    
    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "task_id": "task_xxxx",         // å¯é€‰ï¼Œgenerateè¿”å›žçš„task_id
            "simulation_id": "sim_xxxx"     // å¯é€‰ï¼Œæ¨¡æ‹ŸID
        }
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|failed",
                "progress": 45,
                "message": "..."
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')
        
        # å¦‚æžœæä¾›äº†simulation_idï¼Œå…ˆæ£€æŸ¥æ˜¯å¦å·²æœ‰å®Œæˆçš„æŠ¥å‘Š
        if simulation_id:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": existing_report.report_id,
                        "status": "completed",
                        "progress": 100,
                        "message": t('api.reportGenerated'),
                        "already_completed": True
                    }
                })
        
        if not task_id:
            return jsonify({
                "success": False,
                "error": t('api.requireTaskOrSimId')
            }), 400
        
        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        
        if not task:
            return jsonify({
                "success": False,
                "error": t('api.taskNotFound', id=task_id)
            }), 404
        
        return jsonify({
            "success": True,
            "data": task.to_dict()
        })
        
    except Exception as e:
        logger.error(f"æŸ¥è¯¢ä»»åŠ¡çŠ¶æ€å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== æŠ¥å‘ŠèŽ·å–æŽ¥å£ ==============

@report_bp.route('/<report_id>', methods=['GET'])
def get_report(report_id: str):
    """
    èŽ·å–æŠ¥å‘Šè¯¦æƒ…
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                "simulation_id": "sim_xxxx",
                "status": "completed",
                "outline": {...},
                "markdown_content": "...",
                "created_at": "...",
                "completed_at": "..."
            }
        }
    """
    try:
        report = ReportManager.get_report(report_id)
        
        if not report:
            return jsonify({
                "success": False,
                "error": t('api.reportNotFound', id=report_id)
            }), 404
        
        return jsonify({
            "success": True,
            "data": report.to_dict()
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–æŠ¥å‘Šå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/by-simulation/<simulation_id>', methods=['GET'])
def get_report_by_simulation(simulation_id: str):
    """
    æ ¹æ®æ¨¡æ‹ŸIDèŽ·å–æŠ¥å‘Š
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                ...
            }
        }
    """
    try:
        report = ReportManager.get_report_by_simulation(simulation_id)
        
        if not report:
            return jsonify({
                "success": False,
                "error": t('api.noReportForSim', id=simulation_id),
                "has_report": False
            }), 404
        
        return jsonify({
            "success": True,
            "data": report.to_dict(),
            "has_report": True
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–æŠ¥å‘Šå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/list', methods=['GET'])
def list_reports():
    """
    åˆ—å‡ºæ‰€æœ‰æŠ¥å‘Š
    
    Queryå‚æ•°ï¼š
        simulation_id: æŒ‰æ¨¡æ‹ŸIDè¿‡æ»¤ï¼ˆå¯é€‰ï¼‰
        limit: è¿”å›žæ•°é‡é™åˆ¶ï¼ˆé»˜è®¤50ï¼‰
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": [...],
            "count": 10
        }
    """
    try:
        simulation_id = request.args.get('simulation_id')
        limit = request.args.get('limit', 50, type=int)
        
        reports = ReportManager.list_reports(
            simulation_id=simulation_id,
            limit=limit
        )
        
        return jsonify({
            "success": True,
            "data": [r.to_dict() for r in reports],
            "count": len(reports)
        })
        
    except Exception as e:
        logger.error(f"åˆ—å‡ºæŠ¥å‘Šå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/download', methods=['GET'])
def download_report(report_id: str):
    """
    ä¸‹è½½æŠ¥å‘Šï¼ˆMarkdownæ ¼å¼ï¼‰
    
    è¿”å›žMarkdownæ–‡ä»¶
    """
    try:
        report = ReportManager.get_report(report_id)
        
        if not report:
            return jsonify({
                "success": False,
                "error": t('api.reportNotFound', id=report_id)
            }), 404
        
        md_path = ReportManager._get_report_markdown_path(report_id)
        
        if not os.path.exists(md_path):
            # å¦‚æžœMDæ–‡ä»¶ä¸å­˜åœ¨ï¼Œç”Ÿæˆä¸€ä¸ªä¸´æ—¶æ–‡ä»¶
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(report.markdown_content)
                temp_path = f.name
            
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=f"{report_id}.md"
            )
        
        return send_file(
            md_path,
            as_attachment=True,
            download_name=f"{report_id}.md"
        )
        
    except Exception as e:
        logger.error(f"ä¸‹è½½æŠ¥å‘Šå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>', methods=['DELETE'])
def delete_report(report_id: str):
    """åˆ é™¤æŠ¥å‘Š"""
    try:
        success = ReportManager.delete_report(report_id)
        
        if not success:
            return jsonify({
                "success": False,
                "error": t('api.reportNotFound', id=report_id)
            }), 404
        
        return jsonify({
            "success": True,
            "message": t('api.reportDeleted', id=report_id)
        })
        
    except Exception as e:
        logger.error(f"åˆ é™¤æŠ¥å‘Šå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Report Agentå¯¹è¯æŽ¥å£ ==============

@report_bp.route('/chat', methods=['POST'])
def chat_with_report_agent():
    """
    ä¸ŽReport Agentå¯¹è¯
    
    Report Agentå¯ä»¥åœ¨å¯¹è¯ä¸­è‡ªä¸»è°ƒç”¨æ£€ç´¢å·¥å…·æ¥å›žç­”é—®é¢˜
    
    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "simulation_id": "sim_xxxx",        // å¿…å¡«ï¼Œæ¨¡æ‹ŸID
            "message": "è¯·è§£é‡Šä¸€ä¸‹èˆ†æƒ…èµ°å‘",    // å¿…å¡«ï¼Œç”¨æˆ·æ¶ˆæ¯
            "chat_history": [                   // å¯é€‰ï¼Œå¯¹è¯åŽ†å²
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "response": "Agentå›žå¤...",
                "tool_calls": [è°ƒç”¨çš„å·¥å…·åˆ—è¡¨],
                "sources": [ä¿¡æ¯æ¥æº]
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        message = data.get('message')
        chat_history = data.get('chat_history', [])
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        if not message:
            return jsonify({
                "success": False,
                "error": t('api.requireMessage')
            }), 400
        
        # èŽ·å–æ¨¡æ‹Ÿå’Œé¡¹ç›®ä¿¡æ¯
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404

        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=state.project_id)
            }), 404
        
        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": t('api.missingGraphId')
            }), 400
        
        simulation_requirement = project.simulation_requirement or ""
        
        # åˆ›å»ºAgentå¹¶è¿›è¡Œå¯¹è¯
        agent = ReportAgent(
            graph_id=graph_id,
            simulation_id=simulation_id,
            simulation_requirement=simulation_requirement
        )
        
        result = agent.chat(message=message, chat_history=chat_history)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"å¯¹è¯å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== æŠ¥å‘Šè¿›åº¦ä¸Žåˆ†ç« èŠ‚æŽ¥å£ ==============

@report_bp.route('/<report_id>/progress', methods=['GET'])
def get_report_progress(report_id: str):
    """
    èŽ·å–æŠ¥å‘Šç”Ÿæˆè¿›åº¦ï¼ˆå®žæ—¶ï¼‰
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "status": "generating",
                "progress": 45,
                "message": "æ­£åœ¨ç”Ÿæˆç« èŠ‚: å…³é”®å‘çŽ°",
                "current_section": "å…³é”®å‘çŽ°",
                "completed_sections": ["æ‰§è¡Œæ‘˜è¦", "æ¨¡æ‹ŸèƒŒæ™¯"],
                "updated_at": "2025-12-09T..."
            }
        }
    """
    try:
        progress = ReportManager.get_progress(report_id)
        
        if not progress:
            return jsonify({
                "success": False,
                "error": t('api.reportProgressNotAvail', id=report_id)
            }), 404
        
        return jsonify({
            "success": True,
            "data": progress
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–æŠ¥å‘Šè¿›åº¦å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/sections', methods=['GET'])
def get_report_sections(report_id: str):
    """
    èŽ·å–å·²ç”Ÿæˆçš„ç« èŠ‚åˆ—è¡¨ï¼ˆåˆ†ç« èŠ‚è¾“å‡ºï¼‰
    
    å‰ç«¯å¯ä»¥è½®è¯¢æ­¤æŽ¥å£èŽ·å–å·²ç”Ÿæˆçš„ç« èŠ‚å†…å®¹ï¼Œæ— éœ€ç­‰å¾…æ•´ä¸ªæŠ¥å‘Šå®Œæˆ
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                "sections": [
                    {
                        "filename": "section_01.md",
                        "section_index": 1,
                        "content": "## æ‰§è¡Œæ‘˜è¦\\n\\n..."
                    },
                    ...
                ],
                "total_sections": 3,
                "is_complete": false
            }
        }
    """
    try:
        sections = ReportManager.get_generated_sections(report_id)
        
        # èŽ·å–æŠ¥å‘ŠçŠ¶æ€
        report = ReportManager.get_report(report_id)
        is_complete = report is not None and report.status == ReportStatus.COMPLETED
        
        return jsonify({
            "success": True,
            "data": {
                "report_id": report_id,
                "sections": sections,
                "total_sections": len(sections),
                "is_complete": is_complete
            }
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–ç« èŠ‚åˆ—è¡¨å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/section/<int:section_index>', methods=['GET'])
def get_single_section(report_id: str, section_index: int):
    """
    èŽ·å–å•ä¸ªç« èŠ‚å†…å®¹
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "filename": "section_01.md",
                "content": "## æ‰§è¡Œæ‘˜è¦\\n\\n..."
            }
        }
    """
    try:
        section_path = ReportManager._get_section_path(report_id, section_index)
        
        if not os.path.exists(section_path):
            return jsonify({
                "success": False,
                "error": t('api.sectionNotFound', index=f"{section_index:02d}")
            }), 404
        
        with open(section_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            "success": True,
            "data": {
                "filename": f"section_{section_index:02d}.md",
                "section_index": section_index,
                "content": content
            }
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–ç« èŠ‚å†…å®¹å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== æŠ¥å‘ŠçŠ¶æ€æ£€æŸ¥æŽ¥å£ ==============

@report_bp.route('/check/<simulation_id>', methods=['GET'])
def check_report_status(simulation_id: str):
    """
    æ£€æŸ¥æ¨¡æ‹Ÿæ˜¯å¦æœ‰æŠ¥å‘Šï¼Œä»¥åŠæŠ¥å‘ŠçŠ¶æ€
    
    ç”¨äºŽå‰ç«¯åˆ¤æ–­æ˜¯å¦è§£é”InterviewåŠŸèƒ½
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "has_report": true,
                "report_status": "completed",
                "report_id": "report_xxxx",
                "interview_unlocked": true
            }
        }
    """
    try:
        report = ReportManager.get_report_by_simulation(simulation_id)
        
        has_report = report is not None
        report_status = report.status.value if report else None
        report_id = report.report_id if report else None
        
        # åªæœ‰æŠ¥å‘Šå®ŒæˆåŽæ‰è§£é”interview
        interview_unlocked = has_report and report.status == ReportStatus.COMPLETED
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "has_report": has_report,
                "report_status": report_status,
                "report_id": report_id,
                "interview_unlocked": interview_unlocked
            }
        })
        
    except Exception as e:
        logger.error(f"æ£€æŸ¥æŠ¥å‘ŠçŠ¶æ€å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Agent æ—¥å¿—æŽ¥å£ ==============

@report_bp.route('/<report_id>/agent-log', methods=['GET'])
def get_agent_log(report_id: str):
    """
    èŽ·å– Report Agent çš„è¯¦ç»†æ‰§è¡Œæ—¥å¿—
    
    å®žæ—¶èŽ·å–æŠ¥å‘Šç”Ÿæˆè¿‡ç¨‹ä¸­çš„æ¯ä¸€æ­¥åŠ¨ä½œï¼ŒåŒ…æ‹¬ï¼š
    - æŠ¥å‘Šå¼€å§‹ã€è§„åˆ’å¼€å§‹/å®Œæˆ
    - æ¯ä¸ªç« èŠ‚çš„å¼€å§‹ã€å·¥å…·è°ƒç”¨ã€LLMå“åº”ã€å®Œæˆ
    - æŠ¥å‘Šå®Œæˆæˆ–å¤±è´¥
    
    Queryå‚æ•°ï¼š
        from_line: ä»Žç¬¬å‡ è¡Œå¼€å§‹è¯»å–ï¼ˆå¯é€‰ï¼Œé»˜è®¤0ï¼Œç”¨äºŽå¢žé‡èŽ·å–ï¼‰
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "logs": [
                    {
                        "timestamp": "2025-12-13T...",
                        "elapsed_seconds": 12.5,
                        "report_id": "report_xxxx",
                        "action": "tool_call",
                        "stage": "generating",
                        "section_title": "æ‰§è¡Œæ‘˜è¦",
                        "section_index": 1,
                        "details": {
                            "tool_name": "insight_forge",
                            "parameters": {...},
                            ...
                        }
                    },
                    ...
                ],
                "total_lines": 25,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    try:
        from_line = request.args.get('from_line', 0, type=int)
        
        log_data = ReportManager.get_agent_log(report_id, from_line=from_line)
        
        return jsonify({
            "success": True,
            "data": log_data
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–Agentæ—¥å¿—å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/agent-log/stream', methods=['GET'])
def stream_agent_log(report_id: str):
    """
    èŽ·å–å®Œæ•´çš„ Agent æ—¥å¿—ï¼ˆä¸€æ¬¡æ€§èŽ·å–å…¨éƒ¨ï¼‰
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 25
            }
        }
    """
    try:
        logs = ReportManager.get_agent_log_stream(report_id)
        
        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–Agentæ—¥å¿—å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== æŽ§åˆ¶å°æ—¥å¿—æŽ¥å£ ==============

@report_bp.route('/<report_id>/console-log', methods=['GET'])
def get_console_log(report_id: str):
    """
    èŽ·å– Report Agent çš„æŽ§åˆ¶å°è¾“å‡ºæ—¥å¿—
    
    å®žæ—¶èŽ·å–æŠ¥å‘Šç”Ÿæˆè¿‡ç¨‹ä¸­çš„æŽ§åˆ¶å°è¾“å‡ºï¼ˆINFOã€WARNINGç­‰ï¼‰ï¼Œ
    è¿™ä¸Ž agent-log æŽ¥å£è¿”å›žçš„ç»“æž„åŒ– JSON æ—¥å¿—ä¸åŒï¼Œ
    æ˜¯çº¯æ–‡æœ¬æ ¼å¼çš„æŽ§åˆ¶å°é£Žæ ¼æ—¥å¿—ã€‚
    
    Queryå‚æ•°ï¼š
        from_line: ä»Žç¬¬å‡ è¡Œå¼€å§‹è¯»å–ï¼ˆå¯é€‰ï¼Œé»˜è®¤0ï¼Œç”¨äºŽå¢žé‡èŽ·å–ï¼‰
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "logs": [
                    "[19:46:14] INFO: æœç´¢å®Œæˆ: æ‰¾åˆ° 15 æ¡ç›¸å…³äº‹å®ž",
                    "[19:46:14] INFO: å›¾è°±æœç´¢: graph_id=xxx, query=...",
                    ...
                ],
                "total_lines": 100,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    try:
        from_line = request.args.get('from_line', 0, type=int)
        
        log_data = ReportManager.get_console_log(report_id, from_line=from_line)
        
        return jsonify({
            "success": True,
            "data": log_data
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–æŽ§åˆ¶å°æ—¥å¿—å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/console-log/stream', methods=['GET'])
def stream_console_log(report_id: str):
    """
    èŽ·å–å®Œæ•´çš„æŽ§åˆ¶å°æ—¥å¿—ï¼ˆä¸€æ¬¡æ€§èŽ·å–å…¨éƒ¨ï¼‰
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 100
            }
        }
    """
    try:
        logs = ReportManager.get_console_log_stream(report_id)
        
        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–æŽ§åˆ¶å°æ—¥å¿—å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== å·¥å…·è°ƒç”¨æŽ¥å£ï¼ˆä¾›è°ƒè¯•ä½¿ç”¨ï¼‰==============

@report_bp.route('/tools/search', methods=['POST'])
def search_graph_tool():
    """
    å›¾è°±æœç´¢å·¥å…·æŽ¥å£ï¼ˆä¾›è°ƒè¯•ä½¿ç”¨ï¼‰
    
    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "graph_id": "posiedon_xxxx",
            "query": "æœç´¢æŸ¥è¯¢",
            "limit": 10
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        query = data.get('query')
        limit = data.get('limit', 10)
        
        if not graph_id or not query:
            return jsonify({
                "success": False,
                "error": t('api.requireGraphIdAndQuery')
            }), 400
        
        from ..services.zep_tools import ZepToolsService
        
        tools = ZepToolsService()
        result = tools.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit
        )
        
        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"å›¾è°±æœç´¢å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/tools/statistics', methods=['POST'])
def get_graph_statistics_tool():
    """
    å›¾è°±ç»Ÿè®¡å·¥å…·æŽ¥å£ï¼ˆä¾›è°ƒè¯•ä½¿ç”¨ï¼‰
    
    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "graph_id": "posiedon_xxxx"
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        
        if not graph_id:
            return jsonify({
                "success": False,
                "error": t('api.requireGraphId')
            }), 400
        
        from ..services.zep_tools import ZepToolsService
        
        tools = ZepToolsService()
        result = tools.get_graph_statistics(graph_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–å›¾è°±ç»Ÿè®¡å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

"""
æ¨¡æ‹Ÿç›¸å…³APIè·¯ç”±
Step2: Zepå®žä½“è¯»å–ä¸Žè¿‡æ»¤ã€OASISæ¨¡æ‹Ÿå‡†å¤‡ä¸Žè¿è¡Œï¼ˆå…¨ç¨‹è‡ªåŠ¨åŒ–ï¼‰
"""

import os
import json
import traceback
from flask import request, jsonify, send_file

from . import simulation_bp
from ..config import Config
from ..services.zep_entity_reader import ZepEntityReader
from ..services.oasis_profile_generator import OasisProfileGenerator
from ..services.simulation_manager import SimulationManager, SimulationStatus
from ..services.simulation_runner import SimulationRunner, RunnerStatus
from ..services.job_queue import JobQueue, JobStatus
from ..utils.logger import get_logger
from ..utils.locale import t, get_locale, set_locale
from ..models.project import ProjectManager

logger = get_logger('posiedon.api.simulation')


# Interview prompt ä¼˜åŒ–å‰ç¼€
# æ·»åŠ æ­¤å‰ç¼€å¯ä»¥é¿å…Agentè°ƒç”¨å·¥å…·ï¼Œç›´æŽ¥ç”¨æ–‡æœ¬å›žå¤
INTERVIEW_PROMPT_PREFIX = "ç»“åˆä½ çš„äººè®¾ã€æ‰€æœ‰çš„è¿‡å¾€è®°å¿†ä¸Žè¡ŒåŠ¨ï¼Œä¸è°ƒç”¨ä»»ä½•å·¥å…·ç›´æŽ¥ç”¨æ–‡æœ¬å›žå¤æˆ‘ï¼š"


def optimize_interview_prompt(prompt: str) -> str:
    """
    ä¼˜åŒ–Interviewæé—®ï¼Œæ·»åŠ å‰ç¼€é¿å…Agentè°ƒç”¨å·¥å…·
    
    Args:
        prompt: åŽŸå§‹æé—®
        
    Returns:
        ä¼˜åŒ–åŽçš„æé—®
    """
    if not prompt:
        return prompt
    # é¿å…é‡å¤æ·»åŠ å‰ç¼€
    if prompt.startswith(INTERVIEW_PROMPT_PREFIX):
        return prompt
    return f"{INTERVIEW_PROMPT_PREFIX}{prompt}"


# ============== å®žä½“è¯»å–æŽ¥å£ ==============

@simulation_bp.route('/entities/<graph_id>', methods=['GET'])
def get_graph_entities(graph_id: str):
    """
    èŽ·å–å›¾è°±ä¸­çš„æ‰€æœ‰å®žä½“ï¼ˆå·²è¿‡æ»¤ï¼‰
    
    åªè¿”å›žç¬¦åˆé¢„å®šä¹‰å®žä½“ç±»åž‹çš„èŠ‚ç‚¹ï¼ˆLabelsä¸åªæ˜¯Entityçš„èŠ‚ç‚¹ï¼‰
    
    Queryå‚æ•°ï¼š
        entity_types: é€—å·åˆ†éš”çš„å®žä½“ç±»åž‹åˆ—è¡¨ï¼ˆå¯é€‰ï¼Œç”¨äºŽè¿›ä¸€æ­¥è¿‡æ»¤ï¼‰
        enrich: æ˜¯å¦èŽ·å–ç›¸å…³è¾¹ä¿¡æ¯ï¼ˆé»˜è®¤trueï¼‰
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": t('api.zepApiKeyMissing')
            }), 500
        
        entity_types_str = request.args.get('entity_types', '')
        entity_types = [t.strip() for t in entity_types_str.split(',') if t.strip()] if entity_types_str else None
        enrich = request.args.get('enrich', 'true').lower() == 'true'
        
        logger.info(f"èŽ·å–å›¾è°±å®žä½“: graph_id={graph_id}, entity_types={entity_types}, enrich={enrich}")
        
        reader = ZepEntityReader()
        result = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=enrich
        )
        
        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–å›¾è°±å®žä½“å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/<entity_uuid>', methods=['GET'])
def get_entity_detail(graph_id: str, entity_uuid: str):
    """èŽ·å–å•ä¸ªå®žä½“çš„è¯¦ç»†ä¿¡æ¯"""
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": t('api.zepApiKeyMissing')
            }), 500
        
        reader = ZepEntityReader()
        entity = reader.get_entity_with_context(graph_id, entity_uuid)
        
        if not entity:
            return jsonify({
                "success": False,
                "error": t('api.entityNotFound', id=entity_uuid)
            }), 404
        
        return jsonify({
            "success": True,
            "data": entity.to_dict()
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–å®žä½“è¯¦æƒ…å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/by-type/<entity_type>', methods=['GET'])
def get_entities_by_type(graph_id: str, entity_type: str):
    """èŽ·å–æŒ‡å®šç±»åž‹çš„æ‰€æœ‰å®žä½“"""
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": t('api.zepApiKeyMissing')
            }), 500
        
        enrich = request.args.get('enrich', 'true').lower() == 'true'
        
        reader = ZepEntityReader()
        entities = reader.get_entities_by_type(
            graph_id=graph_id,
            entity_type=entity_type,
            enrich_with_edges=enrich
        )
        
        return jsonify({
            "success": True,
            "data": {
                "entity_type": entity_type,
                "count": len(entities),
                "entities": [e.to_dict() for e in entities]
            }
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–å®žä½“å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== æ¨¡æ‹Ÿç®¡ç†æŽ¥å£ ==============

@simulation_bp.route('/create', methods=['POST'])
def create_simulation():
    """
    åˆ›å»ºæ–°çš„æ¨¡æ‹Ÿ
    
    æ³¨æ„ï¼šmax_roundsç­‰å‚æ•°ç”±LLMæ™ºèƒ½ç”Ÿæˆï¼Œæ— éœ€æ‰‹åŠ¨è®¾ç½®
    
    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "project_id": "proj_xxxx",      // å¿…å¡«
            "graph_id": "posiedon_xxxx",    // å¯é€‰ï¼Œå¦‚ä¸æä¾›åˆ™ä»ŽprojectèŽ·å–
            "enable_twitter": true,          // å¯é€‰ï¼Œé»˜è®¤true
            "enable_reddit": true            // å¯é€‰ï¼Œé»˜è®¤true
        }
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "project_id": "proj_xxxx",
                "graph_id": "posiedon_xxxx",
                "status": "created",
                "enable_twitter": true,
                "enable_reddit": true,
                "created_at": "2025-12-01T10:00:00"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        project_id = data.get('project_id')
        if not project_id:
            return jsonify({
                "success": False,
                "error": t('api.requireProjectId')
            }), 400
        
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=project_id)
            }), 404
        
        graph_id = data.get('graph_id') or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": t('api.graphNotBuilt')
            }), 400
        
        manager = SimulationManager()
        state = manager.create_simulation(
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=data.get('enable_twitter', True),
            enable_reddit=data.get('enable_reddit', True),
        )
        
        return jsonify({
            "success": True,
            "data": state.to_dict()
        })
        
    except Exception as e:
        logger.error(f"åˆ›å»ºæ¨¡æ‹Ÿå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _check_simulation_prepared(simulation_id: str) -> tuple:
    """
    æ£€æŸ¥æ¨¡æ‹Ÿæ˜¯å¦å·²ç»å‡†å¤‡å®Œæˆ
    
    æ£€æŸ¥æ¡ä»¶ï¼š
    1. state.json å­˜åœ¨ä¸” status ä¸º "ready"
    2. å¿…è¦æ–‡ä»¶å­˜åœ¨ï¼šreddit_profiles.json, twitter_profiles.csv, simulation_config.json
    
    æ³¨æ„ï¼šè¿è¡Œè„šæœ¬(run_*.py)ä¿ç•™åœ¨ backend/scripts/ ç›®å½•ï¼Œä¸å†å¤åˆ¶åˆ°æ¨¡æ‹Ÿç›®å½•
    
    Args:
        simulation_id: æ¨¡æ‹ŸID
        
    Returns:
        (is_prepared: bool, info: dict)
    """
    import os
    from ..config import Config
    
    simulation_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
    
    # æ£€æŸ¥ç›®å½•æ˜¯å¦å­˜åœ¨
    if not os.path.exists(simulation_dir):
        return False, {"reason": "æ¨¡æ‹Ÿç›®å½•ä¸å­˜åœ¨"}
    
    # å¿…è¦æ–‡ä»¶åˆ—è¡¨ï¼ˆä¸åŒ…æ‹¬è„šæœ¬ï¼Œè„šæœ¬ä½äºŽ backend/scripts/ï¼‰
    required_files = [
        "state.json",
        "simulation_config.json",
        "reddit_profiles.json",
        "twitter_profiles.csv"
    ]
    
    # æ£€æŸ¥æ–‡ä»¶æ˜¯å¦å­˜åœ¨
    existing_files = []
    missing_files = []
    for f in required_files:
        file_path = os.path.join(simulation_dir, f)
        if os.path.exists(file_path):
            existing_files.append(f)
        else:
            missing_files.append(f)
    
    if missing_files:
        return False, {
            "reason": "ç¼ºå°‘å¿…è¦æ–‡ä»¶",
            "missing_files": missing_files,
            "existing_files": existing_files
        }
    
    # æ£€æŸ¥state.jsonä¸­çš„çŠ¶æ€
    state_file = os.path.join(simulation_dir, "state.json")
    try:
        import json
        with open(state_file, 'r', encoding='utf-8') as f:
            state_data = json.load(f)
        
        status = state_data.get("status", "")
        config_generated = state_data.get("config_generated", False)
        
        # è¯¦ç»†æ—¥å¿—
        logger.debug(f"æ£€æµ‹æ¨¡æ‹Ÿå‡†å¤‡çŠ¶æ€: {simulation_id}, status={status}, config_generated={config_generated}")
        
        # å¦‚æžœ config_generated=True ä¸”æ–‡ä»¶å­˜åœ¨ï¼Œè®¤ä¸ºå‡†å¤‡å®Œæˆ
        # ä»¥ä¸‹çŠ¶æ€éƒ½è¯´æ˜Žå‡†å¤‡å·¥ä½œå·²å®Œæˆï¼š
        # - ready: å‡†å¤‡å®Œæˆï¼Œå¯ä»¥è¿è¡Œ
        # - preparing: å¦‚æžœ config_generated=True è¯´æ˜Žå·²å®Œæˆ
        # - running: æ­£åœ¨è¿è¡Œï¼Œè¯´æ˜Žå‡†å¤‡æ—©å°±å®Œæˆäº†
        # - completed: è¿è¡Œå®Œæˆï¼Œè¯´æ˜Žå‡†å¤‡æ—©å°±å®Œæˆäº†
        # - stopped: å·²åœæ­¢ï¼Œè¯´æ˜Žå‡†å¤‡æ—©å°±å®Œæˆäº†
        # - failed: è¿è¡Œå¤±è´¥ï¼ˆä½†å‡†å¤‡æ˜¯å®Œæˆçš„ï¼‰
        prepared_statuses = ["ready", "preparing", "running", "completed", "stopped", "failed"]
        if status in prepared_statuses and config_generated:
            # èŽ·å–æ–‡ä»¶ç»Ÿè®¡ä¿¡æ¯
            profiles_file = os.path.join(simulation_dir, "reddit_profiles.json")
            config_file = os.path.join(simulation_dir, "simulation_config.json")
            
            profiles_count = 0
            if os.path.exists(profiles_file):
                with open(profiles_file, 'r', encoding='utf-8') as f:
                    profiles_data = json.load(f)
                    profiles_count = len(profiles_data) if isinstance(profiles_data, list) else 0
            
            # å¦‚æžœçŠ¶æ€æ˜¯preparingä½†æ–‡ä»¶å·²å®Œæˆï¼Œè‡ªåŠ¨æ›´æ–°çŠ¶æ€ä¸ºready
            if status == "preparing":
                try:
                    state_data["status"] = "ready"
                    from datetime import datetime
                    state_data["updated_at"] = datetime.now().isoformat()
                    with open(state_file, 'w', encoding='utf-8') as f:
                        json.dump(state_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"è‡ªåŠ¨æ›´æ–°æ¨¡æ‹ŸçŠ¶æ€: {simulation_id} preparing -> ready")
                    status = "ready"
                except Exception as e:
                    logger.warning(f"è‡ªåŠ¨æ›´æ–°çŠ¶æ€å¤±è´¥: {e}")
            
            logger.info(f"æ¨¡æ‹Ÿ {simulation_id} æ£€æµ‹ç»“æžœ: å·²å‡†å¤‡å®Œæˆ (status={status}, config_generated={config_generated})")
            return True, {
                "status": status,
                "entities_count": state_data.get("entities_count", 0),
                "profiles_count": profiles_count,
                "entity_types": state_data.get("entity_types", []),
                "config_generated": config_generated,
                "created_at": state_data.get("created_at"),
                "updated_at": state_data.get("updated_at"),
                "existing_files": existing_files
            }
        else:
            logger.warning(f"æ¨¡æ‹Ÿ {simulation_id} æ£€æµ‹ç»“æžœ: æœªå‡†å¤‡å®Œæˆ (status={status}, config_generated={config_generated})")
            return False, {
                "reason": f"çŠ¶æ€ä¸åœ¨å·²å‡†å¤‡åˆ—è¡¨ä¸­æˆ–config_generatedä¸ºfalse: status={status}, config_generated={config_generated}",
                "status": status,
                "config_generated": config_generated
            }
            
    except Exception as e:
        return False, {"reason": f"è¯»å–çŠ¶æ€æ–‡ä»¶å¤±è´¥: {str(e)}"}


@simulation_bp.route('/prepare', methods=['POST'])
def prepare_simulation():
    """
    å‡†å¤‡æ¨¡æ‹ŸçŽ¯å¢ƒï¼ˆå¼‚æ­¥ä»»åŠ¡ï¼ŒLLMæ™ºèƒ½ç”Ÿæˆæ‰€æœ‰å‚æ•°ï¼‰
    
    è¿™æ˜¯ä¸€ä¸ªè€—æ—¶æ“ä½œï¼ŒæŽ¥å£ä¼šç«‹å³è¿”å›žtask_idï¼Œ
    ä½¿ç”¨ GET /api/simulation/prepare/status æŸ¥è¯¢è¿›åº¦
    
    ç‰¹æ€§ï¼š
    - è‡ªåŠ¨æ£€æµ‹å·²å®Œæˆçš„å‡†å¤‡å·¥ä½œï¼Œé¿å…é‡å¤ç”Ÿæˆ
    - å¦‚æžœå·²å‡†å¤‡å®Œæˆï¼Œç›´æŽ¥è¿”å›žå·²æœ‰ç»“æžœ
    - æ”¯æŒå¼ºåˆ¶é‡æ–°ç”Ÿæˆï¼ˆforce_regenerate=trueï¼‰
    
    æ­¥éª¤ï¼š
    1. æ£€æŸ¥æ˜¯å¦å·²æœ‰å®Œæˆçš„å‡†å¤‡å·¥ä½œ
    2. ä»ŽZepå›¾è°±è¯»å–å¹¶è¿‡æ»¤å®žä½“
    3. ä¸ºæ¯ä¸ªå®žä½“ç”ŸæˆOASIS Agent Profileï¼ˆå¸¦é‡è¯•æœºåˆ¶ï¼‰
    4. LLMæ™ºèƒ½ç”Ÿæˆæ¨¡æ‹Ÿé…ç½®ï¼ˆå¸¦é‡è¯•æœºåˆ¶ï¼‰
    5. ä¿å­˜é…ç½®æ–‡ä»¶å’Œé¢„è®¾è„šæœ¬
    
    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "simulation_id": "sim_xxxx",                   // å¿…å¡«ï¼Œæ¨¡æ‹ŸID
            "entity_types": ["Student", "PublicFigure"],  // å¯é€‰ï¼ŒæŒ‡å®šå®žä½“ç±»åž‹
            "use_llm_for_profiles": true,                 // å¯é€‰ï¼Œæ˜¯å¦ç”¨LLMç”Ÿæˆäººè®¾
            "parallel_profile_count": 5,                  // å¯é€‰ï¼Œå¹¶è¡Œç”Ÿæˆäººè®¾æ•°é‡ï¼Œé»˜è®¤5
            "force_regenerate": false                     // å¯é€‰ï¼Œå¼ºåˆ¶é‡æ–°ç”Ÿæˆï¼Œé»˜è®¤false
        }
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "task_id": "task_xxxx",           // æ–°ä»»åŠ¡æ—¶è¿”å›ž
                "status": "preparing|ready",
                "message": "å‡†å¤‡ä»»åŠ¡å·²å¯åŠ¨|å·²æœ‰å®Œæˆçš„å‡†å¤‡å·¥ä½œ",
                "already_prepared": true|false    // æ˜¯å¦å·²å‡†å¤‡å®Œæˆ
            }
        }
    """
    import threading
    import os
    from ..models.task import TaskManager, TaskStatus
    from ..config import Config
    
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400
        
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404
        
        # æ£€æŸ¥æ˜¯å¦å¼ºåˆ¶é‡æ–°ç”Ÿæˆ
        force_regenerate = data.get('force_regenerate', False)
        logger.info(f"å¼€å§‹å¤„ç† /prepare è¯·æ±‚: simulation_id={simulation_id}, force_regenerate={force_regenerate}")
        
        # æ£€æŸ¥æ˜¯å¦å·²ç»å‡†å¤‡å®Œæˆï¼ˆé¿å…é‡å¤ç”Ÿæˆï¼‰
        if not force_regenerate:
            logger.debug(f"æ£€æŸ¥æ¨¡æ‹Ÿ {simulation_id} æ˜¯å¦å·²å‡†å¤‡å®Œæˆ...")
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
            logger.debug(f"æ£€æŸ¥ç»“æžœ: is_prepared={is_prepared}, prepare_info={prepare_info}")
            if is_prepared:
                logger.info(f"æ¨¡æ‹Ÿ {simulation_id} å·²å‡†å¤‡å®Œæˆï¼Œè·³è¿‡é‡å¤ç”Ÿæˆ")
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "message": t('api.alreadyPrepared'),
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
            else:
                logger.info(f"æ¨¡æ‹Ÿ {simulation_id} æœªå‡†å¤‡å®Œæˆï¼Œå°†å¯åŠ¨å‡†å¤‡ä»»åŠ¡")
        
        # ä»Žé¡¹ç›®èŽ·å–å¿…è¦ä¿¡æ¯
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=state.project_id)
            }), 404
        
        # èŽ·å–æ¨¡æ‹Ÿéœ€æ±‚
        simulation_requirement = project.simulation_requirement or ""
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": t('api.projectMissingRequirement')
            }), 400
        
        # èŽ·å–æ–‡æ¡£æ–‡æœ¬
        document_text = ProjectManager.get_extracted_text(state.project_id) or ""
        
        entity_types_list = data.get('entity_types')
        use_llm_for_profiles = data.get('use_llm_for_profiles', True)
        parallel_profile_count = data.get('parallel_profile_count', 5)
        
        # ========== åŒæ­¥èŽ·å–å®žä½“æ•°é‡ï¼ˆåœ¨åŽå°ä»»åŠ¡å¯åŠ¨å‰ï¼‰ ==========
        # è¿™æ ·å‰ç«¯åœ¨è°ƒç”¨prepareåŽç«‹å³å°±èƒ½èŽ·å–åˆ°é¢„æœŸAgentæ€»æ•°
        try:
            logger.info(f"åŒæ­¥èŽ·å–å®žä½“æ•°é‡: graph_id={state.graph_id}")
            reader = ZepEntityReader()
            # å¿«é€Ÿè¯»å–å®žä½“ï¼ˆä¸éœ€è¦è¾¹ä¿¡æ¯ï¼Œåªç»Ÿè®¡æ•°é‡ï¼‰
            filtered_preview = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=entity_types_list,
                enrich_with_edges=False  # ä¸èŽ·å–è¾¹ä¿¡æ¯ï¼ŒåŠ å¿«é€Ÿåº¦
            )
            # ä¿å­˜å®žä½“æ•°é‡åˆ°çŠ¶æ€ï¼ˆä¾›å‰ç«¯ç«‹å³èŽ·å–ï¼‰
            state.entities_count = filtered_preview.filtered_count
            state.entity_types = list(filtered_preview.entity_types)
            logger.info(f"é¢„æœŸå®žä½“æ•°é‡: {filtered_preview.filtered_count}, ç±»åž‹: {filtered_preview.entity_types}")
        except Exception as e:
            logger.warning(f"åŒæ­¥èŽ·å–å®žä½“æ•°é‡å¤±è´¥ï¼ˆå°†åœ¨åŽå°ä»»åŠ¡ä¸­é‡è¯•ï¼‰: {e}")
            # å¤±è´¥ä¸å½±å“åŽç»­æµç¨‹ï¼ŒåŽå°ä»»åŠ¡ä¼šé‡æ–°èŽ·å–
        
        # åˆ›å»ºå¼‚æ­¥ä»»åŠ¡
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="simulation_prepare",
            metadata={
                "simulation_id": simulation_id,
                "project_id": state.project_id
            }
        )
        
        # æ›´æ–°æ¨¡æ‹ŸçŠ¶æ€ï¼ˆåŒ…å«é¢„å…ˆèŽ·å–çš„å®žä½“æ•°é‡ï¼‰
        state.status = SimulationStatus.PREPARING
        manager._save_simulation_state(state)
        
        # Capture locale before spawning background thread
        current_locale = get_locale()

        # å®šä¹‰åŽå°ä»»åŠ¡
        def run_prepare():
            set_locale(current_locale)
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message=t('progress.startPreparingEnv')
                )
                
                # å‡†å¤‡æ¨¡æ‹Ÿï¼ˆå¸¦è¿›åº¦å›žè°ƒï¼‰
                # å­˜å‚¨é˜¶æ®µè¿›åº¦è¯¦æƒ…
                stage_details = {}
                
                def progress_callback(stage, progress, message, **kwargs):
                    # è®¡ç®—æ€»è¿›åº¦
                    stage_weights = {
                        "reading": (0, 20),           # 0-20%
                        "generating_profiles": (20, 70),  # 20-70%
                        "generating_config": (70, 90),    # 70-90%
                        "copying_scripts": (90, 100)       # 90-100%
                    }
                    
                    start, end = stage_weights.get(stage, (0, 100))
                    current_progress = int(start + (end - start) * progress / 100)
                    
                    # æž„å»ºè¯¦ç»†è¿›åº¦ä¿¡æ¯
                    stage_names = {
                        "reading": t('progress.readingGraphEntities'),
                        "generating_profiles": t('progress.generatingProfiles'),
                        "generating_config": t('progress.generatingSimConfig'),
                        "copying_scripts": t('progress.preparingScripts')
                    }
                    
                    stage_index = list(stage_weights.keys()).index(stage) + 1 if stage in stage_weights else 1
                    total_stages = len(stage_weights)
                    
                    # æ›´æ–°é˜¶æ®µè¯¦æƒ…
                    stage_details[stage] = {
                        "stage_name": stage_names.get(stage, stage),
                        "stage_progress": progress,
                        "current": kwargs.get("current", 0),
                        "total": kwargs.get("total", 0),
                        "item_name": kwargs.get("item_name", "")
                    }
                    
                    # æž„å»ºè¯¦ç»†è¿›åº¦ä¿¡æ¯
                    detail = stage_details[stage]
                    progress_detail_data = {
                        "current_stage": stage,
                        "current_stage_name": stage_names.get(stage, stage),
                        "stage_index": stage_index,
                        "total_stages": total_stages,
                        "stage_progress": progress,
                        "current_item": detail["current"],
                        "total_items": detail["total"],
                        "item_description": message
                    }
                    
                    # æž„å»ºç®€æ´æ¶ˆæ¯
                    if detail["total"] > 0:
                        detailed_message = (
                            f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: "
                            f"{detail['current']}/{detail['total']} - {message}"
                        )
                    else:
                        detailed_message = f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: {message}"
                    
                    task_manager.update_task(
                        task_id,
                        progress=current_progress,
                        message=detailed_message,
                        progress_detail=progress_detail_data
                    )
                
                result_state = manager.prepare_simulation(
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement,
                    document_text=document_text,
                    defined_entity_types=entity_types_list,
                    use_llm_for_profiles=use_llm_for_profiles,
                    progress_callback=progress_callback,
                    parallel_profile_count=parallel_profile_count
                )
                
                # ä»»åŠ¡å®Œæˆ
                task_manager.complete_task(
                    task_id,
                    result=result_state.to_simple_dict()
                )
                
            except Exception as e:
                logger.error(f"å‡†å¤‡æ¨¡æ‹Ÿå¤±è´¥: {str(e)}")
                task_manager.fail_task(task_id, str(e))
                
                # æ›´æ–°æ¨¡æ‹ŸçŠ¶æ€ä¸ºå¤±è´¥
                state = manager.get_simulation(simulation_id)
                if state:
                    state.status = SimulationStatus.FAILED
                    state.error = str(e)
                    manager._save_simulation_state(state)
        
        # å¯åŠ¨åŽå°çº¿ç¨‹
        thread = threading.Thread(target=run_prepare, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "task_id": task_id,
                "status": "preparing",
                "message": t('api.prepareStarted'),
                "already_prepared": False,
                "expected_entities_count": state.entities_count,  # é¢„æœŸçš„Agentæ€»æ•°
                "entity_types": state.entity_types  # å®žä½“ç±»åž‹åˆ—è¡¨
            }
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"å¯åŠ¨å‡†å¤‡ä»»åŠ¡å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/prepare/status', methods=['POST'])
def get_prepare_status():
    """
    æŸ¥è¯¢å‡†å¤‡ä»»åŠ¡è¿›åº¦
    
    æ”¯æŒä¸¤ç§æŸ¥è¯¢æ–¹å¼ï¼š
    1. é€šè¿‡task_idæŸ¥è¯¢æ­£åœ¨è¿›è¡Œçš„ä»»åŠ¡è¿›åº¦
    2. é€šè¿‡simulation_idæ£€æŸ¥æ˜¯å¦å·²æœ‰å®Œæˆçš„å‡†å¤‡å·¥ä½œ
    
    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "task_id": "task_xxxx",          // å¯é€‰ï¼Œprepareè¿”å›žçš„task_id
            "simulation_id": "sim_xxxx"      // å¯é€‰ï¼Œæ¨¡æ‹ŸIDï¼ˆç”¨äºŽæ£€æŸ¥å·²å®Œæˆçš„å‡†å¤‡ï¼‰
        }
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|ready",
                "progress": 45,
                "message": "...",
                "already_prepared": true|false,  // æ˜¯å¦å·²æœ‰å®Œæˆçš„å‡†å¤‡
                "prepare_info": {...}            // å·²å‡†å¤‡å®Œæˆæ—¶çš„è¯¦ç»†ä¿¡æ¯
            }
        }
    """
    from ..models.task import TaskManager
    
    try:
        data = request.get_json() or {}
        
        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')
        
        # å¦‚æžœæä¾›äº†simulation_idï¼Œå…ˆæ£€æŸ¥æ˜¯å¦å·²å‡†å¤‡å®Œæˆ
        if simulation_id:
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
            if is_prepared:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "progress": 100,
                        "message": t('api.alreadyPrepared'),
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
        
        # å¦‚æžœæ²¡æœ‰task_idï¼Œè¿”å›žé”™è¯¯
        if not task_id:
            if simulation_id:
                # æœ‰simulation_idä½†æœªå‡†å¤‡å®Œæˆ
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "not_started",
                        "progress": 0,
                        "message": t('api.notStartedPrepare'),
                        "already_prepared": False
                    }
                })
            return jsonify({
                "success": False,
                "error": t('api.requireTaskOrSimId')
            }), 400
        
        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        
        if not task:
            # ä»»åŠ¡ä¸å­˜åœ¨ï¼Œä½†å¦‚æžœæœ‰simulation_idï¼Œæ£€æŸ¥æ˜¯å¦å·²å‡†å¤‡å®Œæˆ
            if simulation_id:
                is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
                if is_prepared:
                    return jsonify({
                        "success": True,
                        "data": {
                            "simulation_id": simulation_id,
                            "task_id": task_id,
                            "status": "ready",
                            "progress": 100,
                            "message": t('api.taskCompletedPrepared'),
                            "already_prepared": True,
                            "prepare_info": prepare_info
                        }
                    })
            
            return jsonify({
                "success": False,
                "error": t('api.taskNotFound', id=task_id)
            }), 404
        
        task_dict = task.to_dict()
        task_dict["already_prepared"] = False
        
        return jsonify({
            "success": True,
            "data": task_dict
        })
        
    except Exception as e:
        logger.error(f"æŸ¥è¯¢ä»»åŠ¡çŠ¶æ€å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>', methods=['GET'])
def get_simulation(simulation_id: str):
    """èŽ·å–æ¨¡æ‹ŸçŠ¶æ€"""
    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404
        
        result = state.to_dict()
        
        # å¦‚æžœæ¨¡æ‹Ÿå·²å‡†å¤‡å¥½ï¼Œé™„åŠ è¿è¡Œè¯´æ˜Ž
        if state.status == SimulationStatus.READY:
            result["run_instructions"] = manager.get_run_instructions(simulation_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–æ¨¡æ‹ŸçŠ¶æ€å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/list', methods=['GET'])
def list_simulations():
    """
    åˆ—å‡ºæ‰€æœ‰æ¨¡æ‹Ÿ
    
    Queryå‚æ•°ï¼š
        project_id: æŒ‰é¡¹ç›®IDè¿‡æ»¤ï¼ˆå¯é€‰ï¼‰
    """
    try:
        project_id = request.args.get('project_id')
        
        manager = SimulationManager()
        simulations = manager.list_simulations(project_id=project_id)
        
        return jsonify({
            "success": True,
            "data": [s.to_dict() for s in simulations],
            "count": len(simulations)
        })
        
    except Exception as e:
        logger.error(f"åˆ—å‡ºæ¨¡æ‹Ÿå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _get_report_id_for_simulation(simulation_id: str) -> str:
    """
    èŽ·å– simulation å¯¹åº”çš„æœ€æ–° report_id
    
    éåŽ† reports ç›®å½•ï¼Œæ‰¾å‡º simulation_id åŒ¹é…çš„ reportï¼Œ
    å¦‚æžœæœ‰å¤šä¸ªåˆ™è¿”å›žæœ€æ–°çš„ï¼ˆæŒ‰ created_at æŽ’åºï¼‰
    
    Args:
        simulation_id: æ¨¡æ‹ŸID
        
    Returns:
        report_id æˆ– None
    """
    import json
    from datetime import datetime
    
    # reports ç›®å½•è·¯å¾„ï¼šbackend/uploads/reports
    # __file__ æ˜¯ app/api/simulation.pyï¼Œéœ€è¦å‘ä¸Šä¸¤çº§åˆ° backend/
    reports_dir = os.path.join(os.path.dirname(__file__), '../../uploads/reports')
    if not os.path.exists(reports_dir):
        return None
    
    matching_reports = []
    
    try:
        for report_folder in os.listdir(reports_dir):
            report_path = os.path.join(reports_dir, report_folder)
            if not os.path.isdir(report_path):
                continue
            
            meta_file = os.path.join(report_path, "meta.json")
            if not os.path.exists(meta_file):
                continue
            
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                
                if meta.get("simulation_id") == simulation_id:
                    matching_reports.append({
                        "report_id": meta.get("report_id"),
                        "created_at": meta.get("created_at", ""),
                        "status": meta.get("status", "")
                    })
            except Exception:
                continue
        
        if not matching_reports:
            return None
        
        # æŒ‰åˆ›å»ºæ—¶é—´å€’åºæŽ’åºï¼Œè¿”å›žæœ€æ–°çš„
        matching_reports.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return matching_reports[0].get("report_id")
        
    except Exception as e:
        logger.warning(f"æŸ¥æ‰¾ simulation {simulation_id} çš„ report å¤±è´¥: {e}")
        return None


@simulation_bp.route('/history', methods=['GET'])
def get_simulation_history():
    """
    èŽ·å–åŽ†å²æ¨¡æ‹Ÿåˆ—è¡¨ï¼ˆå¸¦é¡¹ç›®è¯¦æƒ…ï¼‰
    
    ç”¨äºŽé¦–é¡µåŽ†å²é¡¹ç›®å±•ç¤ºï¼Œè¿”å›žåŒ…å«é¡¹ç›®åç§°ã€æè¿°ç­‰ä¸°å¯Œä¿¡æ¯çš„æ¨¡æ‹Ÿåˆ—è¡¨
    
    Queryå‚æ•°ï¼š
        limit: è¿”å›žæ•°é‡é™åˆ¶ï¼ˆé»˜è®¤20ï¼‰
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": [
                {
                    "simulation_id": "sim_xxxx",
                    "project_id": "proj_xxxx",
                    "project_name": "æ­¦å¤§èˆ†æƒ…åˆ†æž",
                    "simulation_requirement": "å¦‚æžœæ­¦æ±‰å¤§å­¦å‘å¸ƒ...",
                    "status": "completed",
                    "entities_count": 68,
                    "profiles_count": 68,
                    "entity_types": ["Student", "Professor", ...],
                    "created_at": "2024-12-10",
                    "updated_at": "2024-12-10",
                    "total_rounds": 120,
                    "current_round": 120,
                    "report_id": "report_xxxx",
                    "version": "v1.0.2"
                },
                ...
            ],
            "count": 7
        }
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        
        manager = SimulationManager()
        simulations = manager.list_simulations()[:limit]
        
        # å¢žå¼ºæ¨¡æ‹Ÿæ•°æ®ï¼Œåªä»Ž Simulation æ–‡ä»¶è¯»å–
        enriched_simulations = []
        for sim in simulations:
            sim_dict = sim.to_dict()
            
            # èŽ·å–æ¨¡æ‹Ÿé…ç½®ä¿¡æ¯ï¼ˆä»Ž simulation_config.json è¯»å– simulation_requirementï¼‰
            config = manager.get_simulation_config(sim.simulation_id)
            if config:
                sim_dict["simulation_requirement"] = config.get("simulation_requirement", "")
                time_config = config.get("time_config", {})
                sim_dict["total_simulation_hours"] = time_config.get("total_simulation_hours", 0)
                # æŽ¨èè½®æ•°ï¼ˆåŽå¤‡å€¼ï¼‰
                recommended_rounds = int(
                    time_config.get("total_simulation_hours", 0) * 60 / 
                    max(time_config.get("minutes_per_round", 60), 1)
                )
            else:
                sim_dict["simulation_requirement"] = ""
                sim_dict["total_simulation_hours"] = 0
                recommended_rounds = 0
            
            # èŽ·å–è¿è¡ŒçŠ¶æ€ï¼ˆä»Ž run_state.json è¯»å–ç”¨æˆ·è®¾ç½®çš„å®žé™…è½®æ•°ï¼‰
            run_state = SimulationRunner.get_run_state(sim.simulation_id)
            if run_state:
                sim_dict["current_round"] = run_state.current_round
                sim_dict["runner_status"] = run_state.runner_status.value
                # ä½¿ç”¨ç”¨æˆ·è®¾ç½®çš„ total_roundsï¼Œè‹¥æ— åˆ™ä½¿ç”¨æŽ¨èè½®æ•°
                sim_dict["total_rounds"] = run_state.total_rounds if run_state.total_rounds > 0 else recommended_rounds
            else:
                sim_dict["current_round"] = 0
                sim_dict["runner_status"] = "idle"
                sim_dict["total_rounds"] = recommended_rounds
            
            # èŽ·å–å…³è”é¡¹ç›®çš„æ–‡ä»¶åˆ—è¡¨ï¼ˆæœ€å¤š3ä¸ªï¼‰
            project = ProjectManager.get_project(sim.project_id)
            if project and hasattr(project, 'files') and project.files:
                sim_dict["files"] = [
                    {"filename": f.get("filename", "æœªçŸ¥æ–‡ä»¶")} 
                    for f in project.files[:3]
                ]
            else:
                sim_dict["files"] = []
            
            # èŽ·å–å…³è”çš„ report_idï¼ˆæŸ¥æ‰¾è¯¥ simulation æœ€æ–°çš„ reportï¼‰
            sim_dict["report_id"] = _get_report_id_for_simulation(sim.simulation_id)
            
            # æ·»åŠ ç‰ˆæœ¬å·
            sim_dict["version"] = "v1.0.2"
            
            # æ ¼å¼åŒ–æ—¥æœŸ
            try:
                created_date = sim_dict.get("created_at", "")[:10]
                sim_dict["created_date"] = created_date
            except:
                sim_dict["created_date"] = ""
            
            enriched_simulations.append(sim_dict)
        
        return jsonify({
            "success": True,
            "data": enriched_simulations,
            "count": len(enriched_simulations)
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–åŽ†å²æ¨¡æ‹Ÿå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles', methods=['GET'])
def get_simulation_profiles(simulation_id: str):
    """
    èŽ·å–æ¨¡æ‹Ÿçš„Agent Profile
    
    Queryå‚æ•°ï¼š
        platform: å¹³å°ç±»åž‹ï¼ˆreddit/twitterï¼Œé»˜è®¤redditï¼‰
    """
    try:
        platform = request.args.get('platform', 'reddit')
        
        manager = SimulationManager()
        profiles = manager.get_profiles(simulation_id, platform=platform)
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "count": len(profiles),
                "profiles": profiles
            }
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"èŽ·å–Profileå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles/realtime', methods=['GET'])
def get_simulation_profiles_realtime(simulation_id: str):
    """
    å®žæ—¶èŽ·å–æ¨¡æ‹Ÿçš„Agent Profileï¼ˆç”¨äºŽåœ¨ç”Ÿæˆè¿‡ç¨‹ä¸­å®žæ—¶æŸ¥çœ‹è¿›åº¦ï¼‰
    
    ä¸Ž /profiles æŽ¥å£çš„åŒºåˆ«ï¼š
    - ç›´æŽ¥è¯»å–æ–‡ä»¶ï¼Œä¸ç»è¿‡ SimulationManager
    - é€‚ç”¨äºŽç”Ÿæˆè¿‡ç¨‹ä¸­çš„å®žæ—¶æŸ¥çœ‹
    - è¿”å›žé¢å¤–çš„å…ƒæ•°æ®ï¼ˆå¦‚æ–‡ä»¶ä¿®æ”¹æ—¶é—´ã€æ˜¯å¦æ­£åœ¨ç”Ÿæˆç­‰ï¼‰
    
    Queryå‚æ•°ï¼š
        platform: å¹³å°ç±»åž‹ï¼ˆreddit/twitterï¼Œé»˜è®¤redditï¼‰
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "platform": "reddit",
                "count": 15,
                "total_expected": 93,  // é¢„æœŸæ€»æ•°ï¼ˆå¦‚æžœæœ‰ï¼‰
                "is_generating": true,  // æ˜¯å¦æ­£åœ¨ç”Ÿæˆ
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "profiles": [...]
            }
        }
    """
    import json
    import csv
    from datetime import datetime
    
    try:
        platform = request.args.get('platform', 'reddit')
        
        # èŽ·å–æ¨¡æ‹Ÿç›®å½•
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
        
        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404
        
        # ç¡®å®šæ–‡ä»¶è·¯å¾„
        if platform == "reddit":
            profiles_file = os.path.join(sim_dir, "reddit_profiles.json")
        else:
            profiles_file = os.path.join(sim_dir, "twitter_profiles.csv")
        
        # æ£€æŸ¥æ–‡ä»¶æ˜¯å¦å­˜åœ¨
        file_exists = os.path.exists(profiles_file)
        profiles = []
        file_modified_at = None
        
        if file_exists:
            # èŽ·å–æ–‡ä»¶ä¿®æ”¹æ—¶é—´
            file_stat = os.stat(profiles_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                if platform == "reddit":
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        profiles = json.load(f)
                else:
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        profiles = list(reader)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"è¯»å– profiles æ–‡ä»¶å¤±è´¥ï¼ˆå¯èƒ½æ­£åœ¨å†™å…¥ä¸­ï¼‰: {e}")
                profiles = []
        
        # æ£€æŸ¥æ˜¯å¦æ­£åœ¨ç”Ÿæˆï¼ˆé€šè¿‡ state.json åˆ¤æ–­ï¼‰
        is_generating = False
        total_expected = None
        
        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    is_generating = status == "preparing"
                    total_expected = state_data.get("entities_count")
            except Exception:
                pass
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "platform": platform,
                "count": len(profiles),
                "total_expected": total_expected,
                "is_generating": is_generating,
                "file_exists": file_exists,
                "file_modified_at": file_modified_at,
                "profiles": profiles
            }
        })
        
    except Exception as e:
        logger.error(f"å®žæ—¶èŽ·å–Profileå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/realtime', methods=['GET'])
def get_simulation_config_realtime(simulation_id: str):
    """
    å®žæ—¶èŽ·å–æ¨¡æ‹Ÿé…ç½®ï¼ˆç”¨äºŽåœ¨ç”Ÿæˆè¿‡ç¨‹ä¸­å®žæ—¶æŸ¥çœ‹è¿›åº¦ï¼‰
    
    ä¸Ž /config æŽ¥å£çš„åŒºåˆ«ï¼š
    - ç›´æŽ¥è¯»å–æ–‡ä»¶ï¼Œä¸ç»è¿‡ SimulationManager
    - é€‚ç”¨äºŽç”Ÿæˆè¿‡ç¨‹ä¸­çš„å®žæ—¶æŸ¥çœ‹
    - è¿”å›žé¢å¤–çš„å…ƒæ•°æ®ï¼ˆå¦‚æ–‡ä»¶ä¿®æ”¹æ—¶é—´ã€æ˜¯å¦æ­£åœ¨ç”Ÿæˆç­‰ï¼‰
    - å³ä½¿é…ç½®è¿˜æ²¡ç”Ÿæˆå®Œä¹Ÿèƒ½è¿”å›žéƒ¨åˆ†ä¿¡æ¯
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "is_generating": true,  // æ˜¯å¦æ­£åœ¨ç”Ÿæˆ
                "generation_stage": "generating_config",  // å½“å‰ç”Ÿæˆé˜¶æ®µ
                "config": {...}  // é…ç½®å†…å®¹ï¼ˆå¦‚æžœå­˜åœ¨ï¼‰
            }
        }
    """
    import json
    from datetime import datetime
    
    try:
        # èŽ·å–æ¨¡æ‹Ÿç›®å½•
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
        
        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404
        
        # é…ç½®æ–‡ä»¶è·¯å¾„
        config_file = os.path.join(sim_dir, "simulation_config.json")
        
        # æ£€æŸ¥æ–‡ä»¶æ˜¯å¦å­˜åœ¨
        file_exists = os.path.exists(config_file)
        config = None
        file_modified_at = None
        
        if file_exists:
            # èŽ·å–æ–‡ä»¶ä¿®æ”¹æ—¶é—´
            file_stat = os.stat(config_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"è¯»å– config æ–‡ä»¶å¤±è´¥ï¼ˆå¯èƒ½æ­£åœ¨å†™å…¥ä¸­ï¼‰: {e}")
                config = None
        
        # æ£€æŸ¥æ˜¯å¦æ­£åœ¨ç”Ÿæˆï¼ˆé€šè¿‡ state.json åˆ¤æ–­ï¼‰
        is_generating = False
        generation_stage = None
        config_generated = False
        
        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    is_generating = status == "preparing"
                    config_generated = state_data.get("config_generated", False)
                    
                    # åˆ¤æ–­å½“å‰é˜¶æ®µ
                    if is_generating:
                        if state_data.get("profiles_generated", False):
                            generation_stage = "generating_config"
                        else:
                            generation_stage = "generating_profiles"
                    elif status == "ready":
                        generation_stage = "completed"
            except Exception:
                pass
        
        # æž„å»ºè¿”å›žæ•°æ®
        response_data = {
            "simulation_id": simulation_id,
            "file_exists": file_exists,
            "file_modified_at": file_modified_at,
            "is_generating": is_generating,
            "generation_stage": generation_stage,
            "config_generated": config_generated,
            "config": config
        }
        
        # å¦‚æžœé…ç½®å­˜åœ¨ï¼Œæå–ä¸€äº›å…³é”®ç»Ÿè®¡ä¿¡æ¯
        if config:
            response_data["summary"] = {
                "total_agents": len(config.get("agent_configs", [])),
                "simulation_hours": config.get("time_config", {}).get("total_simulation_hours"),
                "initial_posts_count": len(config.get("event_config", {}).get("initial_posts", [])),
                "hot_topics_count": len(config.get("event_config", {}).get("hot_topics", [])),
                "has_twitter_config": "twitter_config" in config,
                "has_reddit_config": "reddit_config" in config,
                "generated_at": config.get("generated_at"),
                "llm_model": config.get("llm_model")
            }
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except Exception as e:
        logger.error(f"å®žæ—¶èŽ·å–Configå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config', methods=['GET'])
def get_simulation_config(simulation_id: str):
    """
    èŽ·å–æ¨¡æ‹Ÿé…ç½®ï¼ˆLLMæ™ºèƒ½ç”Ÿæˆçš„å®Œæ•´é…ç½®ï¼‰
    
    è¿”å›žåŒ…å«ï¼š
        - time_config: æ—¶é—´é…ç½®ï¼ˆæ¨¡æ‹Ÿæ—¶é•¿ã€è½®æ¬¡ã€é«˜å³°/ä½Žè°·æ—¶æ®µï¼‰
        - agent_configs: æ¯ä¸ªAgentçš„æ´»åŠ¨é…ç½®ï¼ˆæ´»è·ƒåº¦ã€å‘è¨€é¢‘çŽ‡ã€ç«‹åœºç­‰ï¼‰
        - event_config: äº‹ä»¶é…ç½®ï¼ˆåˆå§‹å¸–å­ã€çƒ­ç‚¹è¯é¢˜ï¼‰
        - platform_configs: å¹³å°é…ç½®
        - generation_reasoning: LLMçš„é…ç½®æŽ¨ç†è¯´æ˜Ž
    """
    try:
        manager = SimulationManager()
        config = manager.get_simulation_config(simulation_id)
        
        if not config:
            return jsonify({
                "success": False,
                "error": t('api.configNotFound')
            }), 404
        
        return jsonify({
            "success": True,
            "data": config
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–é…ç½®å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/download', methods=['GET'])
def download_simulation_config(simulation_id: str):
    """ä¸‹è½½æ¨¡æ‹Ÿé…ç½®æ–‡ä»¶"""
    try:
        manager = SimulationManager()
        sim_dir = manager._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return jsonify({
                "success": False,
                "error": t('api.configFileNotFound')
            }), 404
        
        return send_file(
            config_path,
            as_attachment=True,
            download_name="simulation_config.json"
        )
        
    except Exception as e:
        logger.error(f"ä¸‹è½½é…ç½®å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/script/<script_name>/download', methods=['GET'])
def download_simulation_script(script_name: str):
    """
    ä¸‹è½½æ¨¡æ‹Ÿè¿è¡Œè„šæœ¬æ–‡ä»¶ï¼ˆé€šç”¨è„šæœ¬ï¼Œä½äºŽ backend/scripts/ï¼‰
    
    script_nameå¯é€‰å€¼ï¼š
        - run_twitter_simulation.py
        - run_reddit_simulation.py
        - run_parallel_simulation.py
        - action_logger.py
    """
    try:
        # è„šæœ¬ä½äºŽ backend/scripts/ ç›®å½•
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))
        
        # éªŒè¯è„šæœ¬åç§°
        allowed_scripts = [
            "run_twitter_simulation.py",
            "run_reddit_simulation.py", 
            "run_parallel_simulation.py",
            "action_logger.py"
        ]
        
        if script_name not in allowed_scripts:
            return jsonify({
                "success": False,
                "error": t('api.unknownScript', name=script_name, allowed=allowed_scripts)
            }), 400
        
        script_path = os.path.join(scripts_dir, script_name)
        
        if not os.path.exists(script_path):
            return jsonify({
                "success": False,
                "error": t('api.scriptFileNotFound', name=script_name)
            }), 404
        
        return send_file(
            script_path,
            as_attachment=True,
            download_name=script_name
        )
        
    except Exception as e:
        logger.error(f"ä¸‹è½½è„šæœ¬å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Profileç”ŸæˆæŽ¥å£ï¼ˆç‹¬ç«‹ä½¿ç”¨ï¼‰ ==============

@simulation_bp.route('/generate-profiles', methods=['POST'])
def generate_profiles():
    """
    ç›´æŽ¥ä»Žå›¾è°±ç”ŸæˆOASIS Agent Profileï¼ˆä¸åˆ›å»ºæ¨¡æ‹Ÿï¼‰
    
    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "graph_id": "posiedon_xxxx",     // å¿…å¡«
            "entity_types": ["Student"],      // å¯é€‰
            "use_llm": true,                  // å¯é€‰
            "platform": "reddit"              // å¯é€‰
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
        
        entity_types = data.get('entity_types')
        use_llm = data.get('use_llm', True)
        platform = data.get('platform', 'reddit')
        
        reader = ZepEntityReader()
        filtered = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=True
        )
        
        if filtered.filtered_count == 0:
            return jsonify({
                "success": False,
                "error": t('api.noMatchingEntities')
            }), 400
        
        generator = OasisProfileGenerator()
        profiles = generator.generate_profiles_from_entities(
            entities=filtered.entities,
            use_llm=use_llm
        )
        
        if platform == "reddit":
            profiles_data = [p.to_reddit_format() for p in profiles]
        elif platform == "twitter":
            profiles_data = [p.to_twitter_format() for p in profiles]
        else:
            profiles_data = [p.to_dict() for p in profiles]
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "entity_types": list(filtered.entity_types),
                "count": len(profiles_data),
                "profiles": profiles_data
            }
        })
        
    except Exception as e:
        logger.error(f"ç”ŸæˆProfileå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== æ¨¡æ‹Ÿè¿è¡ŒæŽ§åˆ¶æŽ¥å£ ==============

@simulation_bp.route('/start', methods=['POST'])
def start_simulation():
    """
    å¼€å§‹è¿è¡Œæ¨¡æ‹Ÿ

    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "simulation_id": "sim_xxxx",          // å¿…å¡«ï¼Œæ¨¡æ‹ŸID
            "platform": "parallel",                // å¯é€‰: twitter / reddit / parallel (é»˜è®¤)
            "max_rounds": 100,                     // å¯é€‰: æœ€å¤§æ¨¡æ‹Ÿè½®æ•°ï¼Œç”¨äºŽæˆªæ–­è¿‡é•¿çš„æ¨¡æ‹Ÿ
            "enable_graph_memory_update": false,   // å¯é€‰: æ˜¯å¦å°†Agentæ´»åŠ¨åŠ¨æ€æ›´æ–°åˆ°Zepå›¾è°±è®°å¿†
            "force": false                         // å¯é€‰: å¼ºåˆ¶é‡æ–°å¼€å§‹ï¼ˆä¼šåœæ­¢è¿è¡Œä¸­çš„æ¨¡æ‹Ÿå¹¶æ¸…ç†æ—¥å¿—ï¼‰
        }

    å…³äºŽ force å‚æ•°ï¼š
        - å¯ç”¨åŽï¼Œå¦‚æžœæ¨¡æ‹Ÿæ­£åœ¨è¿è¡Œæˆ–å·²å®Œæˆï¼Œä¼šå…ˆåœæ­¢å¹¶æ¸…ç†è¿è¡Œæ—¥å¿—
        - æ¸…ç†çš„å†…å®¹åŒ…æ‹¬ï¼šrun_state.json, actions.jsonl, simulation.log ç­‰
        - ä¸ä¼šæ¸…ç†é…ç½®æ–‡ä»¶ï¼ˆsimulation_config.jsonï¼‰å’Œ profile æ–‡ä»¶
        - é€‚ç”¨äºŽéœ€è¦é‡æ–°è¿è¡Œæ¨¡æ‹Ÿçš„åœºæ™¯

    å…³äºŽ enable_graph_memory_updateï¼š
        - å¯ç”¨åŽï¼Œæ¨¡æ‹Ÿä¸­æ‰€æœ‰Agentçš„æ´»åŠ¨ï¼ˆå‘å¸–ã€è¯„è®ºã€ç‚¹èµžç­‰ï¼‰éƒ½ä¼šå®žæ—¶æ›´æ–°åˆ°Zepå›¾è°±
        - è¿™å¯ä»¥è®©å›¾è°±"è®°ä½"æ¨¡æ‹Ÿè¿‡ç¨‹ï¼Œç”¨äºŽåŽç»­åˆ†æžæˆ–AIå¯¹è¯
        - éœ€è¦æ¨¡æ‹Ÿå…³è”çš„é¡¹ç›®æœ‰æœ‰æ•ˆçš„ graph_id
        - é‡‡ç”¨æ‰¹é‡æ›´æ–°æœºåˆ¶ï¼Œå‡å°‘APIè°ƒç”¨æ¬¡æ•°

    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "process_pid": 12345,
                "twitter_running": true,
                "reddit_running": true,
                "started_at": "2025-12-01T10:00:00",
                "graph_memory_update_enabled": true,  // æ˜¯å¦å¯ç”¨äº†å›¾è°±è®°å¿†æ›´æ–°
                "force_restarted": true               // æ˜¯å¦æ˜¯å¼ºåˆ¶é‡æ–°å¼€å§‹
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

        platform = data.get('platform', 'parallel')
        max_rounds = data.get('max_rounds')  # å¯é€‰ï¼šæœ€å¤§æ¨¡æ‹Ÿè½®æ•°
        enable_graph_memory_update = data.get('enable_graph_memory_update', False)  # å¯é€‰ï¼šæ˜¯å¦å¯ç”¨å›¾è°±è®°å¿†æ›´æ–°
        force = data.get('force', False)  # å¯é€‰ï¼šå¼ºåˆ¶é‡æ–°å¼€å§‹

        # éªŒè¯ max_rounds å‚æ•°
        if max_rounds is not None:
            try:
                max_rounds = int(max_rounds)
                if max_rounds <= 0:
                    return jsonify({
                        "success": False,
                        "error": t('api.maxRoundsPositive')
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": t('api.maxRoundsInvalid')
                }), 400

        if platform not in ['twitter', 'reddit', 'parallel']:
            return jsonify({
                "success": False,
                "error": t('api.invalidPlatform', platform=platform)
            }), 400

        # æ£€æŸ¥æ¨¡æ‹Ÿæ˜¯å¦å·²å‡†å¤‡å¥½
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404

        force_restarted = False
        
        # æ™ºèƒ½å¤„ç†çŠ¶æ€ï¼šå¦‚æžœå‡†å¤‡å·¥ä½œå·²å®Œæˆï¼Œå…è®¸é‡æ–°å¯åŠ¨
        if state.status != SimulationStatus.READY:
            # æ£€æŸ¥å‡†å¤‡å·¥ä½œæ˜¯å¦å·²å®Œæˆ
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)

            if is_prepared:
                # å‡†å¤‡å·¥ä½œå·²å®Œæˆï¼Œæ£€æŸ¥æ˜¯å¦æœ‰æ­£åœ¨è¿è¡Œçš„è¿›ç¨‹
                if state.status == SimulationStatus.RUNNING:
                    # æ£€æŸ¥æ¨¡æ‹Ÿè¿›ç¨‹æ˜¯å¦çœŸçš„åœ¨è¿è¡Œ
                    run_state = SimulationRunner.get_run_state(simulation_id)
                    if run_state and run_state.runner_status.value == "running":
                        # è¿›ç¨‹ç¡®å®žåœ¨è¿è¡Œ
                        if force:
                            # å¼ºåˆ¶æ¨¡å¼ï¼šåœæ­¢è¿è¡Œä¸­çš„æ¨¡æ‹Ÿ
                            logger.info(f"å¼ºåˆ¶æ¨¡å¼ï¼šåœæ­¢è¿è¡Œä¸­çš„æ¨¡æ‹Ÿ {simulation_id}")
                            try:
                                SimulationRunner.stop_simulation(simulation_id)
                            except Exception as e:
                                logger.warning(f"åœæ­¢æ¨¡æ‹Ÿæ—¶å‡ºçŽ°è­¦å‘Š: {str(e)}")
                        else:
                            return jsonify({
                                "success": False,
                                "error": t('api.simRunningForceHint')
                            }), 400

                # å¦‚æžœæ˜¯å¼ºåˆ¶æ¨¡å¼ï¼Œæ¸…ç†è¿è¡Œæ—¥å¿—
                if force:
                    logger.info(f"å¼ºåˆ¶æ¨¡å¼ï¼šæ¸…ç†æ¨¡æ‹Ÿæ—¥å¿— {simulation_id}")
                    cleanup_result = SimulationRunner.cleanup_simulation_logs(simulation_id)
                    if not cleanup_result.get("success"):
                        logger.warning(f"æ¸…ç†æ—¥å¿—æ—¶å‡ºçŽ°è­¦å‘Š: {cleanup_result.get('errors')}")
                    force_restarted = True

                # è¿›ç¨‹ä¸å­˜åœ¨æˆ–å·²ç»“æŸï¼Œé‡ç½®çŠ¶æ€ä¸º ready
                logger.info(f"æ¨¡æ‹Ÿ {simulation_id} å‡†å¤‡å·¥ä½œå·²å®Œæˆï¼Œé‡ç½®çŠ¶æ€ä¸º readyï¼ˆåŽŸçŠ¶æ€: {state.status.value}ï¼‰")
                state.status = SimulationStatus.READY
                manager._save_simulation_state(state)
            else:
                # å‡†å¤‡å·¥ä½œæœªå®Œæˆ
                return jsonify({
                    "success": False,
                    "error": t('api.simNotReady', status=state.status.value)
                }), 400
        
        # èŽ·å–å›¾è°±IDï¼ˆç”¨äºŽå›¾è°±è®°å¿†æ›´æ–°ï¼‰
        graph_id = None
        if enable_graph_memory_update:
            # ä»Žæ¨¡æ‹ŸçŠ¶æ€æˆ–é¡¹ç›®ä¸­èŽ·å– graph_id
            graph_id = state.graph_id
            if not graph_id:
                # å°è¯•ä»Žé¡¹ç›®ä¸­èŽ·å–
                project = ProjectManager.get_project(state.project_id)
                if project:
                    graph_id = project.graph_id
            
            if not graph_id:
                return jsonify({
                    "success": False,
                    "error": t('api.graphIdRequiredForMemory')
                }), 400
            
            logger.info(f"å¯ç”¨å›¾è°±è®°å¿†æ›´æ–°: simulation_id={simulation_id}, graph_id={graph_id}")
        
        # å¯åŠ¨æ¨¡æ‹Ÿ
        run_state = SimulationRunner.start_simulation(
            simulation_id=simulation_id,
            platform=platform,
            max_rounds=max_rounds,
            enable_graph_memory_update=enable_graph_memory_update,
            graph_id=graph_id
        )
        
        # æ›´æ–°æ¨¡æ‹ŸçŠ¶æ€
        state.status = SimulationStatus.RUNNING
        manager._save_simulation_state(state)
        
        response_data = run_state.to_dict()
        if max_rounds:
            response_data['max_rounds_applied'] = max_rounds
        response_data['graph_memory_update_enabled'] = enable_graph_memory_update
        response_data['force_restarted'] = force_restarted
        if enable_graph_memory_update:
            response_data['graph_id'] = graph_id
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"å¯åŠ¨æ¨¡æ‹Ÿå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/stop', methods=['POST'])
def stop_simulation():
    """
    åœæ­¢æ¨¡æ‹Ÿ
    
    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "simulation_id": "sim_xxxx"  // å¿…å¡«ï¼Œæ¨¡æ‹ŸID
        }
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "stopped",
                "completed_at": "2025-12-01T12:00:00"
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
        
        run_state = SimulationRunner.stop_simulation(simulation_id)
        
        # æ›´æ–°æ¨¡æ‹ŸçŠ¶æ€
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.PAUSED
            manager._save_simulation_state(state)
        
        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"åœæ­¢æ¨¡æ‹Ÿå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Pause/Resume/Checkpoint API ==============

from ..services.checkpoint_manager import CheckpointManager, CheckpointMetadata


@simulation_bp.route('/<simulation_id>/pause', methods=['POST'])
def pause_simulation(simulation_id: str):
    """
    Pause a running simulation and create a checkpoint.
    
    The simulation will finish its current round, save state, then halt.
    
    Request (JSON):
        {
            "description": "Optional checkpoint description"
        }
    
    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxx",
                "status": "paused",
                "checkpoint": { checkpoint metadata }
            }
        }
    """
    try:
        data = request.get_json() or {}
        description = data.get('description')
        
        # Get current run state
        run_state = SimulationRunner.get_run_state(simulation_id)
        if not run_state:
            return jsonify({
                "success": False,
                "error": f"Simulation not found: {simulation_id}"
            }), 404
        
        if run_state.runner_status != RunnerStatus.RUNNING:
            return jsonify({
                "success": False,
                "error": f"Simulation is not running (status: {run_state.runner_status.value})"
            }), 400
        
        # Load simulation config for checkpoint
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        config = {}
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        # Get agent personas
        agent_personas = config.get("agent_configs", [])
        
        # Create checkpoint before stopping
        checkpoint = CheckpointManager.create_checkpoint(
            simulation_id=simulation_id,
            round_number=run_state.current_round,
            simulated_hours=run_state.simulated_hours,
            agent_personas=agent_personas,
            config=config,
            graph_id=None,  # TODO: Get from config
            description=description or f"Pause at round {run_state.current_round}"
        )
        
        # Stop the simulation
        SimulationRunner.stop_simulation(simulation_id)
        
        # Update job queue status
        job = JobQueue.get_job_by_simulation(simulation_id)
        if job:
            JobQueue.update_job(
                job.job_id,
                status=JobStatus.PAUSED,
                checkpoint_round=run_state.current_round
            )
        
        # Update simulation manager state
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.PAUSED
            manager._save_simulation_state(state)
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "status": "paused",
                "checkpoint": checkpoint.to_dict()
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to pause simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/resume', methods=['POST'])
def resume_simulation(simulation_id: str):
    """
    Resume a paused simulation from a checkpoint.
    
    Request (JSON):
        {
            "checkpoint_id": "chkpt_r10_xxx",  // Optional, uses latest if not provided
            "max_rounds": null                  // Optional, override max rounds
        }
    
    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxx",
                "status": "running",
                "resumed_from_round": 10,
                "checkpoint_id": "chkpt_r10_xxx"
            }
        }
    """
    try:
        data = request.get_json() or {}
        checkpoint_id = data.get('checkpoint_id')
        max_rounds = data.get('max_rounds')
        
        # If no checkpoint specified, get the latest one
        if not checkpoint_id:
            checkpoints = CheckpointManager.list_checkpoints(simulation_id)
            if not checkpoints:
                return jsonify({
                    "success": False,
                    "error": "No checkpoints found for simulation"
                }), 404
            checkpoint_id = checkpoints[0].checkpoint_id
        
        # Load checkpoint
        checkpoint = CheckpointManager.load_checkpoint(simulation_id, checkpoint_id)
        if not checkpoint:
            return jsonify({
                "success": False,
                "error": f"Checkpoint not found: {checkpoint_id}"
            }), 404
        
        # Restore from checkpoint
        restore_result = CheckpointManager.restore_from_checkpoint(simulation_id, checkpoint_id)
        if not restore_result:
            return jsonify({
                "success": False,
                "error": "Failed to restore from checkpoint"
            }), 500
        
        # Start simulation from checkpoint round
        run_state = SimulationRunner.start_simulation(
            simulation_id=simulation_id,
            platform=checkpoint.config.get("platform", "parallel"),
            max_rounds=max_rounds,
            enable_graph_memory_update=False,
            graph_id=checkpoint.metadata.graph_id
        )
        
        # Update job queue
        job = JobQueue.get_job_by_simulation(simulation_id)
        if job:
            JobQueue.update_job(
                job.job_id,
                status=JobStatus.RUNNING,
                pid=run_state.process_pid,
                step_current=checkpoint.metadata.round_number
            )
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "status": "running",
                "resumed_from_round": checkpoint.metadata.round_number,
                "checkpoint_id": checkpoint_id,
                "pid": run_state.process_pid
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to resume simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/checkpoints', methods=['GET'])
def list_checkpoints(simulation_id: str):
    """
    List all checkpoints for a simulation.
    
    Returns:
        {
            "success": true,
            "data": {
                "checkpoints": [
                    { checkpoint metadata },
                    ...
                ]
            }
        }
    """
    try:
        checkpoints = CheckpointManager.list_checkpoints(simulation_id)
        
        return jsonify({
            "success": True,
            "data": {
                "checkpoints": [cp.to_dict() for cp in checkpoints]
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to list checkpoints: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>/checkpoints/<checkpoint_id>', methods=['GET'])
def get_checkpoint(simulation_id: str, checkpoint_id: str):
    """
    Get details of a specific checkpoint.
    
    Returns:
        {
            "success": true,
            "data": { checkpoint data }
        }
    """
    try:
        checkpoint = CheckpointManager.load_checkpoint(simulation_id, checkpoint_id)
        
        if not checkpoint:
            return jsonify({
                "success": False,
                "error": f"Checkpoint not found: {checkpoint_id}"
            }), 404
        
        return jsonify({
            "success": True,
            "data": checkpoint.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to get checkpoint: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>/checkpoints/<checkpoint_id>', methods=['DELETE'])
def delete_checkpoint(simulation_id: str, checkpoint_id: str):
    """
    Delete a checkpoint.
    
    Returns:
        {
            "success": true,
            "message": "Checkpoint deleted"
        }
    """
    try:
        deleted = CheckpointManager.delete_checkpoint(simulation_id, checkpoint_id)
        
        if not deleted:
            return jsonify({
                "success": False,
                "error": f"Checkpoint not found: {checkpoint_id}"
            }), 404
        
        return jsonify({
            "success": True,
            "message": "Checkpoint deleted"
        })
        
    except Exception as e:
        logger.error(f"Failed to delete checkpoint: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>/checkpoints', methods=['POST'])
def create_checkpoint(simulation_id: str):
    """
    Manually create a checkpoint for a running or paused simulation.
    
    Request (JSON):
        {
            "description": "Optional description"
        }
    
    Returns:
        {
            "success": true,
            "data": { checkpoint metadata }
        }
    """
    try:
        data = request.get_json() or {}
        description = data.get('description')
        
        # Get current state
        run_state = SimulationRunner.get_run_state(simulation_id)
        if not run_state:
            return jsonify({
                "success": False,
                "error": f"Simulation not found: {simulation_id}"
            }), 404
        
        # Load config
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        config = {}
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        agent_personas = config.get("agent_configs", [])
        
        # Create checkpoint
        checkpoint = CheckpointManager.create_checkpoint(
            simulation_id=simulation_id,
            round_number=run_state.current_round,
            simulated_hours=run_state.simulated_hours,
            agent_personas=agent_personas,
            config=config,
            description=description or f"Manual checkpoint at round {run_state.current_round}"
        )
        
        # Update job queue checkpoint round
        job = JobQueue.get_job_by_simulation(simulation_id)
        if job:
            JobQueue.update_job(
                job.job_id,
                checkpoint_round=run_state.current_round
            )
        
        return jsonify({
            "success": True,
            "data": checkpoint.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to create checkpoint: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Cost Estimation & Tracking API ==============

from ..services.cost_tracker import get_cost_tracker, estimate_simulation_cost


@simulation_bp.route('/cost/estimate', methods=['POST'])
def estimate_cost():
    """
    Estimate the cost of running a simulation before starting.
    
    Request (JSON):
        {
            "num_agents": 10,
            "num_rounds": 100,
            "model_name": "gpt-4o"  // Optional, uses config default
        }
    
    Returns:
        {
            "success": true,
            "data": {
                "num_agents": 10,
                "num_rounds": 100,
                "model_name": "gpt-4o",
                "estimated_input_tokens": 375000,
                "estimated_output_tokens": 125000,
                "estimated_total_tokens": 500000,
                "low_cost_usd": 0.875,
                "high_cost_usd": 1.625,
                "average_cost_usd": 1.25,
                "estimation_variance": 0.3
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        num_agents = data.get('num_agents')
        num_rounds = data.get('num_rounds')
        model_name = data.get('model_name')
        
        if not num_agents or not num_rounds:
            return jsonify({
                "success": False,
                "error": "num_agents and num_rounds are required"
            }), 400
        
        estimate = estimate_simulation_cost(
            num_agents=int(num_agents),
            num_rounds=int(num_rounds),
            model_name=model_name
        )
        
        return jsonify({
            "success": True,
            "data": estimate.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Cost estimation failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>/cost', methods=['GET'])
def get_simulation_cost(simulation_id: str):
    """
    Get current cost tracking for a running simulation.
    
    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxx",
                "status": "tracked",
                "usage": {
                    "input_tokens": 10000,
                    "output_tokens": 5000,
                    "total_tokens": 15000,
                    "estimated_cost_usd": 0.05,
                    "request_count": 50,
                    "limit_exceeded": false
                }
            }
        }
    """
    try:
        tracker = get_cost_tracker()
        summary = tracker.get_summary(simulation_id)
        
        return jsonify({
            "success": True,
            "data": summary
        })
        
    except Exception as e:
        logger.error(f"Failed to get cost: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== å®žæ—¶çŠ¶æ€ç›‘æŽ§æŽ¥å£ ==============

@simulation_bp.route('/<simulation_id>/run-status', methods=['GET'])
def get_run_status(simulation_id: str):
    """
    èŽ·å–æ¨¡æ‹Ÿè¿è¡Œå®žæ—¶çŠ¶æ€ï¼ˆç”¨äºŽå‰ç«¯è½®è¯¢ï¼‰
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                "total_rounds": 144,
                "progress_percent": 3.5,
                "simulated_hours": 2,
                "total_simulation_hours": 72,
                "twitter_running": true,
                "reddit_running": true,
                "twitter_actions_count": 150,
                "reddit_actions_count": 200,
                "total_actions_count": 350,
                "started_at": "2025-12-01T10:00:00",
                "updated_at": "2025-12-01T10:30:00"
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        
        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "current_round": 0,
                    "total_rounds": 0,
                    "progress_percent": 0,
                    "twitter_actions_count": 0,
                    "reddit_actions_count": 0,
                    "total_actions_count": 0,
                }
            })
        
        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–è¿è¡ŒçŠ¶æ€å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/run-status/detail', methods=['GET'])
def get_run_status_detail(simulation_id: str):
    """
    èŽ·å–æ¨¡æ‹Ÿè¿è¡Œè¯¦ç»†çŠ¶æ€ï¼ˆåŒ…å«æ‰€æœ‰åŠ¨ä½œï¼‰
    
    ç”¨äºŽå‰ç«¯å±•ç¤ºå®žæ—¶åŠ¨æ€
    
    Queryå‚æ•°ï¼š
        platform: è¿‡æ»¤å¹³å°ï¼ˆtwitter/redditï¼Œå¯é€‰ï¼‰
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                ...
                "all_actions": [
                    {
                        "round_num": 5,
                        "timestamp": "2025-12-01T10:30:00",
                        "platform": "twitter",
                        "agent_id": 3,
                        "agent_name": "Agent Name",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": "..."},
                        "result": null,
                        "success": true
                    },
                    ...
                ],
                "twitter_actions": [...],  # Twitter å¹³å°çš„æ‰€æœ‰åŠ¨ä½œ
                "reddit_actions": [...]    # Reddit å¹³å°çš„æ‰€æœ‰åŠ¨ä½œ
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        platform_filter = request.args.get('platform')
        
        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "all_actions": [],
                    "twitter_actions": [],
                    "reddit_actions": []
                }
            })
        
        # èŽ·å–å®Œæ•´çš„åŠ¨ä½œåˆ—è¡¨
        all_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter
        )
        
        # åˆ†å¹³å°èŽ·å–åŠ¨ä½œ
        twitter_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="twitter"
        ) if not platform_filter or platform_filter == "twitter" else []
        
        reddit_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="reddit"
        ) if not platform_filter or platform_filter == "reddit" else []
        
        # èŽ·å–å½“å‰è½®æ¬¡çš„åŠ¨ä½œï¼ˆrecent_actions åªå±•ç¤ºæœ€æ–°ä¸€è½®ï¼‰
        current_round = run_state.current_round
        recent_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter,
            round_num=current_round
        ) if current_round > 0 else []
        
        # èŽ·å–åŸºç¡€çŠ¶æ€ä¿¡æ¯
        result = run_state.to_dict()
        result["all_actions"] = [a.to_dict() for a in all_actions]
        result["twitter_actions"] = [a.to_dict() for a in twitter_actions]
        result["reddit_actions"] = [a.to_dict() for a in reddit_actions]
        result["rounds_count"] = len(run_state.rounds)
        # recent_actions åªå±•ç¤ºå½“å‰æœ€æ–°ä¸€è½®ä¸¤ä¸ªå¹³å°çš„å†…å®¹
        result["recent_actions"] = [a.to_dict() for a in recent_actions]
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–è¯¦ç»†çŠ¶æ€å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/actions', methods=['GET'])
def get_simulation_actions(simulation_id: str):
    """
    èŽ·å–æ¨¡æ‹Ÿä¸­çš„AgentåŠ¨ä½œåŽ†å²
    
    Queryå‚æ•°ï¼š
        limit: è¿”å›žæ•°é‡ï¼ˆé»˜è®¤100ï¼‰
        offset: åç§»é‡ï¼ˆé»˜è®¤0ï¼‰
        platform: è¿‡æ»¤å¹³å°ï¼ˆtwitter/redditï¼‰
        agent_id: è¿‡æ»¤Agent ID
        round_num: è¿‡æ»¤è½®æ¬¡
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "count": 100,
                "actions": [...]
            }
        }
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        platform = request.args.get('platform')
        agent_id = request.args.get('agent_id', type=int)
        round_num = request.args.get('round_num', type=int)
        
        actions = SimulationRunner.get_actions(
            simulation_id=simulation_id,
            limit=limit,
            offset=offset,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )
        
        return jsonify({
            "success": True,
            "data": {
                "count": len(actions),
                "actions": [a.to_dict() for a in actions]
            }
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–åŠ¨ä½œåŽ†å²å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/timeline', methods=['GET'])
def get_simulation_timeline(simulation_id: str):
    """
    èŽ·å–æ¨¡æ‹Ÿæ—¶é—´çº¿ï¼ˆæŒ‰è½®æ¬¡æ±‡æ€»ï¼‰
    
    ç”¨äºŽå‰ç«¯å±•ç¤ºè¿›åº¦æ¡å’Œæ—¶é—´çº¿è§†å›¾
    
    Queryå‚æ•°ï¼š
        start_round: èµ·å§‹è½®æ¬¡ï¼ˆé»˜è®¤0ï¼‰
        end_round: ç»“æŸè½®æ¬¡ï¼ˆé»˜è®¤å…¨éƒ¨ï¼‰
    
    è¿”å›žæ¯è½®çš„æ±‡æ€»ä¿¡æ¯
    """
    try:
        start_round = request.args.get('start_round', 0, type=int)
        end_round = request.args.get('end_round', type=int)
        
        timeline = SimulationRunner.get_timeline(
            simulation_id=simulation_id,
            start_round=start_round,
            end_round=end_round
        )
        
        return jsonify({
            "success": True,
            "data": {
                "rounds_count": len(timeline),
                "timeline": timeline
            }
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–æ—¶é—´çº¿å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/agent-stats', methods=['GET'])
def get_agent_stats(simulation_id: str):
    """
    èŽ·å–æ¯ä¸ªAgentçš„ç»Ÿè®¡ä¿¡æ¯
    
    ç”¨äºŽå‰ç«¯å±•ç¤ºAgentæ´»è·ƒåº¦æŽ’è¡Œã€åŠ¨ä½œåˆ†å¸ƒç­‰
    """
    try:
        stats = SimulationRunner.get_agent_stats(simulation_id)
        
        return jsonify({
            "success": True,
            "data": {
                "agents_count": len(stats),
                "stats": stats
            }
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–Agentç»Ÿè®¡å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== æ•°æ®åº“æŸ¥è¯¢æŽ¥å£ ==============

@simulation_bp.route('/<simulation_id>/posts', methods=['GET'])
def get_simulation_posts(simulation_id: str):
    """
    èŽ·å–æ¨¡æ‹Ÿä¸­çš„å¸–å­
    
    Queryå‚æ•°ï¼š
        platform: å¹³å°ç±»åž‹ï¼ˆtwitter/redditï¼‰
        limit: è¿”å›žæ•°é‡ï¼ˆé»˜è®¤50ï¼‰
        offset: åç§»é‡
    
    è¿”å›žå¸–å­åˆ—è¡¨ï¼ˆä»ŽSQLiteæ•°æ®åº“è¯»å–ï¼‰
    """
    try:
        platform = request.args.get('platform', 'reddit')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )
        
        db_file = f"{platform}_simulation.db"
        db_path = os.path.join(sim_dir, db_file)
        
        if not os.path.exists(db_path):
            return jsonify({
                "success": True,
                "data": {
                    "platform": platform,
                    "count": 0,
                    "posts": [],
                    "message": t('api.dbNotExist')
                }
            })
        
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM post 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            posts = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT COUNT(*) FROM post")
            total = cursor.fetchone()[0]
            
        except sqlite3.OperationalError:
            posts = []
            total = 0
        
        conn.close()
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "total": total,
                "count": len(posts),
                "posts": posts
            }
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–å¸–å­å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/comments', methods=['GET'])
def get_simulation_comments(simulation_id: str):
    """
    èŽ·å–æ¨¡æ‹Ÿä¸­çš„è¯„è®ºï¼ˆä»…Redditï¼‰
    
    Queryå‚æ•°ï¼š
        post_id: è¿‡æ»¤å¸–å­IDï¼ˆå¯é€‰ï¼‰
        limit: è¿”å›žæ•°é‡
        offset: åç§»é‡
    """
    try:
        post_id = request.args.get('post_id')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )
        
        db_path = os.path.join(sim_dir, "reddit_simulation.db")
        
        if not os.path.exists(db_path):
            return jsonify({
                "success": True,
                "data": {
                    "count": 0,
                    "comments": []
                }
            })
        
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            if post_id:
                cursor.execute("""
                    SELECT * FROM comment 
                    WHERE post_id = ?
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (post_id, limit, offset))
            else:
                cursor.execute("""
                    SELECT * FROM comment 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (limit, offset))
            
            comments = [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.OperationalError:
            comments = []
        
        conn.close()
        
        return jsonify({
            "success": True,
            "data": {
                "count": len(comments),
                "comments": comments
            }
        })
        
    except Exception as e:
        logger.error(f"èŽ·å–è¯„è®ºå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Interview é‡‡è®¿æŽ¥å£ ==============

@simulation_bp.route('/interview', methods=['POST'])
def interview_agent():
    """
    é‡‡è®¿å•ä¸ªAgent

    æ³¨æ„ï¼šæ­¤åŠŸèƒ½éœ€è¦æ¨¡æ‹ŸçŽ¯å¢ƒå¤„äºŽè¿è¡ŒçŠ¶æ€ï¼ˆå®Œæˆæ¨¡æ‹Ÿå¾ªçŽ¯åŽè¿›å…¥ç­‰å¾…å‘½ä»¤æ¨¡å¼ï¼‰

    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "simulation_id": "sim_xxxx",       // å¿…å¡«ï¼Œæ¨¡æ‹ŸID
            "agent_id": 0,                     // å¿…å¡«ï¼ŒAgent ID
            "prompt": "ä½ å¯¹è¿™ä»¶äº‹æœ‰ä»€ä¹ˆçœ‹æ³•ï¼Ÿ",  // å¿…å¡«ï¼Œé‡‡è®¿é—®é¢˜
            "platform": "twitter",             // å¯é€‰ï¼ŒæŒ‡å®šå¹³å°ï¼ˆtwitter/redditï¼‰
                                               // ä¸æŒ‡å®šæ—¶ï¼šåŒå¹³å°æ¨¡æ‹ŸåŒæ—¶é‡‡è®¿ä¸¤ä¸ªå¹³å°
            "timeout": 60                      // å¯é€‰ï¼Œè¶…æ—¶æ—¶é—´ï¼ˆç§’ï¼‰ï¼Œé»˜è®¤60
        }

    è¿”å›žï¼ˆä¸æŒ‡å®šplatformï¼ŒåŒå¹³å°æ¨¡å¼ï¼‰ï¼š
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "ä½ å¯¹è¿™ä»¶äº‹æœ‰ä»€ä¹ˆçœ‹æ³•ï¼Ÿ",
                "result": {
                    "agent_id": 0,
                    "prompt": "...",
                    "platforms": {
                        "twitter": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit": {"agent_id": 0, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }

    è¿”å›žï¼ˆæŒ‡å®šplatformï¼‰ï¼š
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "ä½ å¯¹è¿™ä»¶äº‹æœ‰ä»€ä¹ˆçœ‹æ³•ï¼Ÿ",
                "result": {
                    "agent_id": 0,
                    "response": "æˆ‘è®¤ä¸º...",
                    "platform": "twitter",
                    "timestamp": "2025-12-08T10:00:00"
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        agent_id = data.get('agent_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # å¯é€‰ï¼štwitter/reddit/None
        timeout = data.get('timeout', 60)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400
        
        if agent_id is None:
            return jsonify({
                "success": False,
                "error": t('api.requireAgentId')
            }), 400
        
        if not prompt:
            return jsonify({
                "success": False,
                "error": t('api.requirePrompt')
            }), 400
        
        # éªŒè¯platformå‚æ•°
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": t('api.invalidInterviewPlatform')
            }), 400
        
        # æ£€æŸ¥çŽ¯å¢ƒçŠ¶æ€
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": t('api.envNotRunning')
            }), 400
        
        # ä¼˜åŒ–promptï¼Œæ·»åŠ å‰ç¼€é¿å…Agentè°ƒç”¨å·¥å…·
        optimized_prompt = optimize_interview_prompt(prompt)
        
        result = SimulationRunner.interview_agent(
            simulation_id=simulation_id,
            agent_id=agent_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": t('api.interviewTimeout', error=str(e))
        }), 504
        
    except Exception as e:
        logger.error(f"Interviewå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/batch', methods=['POST'])
def interview_agents_batch():
    """
    æ‰¹é‡é‡‡è®¿å¤šä¸ªAgent

    æ³¨æ„ï¼šæ­¤åŠŸèƒ½éœ€è¦æ¨¡æ‹ŸçŽ¯å¢ƒå¤„äºŽè¿è¡ŒçŠ¶æ€

    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "simulation_id": "sim_xxxx",       // å¿…å¡«ï¼Œæ¨¡æ‹ŸID
            "interviews": [                    // å¿…å¡«ï¼Œé‡‡è®¿åˆ—è¡¨
                {
                    "agent_id": 0,
                    "prompt": "ä½ å¯¹Aæœ‰ä»€ä¹ˆçœ‹æ³•ï¼Ÿ",
                    "platform": "twitter"      // å¯é€‰ï¼ŒæŒ‡å®šè¯¥Agentçš„é‡‡è®¿å¹³å°
                },
                {
                    "agent_id": 1,
                    "prompt": "ä½ å¯¹Bæœ‰ä»€ä¹ˆçœ‹æ³•ï¼Ÿ"  // ä¸æŒ‡å®šplatformåˆ™ä½¿ç”¨é»˜è®¤å€¼
                }
            ],
            "platform": "reddit",              // å¯é€‰ï¼Œé»˜è®¤å¹³å°ï¼ˆè¢«æ¯é¡¹çš„platformè¦†ç›–ï¼‰
                                               // ä¸æŒ‡å®šæ—¶ï¼šåŒå¹³å°æ¨¡æ‹Ÿæ¯ä¸ªAgentåŒæ—¶é‡‡è®¿ä¸¤ä¸ªå¹³å°
            "timeout": 120                     // å¯é€‰ï¼Œè¶…æ—¶æ—¶é—´ï¼ˆç§’ï¼‰ï¼Œé»˜è®¤120
        }

    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "interviews_count": 2,
                "result": {
                    "interviews_count": 4,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        "twitter_1": {"agent_id": 1, "response": "...", "platform": "twitter"},
                        "reddit_1": {"agent_id": 1, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        interviews = data.get('interviews')
        platform = data.get('platform')  # å¯é€‰ï¼štwitter/reddit/None
        timeout = data.get('timeout', 120)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        if not interviews or not isinstance(interviews, list):
            return jsonify({
                "success": False,
                "error": t('api.requireInterviews')
            }), 400

        # éªŒè¯platformå‚æ•°
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": t('api.invalidInterviewPlatform')
            }), 400

        # éªŒè¯æ¯ä¸ªé‡‡è®¿é¡¹
        for i, interview in enumerate(interviews):
            if 'agent_id' not in interview:
                return jsonify({
                    "success": False,
                    "error": t('api.interviewListMissingAgentId', index=i+1)
                }), 400
            if 'prompt' not in interview:
                return jsonify({
                    "success": False,
                    "error": t('api.interviewListMissingPrompt', index=i+1)
                }), 400
            # éªŒè¯æ¯é¡¹çš„platformï¼ˆå¦‚æžœæœ‰ï¼‰
            item_platform = interview.get('platform')
            if item_platform and item_platform not in ("twitter", "reddit"):
                return jsonify({
                    "success": False,
                    "error": t('api.interviewListInvalidPlatform', index=i+1)
                }), 400

        # æ£€æŸ¥çŽ¯å¢ƒçŠ¶æ€
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": t('api.envNotRunning')
            }), 400

        # ä¼˜åŒ–æ¯ä¸ªé‡‡è®¿é¡¹çš„promptï¼Œæ·»åŠ å‰ç¼€é¿å…Agentè°ƒç”¨å·¥å…·
        optimized_interviews = []
        for interview in interviews:
            optimized_interview = interview.copy()
            optimized_interview['prompt'] = optimize_interview_prompt(interview.get('prompt', ''))
            optimized_interviews.append(optimized_interview)

        result = SimulationRunner.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=optimized_interviews,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": t('api.batchInterviewTimeout', error=str(e))
        }), 504

    except Exception as e:
        logger.error(f"æ‰¹é‡Interviewå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/all', methods=['POST'])
def interview_all_agents():
    """
    å…¨å±€é‡‡è®¿ - ä½¿ç”¨ç›¸åŒé—®é¢˜é‡‡è®¿æ‰€æœ‰Agent

    æ³¨æ„ï¼šæ­¤åŠŸèƒ½éœ€è¦æ¨¡æ‹ŸçŽ¯å¢ƒå¤„äºŽè¿è¡ŒçŠ¶æ€

    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "simulation_id": "sim_xxxx",            // å¿…å¡«ï¼Œæ¨¡æ‹ŸID
            "prompt": "ä½ å¯¹è¿™ä»¶äº‹æ•´ä½“æœ‰ä»€ä¹ˆçœ‹æ³•ï¼Ÿ",  // å¿…å¡«ï¼Œé‡‡è®¿é—®é¢˜ï¼ˆæ‰€æœ‰Agentä½¿ç”¨ç›¸åŒé—®é¢˜ï¼‰
            "platform": "reddit",                   // å¯é€‰ï¼ŒæŒ‡å®šå¹³å°ï¼ˆtwitter/redditï¼‰
                                                    // ä¸æŒ‡å®šæ—¶ï¼šåŒå¹³å°æ¨¡æ‹Ÿæ¯ä¸ªAgentåŒæ—¶é‡‡è®¿ä¸¤ä¸ªå¹³å°
            "timeout": 180                          // å¯é€‰ï¼Œè¶…æ—¶æ—¶é—´ï¼ˆç§’ï¼‰ï¼Œé»˜è®¤180
        }

    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "interviews_count": 50,
                "result": {
                    "interviews_count": 100,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        ...
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # å¯é€‰ï¼štwitter/reddit/None
        timeout = data.get('timeout', 180)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        if not prompt:
            return jsonify({
                "success": False,
                "error": t('api.requirePrompt')
            }), 400

        # éªŒè¯platformå‚æ•°
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": t('api.invalidInterviewPlatform')
            }), 400

        # æ£€æŸ¥çŽ¯å¢ƒçŠ¶æ€
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": t('api.envNotRunning')
            }), 400

        # ä¼˜åŒ–promptï¼Œæ·»åŠ å‰ç¼€é¿å…Agentè°ƒç”¨å·¥å…·
        optimized_prompt = optimize_interview_prompt(prompt)

        result = SimulationRunner.interview_all_agents(
            simulation_id=simulation_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": t('api.globalInterviewTimeout', error=str(e))
        }), 504

    except Exception as e:
        logger.error(f"å…¨å±€Interviewå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/history', methods=['POST'])
def get_interview_history():
    """
    èŽ·å–InterviewåŽ†å²è®°å½•

    ä»Žæ¨¡æ‹Ÿæ•°æ®åº“ä¸­è¯»å–æ‰€æœ‰Interviewè®°å½•

    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "simulation_id": "sim_xxxx",  // å¿…å¡«ï¼Œæ¨¡æ‹ŸID
            "platform": "reddit",          // å¯é€‰ï¼Œå¹³å°ç±»åž‹ï¼ˆreddit/twitterï¼‰
                                           // ä¸æŒ‡å®šåˆ™è¿”å›žä¸¤ä¸ªå¹³å°çš„æ‰€æœ‰åŽ†å²
            "agent_id": 0,                 // å¯é€‰ï¼ŒåªèŽ·å–è¯¥Agentçš„é‡‡è®¿åŽ†å²
            "limit": 100                   // å¯é€‰ï¼Œè¿”å›žæ•°é‡ï¼Œé»˜è®¤100
        }

    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "count": 10,
                "history": [
                    {
                        "agent_id": 0,
                        "response": "æˆ‘è®¤ä¸º...",
                        "prompt": "ä½ å¯¹è¿™ä»¶äº‹æœ‰ä»€ä¹ˆçœ‹æ³•ï¼Ÿ",
                        "timestamp": "2025-12-08T10:00:00",
                        "platform": "reddit"
                    },
                    ...
                ]
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        platform = data.get('platform')  # ä¸æŒ‡å®šåˆ™è¿”å›žä¸¤ä¸ªå¹³å°çš„åŽ†å²
        agent_id = data.get('agent_id')
        limit = data.get('limit', 100)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        history = SimulationRunner.get_interview_history(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            limit=limit
        )

        return jsonify({
            "success": True,
            "data": {
                "count": len(history),
                "history": history
            }
        })

    except Exception as e:
        logger.error(f"èŽ·å–InterviewåŽ†å²å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/env-status', methods=['POST'])
def get_env_status():
    """
    èŽ·å–æ¨¡æ‹ŸçŽ¯å¢ƒçŠ¶æ€

    æ£€æŸ¥æ¨¡æ‹ŸçŽ¯å¢ƒæ˜¯å¦å­˜æ´»ï¼ˆå¯ä»¥æŽ¥æ”¶Interviewå‘½ä»¤ï¼‰

    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "simulation_id": "sim_xxxx"  // å¿…å¡«ï¼Œæ¨¡æ‹ŸID
        }

    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "env_alive": true,
                "twitter_available": true,
                "reddit_available": true,
                "message": "çŽ¯å¢ƒæ­£åœ¨è¿è¡Œï¼Œå¯ä»¥æŽ¥æ”¶Interviewå‘½ä»¤"
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

        env_alive = SimulationRunner.check_env_alive(simulation_id)
        
        # èŽ·å–æ›´è¯¦ç»†çš„çŠ¶æ€ä¿¡æ¯
        env_status = SimulationRunner.get_env_status_detail(simulation_id)

        if env_alive:
            message = t('api.envRunning')
        else:
            message = t('api.envNotRunningShort')

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "env_alive": env_alive,
                "twitter_available": env_status.get("twitter_available", False),
                "reddit_available": env_status.get("reddit_available", False),
                "message": message
            }
        })

    except Exception as e:
        logger.error(f"èŽ·å–çŽ¯å¢ƒçŠ¶æ€å¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/close-env', methods=['POST'])
def close_simulation_env():
    """
    å…³é—­æ¨¡æ‹ŸçŽ¯å¢ƒ
    
    å‘æ¨¡æ‹Ÿå‘é€å…³é—­çŽ¯å¢ƒå‘½ä»¤ï¼Œä½¿å…¶ä¼˜é›…é€€å‡ºç­‰å¾…å‘½ä»¤æ¨¡å¼ã€‚
    
    æ³¨æ„ï¼šè¿™ä¸åŒäºŽ /stop æŽ¥å£ï¼Œ/stop ä¼šå¼ºåˆ¶ç»ˆæ­¢è¿›ç¨‹ï¼Œ
    è€Œæ­¤æŽ¥å£ä¼šè®©æ¨¡æ‹Ÿä¼˜é›…åœ°å…³é—­çŽ¯å¢ƒå¹¶é€€å‡ºã€‚
    
    è¯·æ±‚ï¼ˆJSONï¼‰ï¼š
        {
            "simulation_id": "sim_xxxx",  // å¿…å¡«ï¼Œæ¨¡æ‹ŸID
            "timeout": 30                  // å¯é€‰ï¼Œè¶…æ—¶æ—¶é—´ï¼ˆç§’ï¼‰ï¼Œé»˜è®¤30
        }
    
    è¿”å›žï¼š
        {
            "success": true,
            "data": {
                "message": "çŽ¯å¢ƒå…³é—­å‘½ä»¤å·²å‘é€",
                "result": {...},
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        timeout = data.get('timeout', 30)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400
        
        result = SimulationRunner.close_simulation_env(
            simulation_id=simulation_id,
            timeout=timeout
        )
        
        # æ›´æ–°æ¨¡æ‹ŸçŠ¶æ€
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.COMPLETED
            manager._save_simulation_state(state)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"å…³é—­çŽ¯å¢ƒå¤±è´¥: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Job Queue API (Subprocess Resilience) ==============

from ..services.job_queue import JobQueue, JobStatus, JobRecord


@simulation_bp.route('/jobs', methods=['GET'])
def list_jobs():
    """
    List all simulation jobs with optional filtering.
    
    Query Parameters:
        limit: Maximum number of jobs (default 100)
        offset: Pagination offset (default 0)
        status: Filter by status (pending, running, completed, failed, interrupted)
    
    Returns:
        {
            "success": true,
            "data": {
                "jobs": [...],
                "total": 50
            }
        }
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        status_filter = request.args.get('status')
        
        status_list = None
        if status_filter:
            try:
                status_list = [JobStatus(status_filter)]
            except ValueError:
                pass
        
        jobs = JobQueue.get_all_jobs(limit=limit, offset=offset, status_filter=status_list)
        
        return jsonify({
            "success": True,
            "data": {
                "jobs": [job.to_dict() for job in jobs],
                "count": len(jobs)
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to list jobs: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job(job_id: str):
    """
    Get a specific job by ID.
    
    Returns:
        {
            "success": true,
            "data": { job details }
        }
    """
    try:
        job = JobQueue.get_job(job_id)
        
        if not job:
            return jsonify({
                "success": False,
                "error": f"Job not found: {job_id}"
            }), 404
        
        return jsonify({
            "success": True,
            "data": job.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/jobs/interrupted', methods=['GET'])
def get_interrupted_jobs():
    """
    Get all jobs that were interrupted and can be restarted.
    
    Returns:
        {
            "success": true,
            "data": {
                "interrupted_jobs": [...],
                "restartable_jobs": [...]
            }
        }
    """
    try:
        # Detect any newly interrupted jobs
        interrupted = JobQueue.detect_interrupted_jobs()
        
        # Get all restartable jobs
        restartable = JobQueue.get_restartable_jobs()
        
        return jsonify({
            "success": True,
            "data": {
                "interrupted_jobs": [job.to_dict() for job in interrupted],
                "restartable_jobs": [job.to_dict() for job in restartable]
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get interrupted jobs: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/jobs/<job_id>/restart', methods=['POST'])
def restart_job(job_id: str):
    """
    Restart an interrupted or failed job from the last checkpoint.
    
    Request (JSON):
        {
            "from_checkpoint": true,  // Optional, default true - resume from checkpoint
            "max_rounds": null        // Optional, override max rounds
        }
    
    Returns:
        {
            "success": true,
            "data": {
                "job_id": "...",
                "simulation_id": "...",
                "resumed_from_round": 5,
                "status": "running"
            }
        }
    """
    try:
        data = request.get_json() or {}
        from_checkpoint = data.get('from_checkpoint', True)
        max_rounds = data.get('max_rounds')
        
        # Get the job
        job = JobQueue.get_job(job_id)
        if not job:
            return jsonify({
                "success": False,
                "error": f"Job not found: {job_id}"
            }), 404
        
        # Check if job can be restarted
        if job.status not in [JobStatus.INTERRUPTED, JobStatus.FAILED, JobStatus.PAUSED, JobStatus.STOPPED]:
            return jsonify({
                "success": False,
                "error": f"Job cannot be restarted (status: {job.status.value})"
            }), 400
        
        # Determine starting round
        start_round = job.checkpoint_round if from_checkpoint else 0
        
        # Update job status to pending
        JobQueue.update_job(
            job_id,
            status=JobStatus.PENDING,
            error_msg=None
        )
        
        # Start the simulation from the checkpoint
        # This reuses the existing simulation config
        try:
            import json as json_module
            config = json_module.loads(job.config_json) if job.config_json else {}
            
            state = SimulationRunner.start_simulation(
                simulation_id=job.simulation_id,
                platform=job.platform,
                max_rounds=max_rounds,
                enable_graph_memory_update=bool(job.graph_id),
                graph_id=job.graph_id
            )
            
            # Update job with new PID
            JobQueue.update_job(
                job_id,
                status=JobStatus.RUNNING,
                pid=state.process_pid,
                step_current=start_round
            )
            
            return jsonify({
                "success": True,
                "data": {
                    "job_id": job_id,
                    "simulation_id": job.simulation_id,
                    "resumed_from_round": start_round,
                    "status": "running",
                    "pid": state.process_pid
                }
            })
            
        except Exception as e:
            JobQueue.update_job(
                job_id,
                status=JobStatus.FAILED,
                error_msg=str(e)
            )
            raise
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Failed to restart job {job_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id: str):
    """
    Delete a job record.
    
    Note: This only deletes the job tracking record, not the simulation data.
    
    Returns:
        {
            "success": true,
            "message": "Job deleted"
        }
    """
    try:
        deleted = JobQueue.delete_job(job_id)
        
        if not deleted:
            return jsonify({
                "success": False,
                "error": f"Job not found: {job_id}"
            }), 404
        
        return jsonify({
            "success": True,
            "message": "Job deleted"
        })
        
    except Exception as e:
        logger.error(f"Failed to delete job {job_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

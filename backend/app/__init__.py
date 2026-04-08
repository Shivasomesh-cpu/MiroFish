"""
Posiedon Backend - Flaskåº”ç”¨å·¥åŽ‚
"""

import os
import warnings

# æŠ‘åˆ¶ multiprocessing resource_tracker çš„è­¦å‘Šï¼ˆæ¥è‡ªç¬¬ä¸‰æ–¹åº“å¦‚ transformersï¼‰
# éœ€è¦åœ¨æ‰€æœ‰å…¶ä»–å¯¼å…¥ä¹‹å‰è®¾ç½®
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flaskåº”ç”¨å·¥åŽ‚å‡½æ•°"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # è®¾ç½®JSONç¼–ç ï¼šç¡®ä¿ä¸­æ–‡ç›´æŽ¥æ˜¾ç¤ºï¼ˆè€Œä¸æ˜¯ \uXXXX æ ¼å¼ï¼‰
    # Flask >= 2.3 ä½¿ç”¨ app.json.ensure_asciiï¼Œæ—§ç‰ˆæœ¬ä½¿ç”¨ JSON_AS_ASCII é…ç½®
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # è®¾ç½®æ—¥å¿—
    logger = setup_logger('posiedon')
    
    # åªåœ¨ reloader å­è¿›ç¨‹ä¸­æ‰“å°å¯åŠ¨ä¿¡æ¯ï¼ˆé¿å… debug æ¨¡å¼ä¸‹æ‰“å°ä¸¤æ¬¡ï¼‰
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("Posiedon Backend å¯åŠ¨ä¸­...")
        logger.info("=" * 50)
    
    # å¯ç”¨CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # æ³¨å†Œæ¨¡æ‹Ÿè¿›ç¨‹æ¸…ç†å‡½æ•°ï¼ˆç¡®ä¿æœåŠ¡å™¨å…³é—­æ—¶ç»ˆæ­¢æ‰€æœ‰æ¨¡æ‹Ÿè¿›ç¨‹ï¼‰
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("å·²æ³¨å†Œæ¨¡æ‹Ÿè¿›ç¨‹æ¸…ç†å‡½æ•°")
    
    # Check for interrupted jobs on startup
    from .services.job_queue import check_and_recover_interrupted_jobs
    if should_log_startup:
        interrupted = check_and_recover_interrupted_jobs()
        if interrupted:
            logger.warning(f"Found {len(interrupted)} interrupted jobs - "
                          "use /api/simulation/jobs/interrupted to view and restart them")
    
    # è¯·æ±‚æ—¥å¿—ä¸­é—´ä»¶
    @app.before_request
    def log_request():
        logger = get_logger('posiedon.request')
        logger.debug(f"è¯·æ±‚: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"è¯·æ±‚ä½“: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('posiedon.request')
        logger.debug(f"å“åº”: {response.status_code}")
        return response
    
    # æ³¨å†Œè“å›¾
    from .api import graph_bp, simulation_bp, report_bp
    from .api.stream import stream_bp, SimulationStatePoller
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(stream_bp, url_prefix='/api/stream')
    
    # Start SSE state poller for real-time updates
    if should_log_startup:
        SimulationStatePoller.start()
        logger.info("SSE state poller started")
    
    # å¥åº·æ£€æŸ¥
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'Posiedon Backend'}
    
    if should_log_startup:
        logger.info("Posiedon Backend å¯åŠ¨å®Œæˆ")
    
    return app


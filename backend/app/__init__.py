"""Posiedon backend Flask application factory."""

import os
import warnings

# Silence noisy multiprocessing resource tracker warnings from third-party libraries.
# This must be configured before other heavy imports.
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Keep JSON responses human-readable instead of escaping non-ASCII characters.
    if hasattr(app, "json") and hasattr(app.json, "ensure_ascii"):
        app.json.ensure_ascii = False

    logger = setup_logger("posiedon")

    # Avoid duplicate startup logs when the dev reloader is enabled.
    is_reloader_process = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    debug_mode = app.config.get("DEBUG", False)
    should_log_startup = not debug_mode or is_reloader_process

    if should_log_startup:
        logger.info("=" * 50)
        logger.info("Starting Posiedon Backend...")
        logger.info("=" * 50)

    # Enable CORS for API routes.
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register simulation cleanup so background workers are stopped on shutdown.
    from .services.simulation_runner import SimulationRunner

    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Registered simulation cleanup hooks")

    # Check for interrupted jobs on startup.
    from .services.job_queue import check_and_recover_interrupted_jobs

    if should_log_startup:
        interrupted = check_and_recover_interrupted_jobs()
        if interrupted:
            logger.warning(
                f"Found {len(interrupted)} interrupted jobs - "
                "use /api/simulation/jobs/interrupted to view and restart them"
            )

    # Request and response logging middleware.
    @app.before_request
    def log_request():
        request_logger = get_logger("posiedon.request")
        request_logger.debug(f"Request: {request.method} {request.path}")
        if request.content_type and "json" in request.content_type:
            request_logger.debug(f"Payload: {request.get_json(silent=True)}")

    @app.after_request
    def log_response(response):
        request_logger = get_logger("posiedon.request")
        request_logger.debug(f"Response: {response.status_code}")
        return response

    # Register blueprints.
    from .api import graph_bp, simulation_bp, report_bp
    from .api.stream import stream_bp, SimulationStatePoller

    app.register_blueprint(graph_bp, url_prefix="/api/graph")
    app.register_blueprint(simulation_bp, url_prefix="/api/simulation")
    app.register_blueprint(report_bp, url_prefix="/api/report")
    app.register_blueprint(stream_bp, url_prefix="/api/stream")

    if should_log_startup:
        SimulationStatePoller.start()
        logger.info("SSE state poller started")

    @app.route("/health")
    def health():
        return {"status": "ok", "service": "Posiedon Backend"}

    if should_log_startup:
        logger.info("Posiedon Backend started")

    return app

"""
Server-Sent Events (SSE) Stream API

Provides real-time updates for simulation progress using Server-Sent Events.
This replaces polling-based updates with push-based streaming for better
performance and user experience.

Events:
- step_complete: Fired after each simulation round completes
- simulation_done: Fired when simulation finishes successfully
- simulation_error: Fired on simulation failure
- heartbeat: Periodic keepalive to prevent connection timeout
"""

import json
import time
import threading
from datetime import datetime
from typing import Dict, Any, Generator, Optional
from queue import Queue, Empty
from flask import Blueprint, Response, request

from ..config import Config
from ..utils.logger import get_logger
from ..services.simulation_runner import SimulationRunner, RunnerStatus

logger = get_logger('posiedon.api.stream')

stream_bp = Blueprint('stream', __name__)


class SimulationEventEmitter:
    """
    Manages event streams for simulation updates.
    
    Each simulation can have multiple subscribers (browser tabs).
    Events are pushed to all subscribers when the simulation state changes.
    """
    
    # Active subscriptions: simulation_id -> list of (queue, client_id)
    _subscriptions: Dict[str, list] = {}
    _lock = threading.Lock()
    
    # Heartbeat interval in seconds
    HEARTBEAT_INTERVAL = 15
    
    @classmethod
    def subscribe(cls, simulation_id: str, client_id: str) -> Queue:
        """
        Subscribe to events for a simulation.
        
        Args:
            simulation_id: The simulation to subscribe to
            client_id: Unique client identifier
            
        Returns:
            Queue that will receive events
        """
        queue = Queue()
        
        with cls._lock:
            if simulation_id not in cls._subscriptions:
                cls._subscriptions[simulation_id] = []
            cls._subscriptions[simulation_id].append((queue, client_id))
            
        logger.debug(f"Client {client_id} subscribed to simulation {simulation_id}")
        return queue
    
    @classmethod
    def unsubscribe(cls, simulation_id: str, client_id: str):
        """
        Unsubscribe from simulation events.
        
        Args:
            simulation_id: The simulation ID
            client_id: The client to unsubscribe
        """
        with cls._lock:
            if simulation_id in cls._subscriptions:
                cls._subscriptions[simulation_id] = [
                    (q, cid) for q, cid in cls._subscriptions[simulation_id]
                    if cid != client_id
                ]
                if not cls._subscriptions[simulation_id]:
                    del cls._subscriptions[simulation_id]
                    
        logger.debug(f"Client {client_id} unsubscribed from simulation {simulation_id}")
    
    @classmethod
    def emit(cls, simulation_id: str, event_type: str, data: Dict[str, Any]):
        """
        Emit an event to all subscribers of a simulation.
        
        Args:
            simulation_id: The simulation ID
            event_type: Event type (step_complete, simulation_done, etc.)
            data: Event payload
        """
        with cls._lock:
            if simulation_id not in cls._subscriptions:
                return
            
            event = {
                "event": event_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            
            for queue, client_id in cls._subscriptions[simulation_id]:
                try:
                    queue.put_nowait(event)
                except Exception as e:
                    logger.warning(f"Failed to emit event to client {client_id}: {e}")
    
    @classmethod
    def emit_step_complete(
        cls,
        simulation_id: str,
        current_round: int,
        total_rounds: int,
        last_action_summary: Optional[Dict[str, Any]] = None
    ):
        """Emit a step_complete event."""
        cls.emit(simulation_id, "step_complete", {
            "current_round": current_round,
            "total_rounds": total_rounds,
            "progress_percent": round(current_round / max(total_rounds, 1) * 100, 1),
            "last_action": last_action_summary
        })
    
    @classmethod
    def emit_simulation_done(cls, simulation_id: str, summary: Dict[str, Any]):
        """Emit a simulation_done event."""
        cls.emit(simulation_id, "simulation_done", summary)
    
    @classmethod
    def emit_simulation_error(cls, simulation_id: str, error: str):
        """Emit a simulation_error event."""
        cls.emit(simulation_id, "simulation_error", {"error": error})
    
    @classmethod
    def get_subscriber_count(cls, simulation_id: str) -> int:
        """Get the number of active subscribers for a simulation."""
        with cls._lock:
            return len(cls._subscriptions.get(simulation_id, []))


def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """
    Format an event as Server-Sent Events message.
    
    SSE format:
    event: <event_type>
    data: <json_data>
    
    (blank line to end message)
    """
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def generate_event_stream(
    simulation_id: str,
    client_id: str
) -> Generator[str, None, None]:
    """
    Generate SSE event stream for a simulation.
    
    This is a generator that yields SSE-formatted events.
    It handles:
    - Initial state push
    - Event queue monitoring
    - Heartbeat keepalives
    - Connection cleanup
    """
    queue = SimulationEventEmitter.subscribe(simulation_id, client_id)
    last_heartbeat = time.time()
    
    try:
        # Send initial state
        state = SimulationRunner.get_run_state(simulation_id)
        if state:
            yield format_sse_event("init", state.to_dict())
        
        while True:
            try:
                # Check for events (with timeout for heartbeat)
                event = queue.get(timeout=SimulationEventEmitter.HEARTBEAT_INTERVAL / 2)
                yield format_sse_event(event["event"], event["data"])
                
                # Check if simulation is complete
                if event["event"] in ["simulation_done", "simulation_error"]:
                    break
                    
            except Empty:
                # No event, check if we need heartbeat
                current_time = time.time()
                if current_time - last_heartbeat >= SimulationEventEmitter.HEARTBEAT_INTERVAL:
                    yield format_sse_event("heartbeat", {"timestamp": datetime.now().isoformat()})
                    last_heartbeat = current_time
                
                # Also poll simulation state for updates
                state = SimulationRunner.get_run_state(simulation_id)
                if state:
                    # Check if simulation finished while we were waiting
                    if state.runner_status == RunnerStatus.COMPLETED:
                        yield format_sse_event("simulation_done", state.to_dict())
                        break
                    elif state.runner_status == RunnerStatus.FAILED:
                        yield format_sse_event("simulation_error", {
                            "error": state.error or "Unknown error"
                        })
                        break
                    elif state.runner_status == RunnerStatus.STOPPED:
                        yield format_sse_event("simulation_stopped", state.to_dict())
                        break
                    
                    # Emit state update
                    yield format_sse_event("state_update", state.to_dict())
                    
    except GeneratorExit:
        pass
    finally:
        SimulationEventEmitter.unsubscribe(simulation_id, client_id)


@stream_bp.route('/<simulation_id>', methods=['GET'])
def stream_simulation(simulation_id: str):
    """
    Server-Sent Events stream for simulation updates.
    
    Connect to this endpoint to receive real-time updates for a simulation.
    
    Query Parameters:
        client_id: Optional client identifier (auto-generated if not provided)
    
    Events:
        - init: Initial simulation state
        - state_update: Periodic state updates
        - step_complete: After each round completes
        - simulation_done: Simulation finished successfully
        - simulation_error: Simulation failed
        - simulation_stopped: Simulation was stopped by user
        - heartbeat: Keepalive ping
    
    Example client (JavaScript):
        const source = new EventSource('/api/stream/sim_xxx');
        source.addEventListener('step_complete', (e) => {
            const data = JSON.parse(e.data);
            console.log(`Round ${data.current_round}/${data.total_rounds}`);
        });
    """
    # Validate simulation exists
    state = SimulationRunner.get_run_state(simulation_id)
    if not state:
        return {"success": False, "error": f"Simulation not found: {simulation_id}"}, 404
    
    # Generate client ID
    client_id = request.args.get('client_id', f"client_{int(time.time() * 1000)}")
    
    logger.info(f"SSE connection: simulation={simulation_id}, client={client_id}")
    
    return Response(
        generate_event_stream(simulation_id, client_id),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
            'Access-Control-Allow-Origin': '*'
        }
    )


@stream_bp.route('/<simulation_id>/subscribers', methods=['GET'])
def get_subscribers(simulation_id: str):
    """
    Get the number of active SSE subscribers for a simulation.
    
    Returns:
        {
            "simulation_id": "sim_xxx",
            "subscriber_count": 3
        }
    """
    count = SimulationEventEmitter.get_subscriber_count(simulation_id)
    return {
        "simulation_id": simulation_id,
        "subscriber_count": count
    }


# Background task to poll simulation state and emit events
# This bridges the gap between the file-based monitoring in SimulationRunner
# and the event-based SSE system

class SimulationStatePoller:
    """
    Polls simulation states and emits events to SSE subscribers.
    
    This runs in a background thread and monitors active simulations,
    emitting events when state changes are detected.
    """
    
    _polling_thread: Optional[threading.Thread] = None
    _stop_event = threading.Event()
    _last_states: Dict[str, Dict[str, Any]] = {}
    
    POLL_INTERVAL = 2  # seconds
    
    @classmethod
    def start(cls):
        """Start the background polling thread."""
        if cls._polling_thread and cls._polling_thread.is_alive():
            return
        
        cls._stop_event.clear()
        cls._polling_thread = threading.Thread(
            target=cls._poll_loop,
            daemon=True
        )
        cls._polling_thread.start()
        logger.info("SimulationStatePoller started")
    
    @classmethod
    def stop(cls):
        """Stop the background polling thread."""
        cls._stop_event.set()
        if cls._polling_thread:
            cls._polling_thread.join(timeout=5)
        logger.info("SimulationStatePoller stopped")
    
    @classmethod
    def _poll_loop(cls):
        """Main polling loop."""
        while not cls._stop_event.is_set():
            try:
                cls._check_simulations()
            except Exception as e:
                logger.error(f"Error in state poller: {e}")
            
            cls._stop_event.wait(cls.POLL_INTERVAL)
    
    @classmethod
    def _check_simulations(cls):
        """Check all simulations with active subscribers."""
        with SimulationEventEmitter._lock:
            active_sims = list(SimulationEventEmitter._subscriptions.keys())
        
        for sim_id in active_sims:
            try:
                state = SimulationRunner.get_run_state(sim_id)
                if not state:
                    continue
                
                current_state = state.to_dict()
                last_state = cls._last_states.get(sim_id, {})
                
                # Check for changes
                if current_state.get('current_round', 0) > last_state.get('current_round', 0):
                    # Round completed
                    SimulationEventEmitter.emit_step_complete(
                        sim_id,
                        current_state['current_round'],
                        current_state['total_rounds']
                    )
                
                if current_state.get('runner_status') != last_state.get('runner_status'):
                    status = current_state['runner_status']
                    if status == 'completed':
                        SimulationEventEmitter.emit_simulation_done(sim_id, current_state)
                    elif status == 'failed':
                        SimulationEventEmitter.emit_simulation_error(
                            sim_id,
                            current_state.get('error', 'Unknown error')
                        )
                
                cls._last_states[sim_id] = current_state
                
            except Exception as e:
                logger.warning(f"Error checking simulation {sim_id}: {e}")


# Auto-start poller when module is imported
# SimulationStatePoller.start()  # Commented out - start from app factory instead

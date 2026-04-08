"""
OASISæ¨¡æ‹Ÿè¿è¡Œå™¨
åœ¨åŽå°è¿è¡Œæ¨¡æ‹Ÿå¹¶è®°å½•æ¯ä¸ªAgentçš„åŠ¨ä½œï¼Œæ”¯æŒå®žæ—¶çŠ¶æ€ç›‘æŽ§
"""

import os
import sys
import json
import time
import asyncio
import threading
import subprocess
import signal
import atexit
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_locale, set_locale
from .zep_graph_memory_updater import ZepGraphMemoryManager
from .simulation_ipc import SimulationIPCClient, CommandType, IPCResponse
from .hallucination_gate import HallucinationGate, HallucinationScore

logger = get_logger('posiedon.simulation_runner')

# æ ‡è®°æ˜¯å¦å·²æ³¨å†Œæ¸…ç†å‡½æ•°
_cleanup_registered = False

# å¹³å°æ£€æµ‹
IS_WINDOWS = sys.platform == 'win32'


class RunnerStatus(str, Enum):
    """è¿è¡Œå™¨çŠ¶æ€"""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentAction:
    """AgentåŠ¨ä½œè®°å½•"""
    round_num: int
    timestamp: str
    platform: str  # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str  # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    success: bool = True
    # Hallucination validation score: 0=clean, 1=corrected, 2=forced_fallback
    hallucination_score: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "platform": self.platform,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "action_args": self.action_args,
            "result": self.result,
            "success": self.success,
            "hallucination_score": self.hallucination_score,
        }


@dataclass
class RoundSummary:
    """æ¯è½®æ‘˜è¦"""
    round_num: int
    start_time: str
    end_time: Optional[str] = None
    simulated_hour: int = 0
    twitter_actions: int = 0
    reddit_actions: int = 0
    active_agents: List[int] = field(default_factory=list)
    actions: List[AgentAction] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "simulated_hour": self.simulated_hour,
            "twitter_actions": self.twitter_actions,
            "reddit_actions": self.reddit_actions,
            "active_agents": self.active_agents,
            "actions_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
        }


@dataclass
class SimulationRunState:
    """æ¨¡æ‹Ÿè¿è¡ŒçŠ¶æ€ï¼ˆå®žæ—¶ï¼‰"""
    simulation_id: str
    runner_status: RunnerStatus = RunnerStatus.IDLE
    
    # è¿›åº¦ä¿¡æ¯
    current_round: int = 0
    total_rounds: int = 0
    simulated_hours: int = 0
    total_simulation_hours: int = 0
    
    # å„å¹³å°ç‹¬ç«‹è½®æ¬¡å’Œæ¨¡æ‹Ÿæ—¶é—´ï¼ˆç”¨äºŽåŒå¹³å°å¹¶è¡Œæ˜¾ç¤ºï¼‰
    twitter_current_round: int = 0
    reddit_current_round: int = 0
    twitter_simulated_hours: int = 0
    reddit_simulated_hours: int = 0
    
    # å¹³å°çŠ¶æ€
    twitter_running: bool = False
    reddit_running: bool = False
    twitter_actions_count: int = 0
    reddit_actions_count: int = 0
    
    # å¹³å°å®ŒæˆçŠ¶æ€ï¼ˆé€šè¿‡æ£€æµ‹ actions.jsonl ä¸­çš„ simulation_end äº‹ä»¶ï¼‰
    twitter_completed: bool = False
    reddit_completed: bool = False
    
    # æ¯è½®æ‘˜è¦
    rounds: List[RoundSummary] = field(default_factory=list)
    
    # æœ€è¿‘åŠ¨ä½œï¼ˆç”¨äºŽå‰ç«¯å®žæ—¶å±•ç¤ºï¼‰
    recent_actions: List[AgentAction] = field(default_factory=list)
    max_recent_actions: int = 50
    
    # æ—¶é—´æˆ³
    started_at: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    # é”™è¯¯ä¿¡æ¯
    error: Optional[str] = None
    
    # è¿›ç¨‹IDï¼ˆç”¨äºŽåœæ­¢ï¼‰
    process_pid: Optional[int] = None
    
    def add_action(self, action: AgentAction):
        """æ·»åŠ åŠ¨ä½œåˆ°æœ€è¿‘åŠ¨ä½œåˆ—è¡¨"""
        self.recent_actions.insert(0, action)
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions = self.recent_actions[:self.max_recent_actions]
        
        if action.platform == "twitter":
            self.twitter_actions_count += 1
        else:
            self.reddit_actions_count += 1
        
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "runner_status": self.runner_status.value,
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "simulated_hours": self.simulated_hours,
            "total_simulation_hours": self.total_simulation_hours,
            "progress_percent": round(self.current_round / max(self.total_rounds, 1) * 100, 1),
            # å„å¹³å°ç‹¬ç«‹è½®æ¬¡å’Œæ—¶é—´
            "twitter_current_round": self.twitter_current_round,
            "reddit_current_round": self.reddit_current_round,
            "twitter_simulated_hours": self.twitter_simulated_hours,
            "reddit_simulated_hours": self.reddit_simulated_hours,
            "twitter_running": self.twitter_running,
            "reddit_running": self.reddit_running,
            "twitter_completed": self.twitter_completed,
            "reddit_completed": self.reddit_completed,
            "twitter_actions_count": self.twitter_actions_count,
            "reddit_actions_count": self.reddit_actions_count,
            "total_actions_count": self.twitter_actions_count + self.reddit_actions_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "process_pid": self.process_pid,
        }
    
    def to_detail_dict(self) -> Dict[str, Any]:
        """åŒ…å«æœ€è¿‘åŠ¨ä½œçš„è¯¦ç»†ä¿¡æ¯"""
        result = self.to_dict()
        result["recent_actions"] = [a.to_dict() for a in self.recent_actions]
        result["rounds_count"] = len(self.rounds)
        return result


class SimulationRunner:
    """
    æ¨¡æ‹Ÿè¿è¡Œå™¨
    
    è´Ÿè´£ï¼š
    1. åœ¨åŽå°è¿›ç¨‹ä¸­è¿è¡ŒOASISæ¨¡æ‹Ÿ
    2. è§£æžè¿è¡Œæ—¥å¿—ï¼Œè®°å½•æ¯ä¸ªAgentçš„åŠ¨ä½œ
    3. æä¾›å®žæ—¶çŠ¶æ€æŸ¥è¯¢æŽ¥å£
    4. æ”¯æŒæš‚åœ/åœæ­¢/æ¢å¤æ“ä½œ
    """
    
    # è¿è¡ŒçŠ¶æ€å­˜å‚¨ç›®å½•
    RUN_STATE_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../uploads/simulations'
    )
    
    # è„šæœ¬ç›®å½•
    SCRIPTS_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../scripts'
    )
    
    # å†…å­˜ä¸­çš„è¿è¡ŒçŠ¶æ€
    _run_states: Dict[str, SimulationRunState] = {}
    _processes: Dict[str, subprocess.Popen] = {}
    _action_queues: Dict[str, Queue] = {}
    _monitor_threads: Dict[str, threading.Thread] = {}
    _stdout_files: Dict[str, Any] = {}  # å­˜å‚¨ stdout æ–‡ä»¶å¥æŸ„
    _stderr_files: Dict[str, Any] = {}  # å­˜å‚¨ stderr æ–‡ä»¶å¥æŸ„
    
    # å›¾è°±è®°å¿†æ›´æ–°é…ç½®
    _graph_memory_enabled: Dict[str, bool] = {}  # simulation_id -> enabled
    
    @classmethod
    def get_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """èŽ·å–è¿è¡ŒçŠ¶æ€"""
        if simulation_id in cls._run_states:
            return cls._run_states[simulation_id]
        
        # å°è¯•ä»Žæ–‡ä»¶åŠ è½½
        state = cls._load_run_state(simulation_id)
        if state:
            cls._run_states[simulation_id] = state
        return state
    
    @classmethod
    def _load_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """ä»Žæ–‡ä»¶åŠ è½½è¿è¡ŒçŠ¶æ€"""
        state_file = os.path.join(cls.RUN_STATE_DIR, simulation_id, "run_state.json")
        if not os.path.exists(state_file):
            return None
        
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            state = SimulationRunState(
                simulation_id=simulation_id,
                runner_status=RunnerStatus(data.get("runner_status", "idle")),
                current_round=data.get("current_round", 0),
                total_rounds=data.get("total_rounds", 0),
                simulated_hours=data.get("simulated_hours", 0),
                total_simulation_hours=data.get("total_simulation_hours", 0),
                # å„å¹³å°ç‹¬ç«‹è½®æ¬¡å’Œæ—¶é—´
                twitter_current_round=data.get("twitter_current_round", 0),
                reddit_current_round=data.get("reddit_current_round", 0),
                twitter_simulated_hours=data.get("twitter_simulated_hours", 0),
                reddit_simulated_hours=data.get("reddit_simulated_hours", 0),
                twitter_running=data.get("twitter_running", False),
                reddit_running=data.get("reddit_running", False),
                twitter_completed=data.get("twitter_completed", False),
                reddit_completed=data.get("reddit_completed", False),
                twitter_actions_count=data.get("twitter_actions_count", 0),
                reddit_actions_count=data.get("reddit_actions_count", 0),
                started_at=data.get("started_at"),
                updated_at=data.get("updated_at", datetime.now().isoformat()),
                completed_at=data.get("completed_at"),
                error=data.get("error"),
                process_pid=data.get("process_pid"),
            )
            
            # åŠ è½½æœ€è¿‘åŠ¨ä½œ
            actions_data = data.get("recent_actions", [])
            for a in actions_data:
                state.recent_actions.append(AgentAction(
                    round_num=a.get("round_num", 0),
                    timestamp=a.get("timestamp", ""),
                    platform=a.get("platform", ""),
                    agent_id=a.get("agent_id", 0),
                    agent_name=a.get("agent_name", ""),
                    action_type=a.get("action_type", ""),
                    action_args=a.get("action_args", {}),
                    result=a.get("result"),
                    success=a.get("success", True),
                ))
            
            return state
        except Exception as e:
            logger.error(f"åŠ è½½è¿è¡ŒçŠ¶æ€å¤±è´¥: {str(e)}")
            return None
    
    @classmethod
    def _save_run_state(cls, state: SimulationRunState):
        """ä¿å­˜è¿è¡ŒçŠ¶æ€åˆ°æ–‡ä»¶"""
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        state_file = os.path.join(sim_dir, "run_state.json")
        
        data = state.to_detail_dict()
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        cls._run_states[state.simulation_id] = state
    
    @classmethod
    def start_simulation(
        cls,
        simulation_id: str,
        platform: str = "parallel",  # twitter / reddit / parallel
        max_rounds: int = None,  # æœ€å¤§æ¨¡æ‹Ÿè½®æ•°ï¼ˆå¯é€‰ï¼Œç”¨äºŽæˆªæ–­è¿‡é•¿çš„æ¨¡æ‹Ÿï¼‰
        enable_graph_memory_update: bool = False,  # æ˜¯å¦å°†æ´»åŠ¨æ›´æ–°åˆ°Zepå›¾è°±
        graph_id: str = None  # Zepå›¾è°±IDï¼ˆå¯ç”¨å›¾è°±æ›´æ–°æ—¶å¿…éœ€ï¼‰
    ) -> SimulationRunState:
        """
        å¯åŠ¨æ¨¡æ‹Ÿ
        
        Args:
            simulation_id: æ¨¡æ‹ŸID
            platform: è¿è¡Œå¹³å° (twitter/reddit/parallel)
            max_rounds: æœ€å¤§æ¨¡æ‹Ÿè½®æ•°ï¼ˆå¯é€‰ï¼Œç”¨äºŽæˆªæ–­è¿‡é•¿çš„æ¨¡æ‹Ÿï¼‰
            enable_graph_memory_update: æ˜¯å¦å°†Agentæ´»åŠ¨åŠ¨æ€æ›´æ–°åˆ°Zepå›¾è°±
            graph_id: Zepå›¾è°±IDï¼ˆå¯ç”¨å›¾è°±æ›´æ–°æ—¶å¿…éœ€ï¼‰
            
        Returns:
            SimulationRunState
        """
        # æ£€æŸ¥æ˜¯å¦å·²åœ¨è¿è¡Œ
        existing = cls.get_run_state(simulation_id)
        if existing and existing.runner_status in [RunnerStatus.RUNNING, RunnerStatus.STARTING]:
            raise ValueError(f"æ¨¡æ‹Ÿå·²åœ¨è¿è¡Œä¸­: {simulation_id}")
        
        # åŠ è½½æ¨¡æ‹Ÿé…ç½®
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            raise ValueError(f"æ¨¡æ‹Ÿé…ç½®ä¸å­˜åœ¨ï¼Œè¯·å…ˆè°ƒç”¨ /prepare æŽ¥å£")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # åˆå§‹åŒ–è¿è¡ŒçŠ¶æ€
        time_config = config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)
        total_rounds = int(total_hours * 60 / minutes_per_round)
        
        # å¦‚æžœæŒ‡å®šäº†æœ€å¤§è½®æ•°ï¼Œåˆ™æˆªæ–­
        if max_rounds is not None and max_rounds > 0:
            original_rounds = total_rounds
            total_rounds = min(total_rounds, max_rounds)
            if total_rounds < original_rounds:
                logger.info(f"è½®æ•°å·²æˆªæ–­: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})")
        
        state = SimulationRunState(
            simulation_id=simulation_id,
            runner_status=RunnerStatus.STARTING,
            total_rounds=total_rounds,
            total_simulation_hours=total_hours,
            started_at=datetime.now().isoformat(),
        )
        
        cls._save_run_state(state)
        
        # å¦‚æžœå¯ç”¨å›¾è°±è®°å¿†æ›´æ–°ï¼Œåˆ›å»ºæ›´æ–°å™¨
        if enable_graph_memory_update:
            if not graph_id:
                raise ValueError("å¯ç”¨å›¾è°±è®°å¿†æ›´æ–°æ—¶å¿…é¡»æä¾› graph_id")
            
            try:
                ZepGraphMemoryManager.create_updater(simulation_id, graph_id)
                cls._graph_memory_enabled[simulation_id] = True
                logger.info(f"å·²å¯ç”¨å›¾è°±è®°å¿†æ›´æ–°: simulation_id={simulation_id}, graph_id={graph_id}")
            except Exception as e:
                logger.error(f"åˆ›å»ºå›¾è°±è®°å¿†æ›´æ–°å™¨å¤±è´¥: {e}")
                cls._graph_memory_enabled[simulation_id] = False
        else:
            cls._graph_memory_enabled[simulation_id] = False
        
        # ç¡®å®šè¿è¡Œå“ªä¸ªè„šæœ¬ï¼ˆè„šæœ¬ä½äºŽ backend/scripts/ ç›®å½•ï¼‰
        if platform == "twitter":
            script_name = "run_twitter_simulation.py"
            state.twitter_running = True
        elif platform == "reddit":
            script_name = "run_reddit_simulation.py"
            state.reddit_running = True
        else:
            script_name = "run_parallel_simulation.py"
            state.twitter_running = True
            state.reddit_running = True
        
        script_path = os.path.join(cls.SCRIPTS_DIR, script_name)
        
        if not os.path.exists(script_path):
            raise ValueError(f"è„šæœ¬ä¸å­˜åœ¨: {script_path}")
        
        # åˆ›å»ºåŠ¨ä½œé˜Ÿåˆ—
        action_queue = Queue()
        cls._action_queues[simulation_id] = action_queue
        
        # å¯åŠ¨æ¨¡æ‹Ÿè¿›ç¨‹
        try:
            # æž„å»ºè¿è¡Œå‘½ä»¤ï¼Œä½¿ç”¨å®Œæ•´è·¯å¾„
            # æ–°çš„æ—¥å¿—ç»“æž„ï¼š
            #   twitter/actions.jsonl - Twitter åŠ¨ä½œæ—¥å¿—
            #   reddit/actions.jsonl  - Reddit åŠ¨ä½œæ—¥å¿—
            #   simulation.log        - ä¸»è¿›ç¨‹æ—¥å¿—
            
            cmd = [
                sys.executable,  # Pythonè§£é‡Šå™¨
                script_path,
                "--config", config_path,  # ä½¿ç”¨å®Œæ•´é…ç½®æ–‡ä»¶è·¯å¾„
            ]
            
            # å¦‚æžœæŒ‡å®šäº†æœ€å¤§è½®æ•°ï¼Œæ·»åŠ åˆ°å‘½ä»¤è¡Œå‚æ•°
            if max_rounds is not None and max_rounds > 0:
                cmd.extend(["--max-rounds", str(max_rounds)])
            
            # åˆ›å»ºä¸»æ—¥å¿—æ–‡ä»¶ï¼Œé¿å… stdout/stderr ç®¡é“ç¼“å†²åŒºæ»¡å¯¼è‡´è¿›ç¨‹é˜»å¡ž
            main_log_path = os.path.join(sim_dir, "simulation.log")
            main_log_file = open(main_log_path, 'w', encoding='utf-8')
            
            # è®¾ç½®å­è¿›ç¨‹çŽ¯å¢ƒå˜é‡ï¼Œç¡®ä¿ Windows ä¸Šä½¿ç”¨ UTF-8 ç¼–ç 
            # è¿™å¯ä»¥ä¿®å¤ç¬¬ä¸‰æ–¹åº“ï¼ˆå¦‚ OASISï¼‰è¯»å–æ–‡ä»¶æ—¶æœªæŒ‡å®šç¼–ç çš„é—®é¢˜
            env = os.environ.copy()
            env['PYTHONUTF8'] = '1'  # Python 3.7+ æ”¯æŒï¼Œè®©æ‰€æœ‰ open() é»˜è®¤ä½¿ç”¨ UTF-8
            env['PYTHONIOENCODING'] = 'utf-8'  # ç¡®ä¿ stdout/stderr ä½¿ç”¨ UTF-8
            
            # è®¾ç½®å·¥ä½œç›®å½•ä¸ºæ¨¡æ‹Ÿç›®å½•ï¼ˆæ•°æ®åº“ç­‰æ–‡ä»¶ä¼šç”Ÿæˆåœ¨æ­¤ï¼‰
            # Cross-platform process creation:
            # - Unix: start_new_session=True creates new process group for os.killpg
            # - Windows: CREATE_NEW_PROCESS_GROUP flag for job control
            popen_kwargs = {
                'cwd': sim_dir,
                'stdout': main_log_file,
                'stderr': subprocess.STDOUT,  # stderr ä¹Ÿå†™å…¥åŒä¸€ä¸ªæ–‡ä»¶
                'text': True,
                'encoding': 'utf-8',  # æ˜¾å¼æŒ‡å®šç¼–ç 
                'bufsize': 1,
                'env': env,  # ä¼ é€’å¸¦æœ‰ UTF-8 è®¾ç½®çš„çŽ¯å¢ƒå˜é‡
            }
            
            if IS_WINDOWS:
                # Windows: CREATE_NEW_PROCESS_GROUP allows sending CTRL_BREAK_EVENT
                popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                # Unix: start_new_session creates new process group for os.killpg
                popen_kwargs['start_new_session'] = True
            
            process = subprocess.Popen(cmd, **popen_kwargs)
            
            # ä¿å­˜æ–‡ä»¶å¥æŸ„ä»¥ä¾¿åŽç»­å…³é—­
            cls._stdout_files[simulation_id] = main_log_file
            cls._stderr_files[simulation_id] = None  # ä¸å†éœ€è¦å•ç‹¬çš„ stderr
            
            state.process_pid = process.pid
            state.runner_status = RunnerStatus.RUNNING
            cls._processes[simulation_id] = process
            cls._save_run_state(state)
            
            # Capture locale before spawning monitor thread
            current_locale = get_locale()

            # å¯åŠ¨ç›‘æŽ§çº¿ç¨‹
            monitor_thread = threading.Thread(
                target=cls._monitor_simulation,
                args=(simulation_id, current_locale),
                daemon=True
            )
            monitor_thread.start()
            cls._monitor_threads[simulation_id] = monitor_thread
            
            logger.info(f"æ¨¡æ‹Ÿå¯åŠ¨æˆåŠŸ: {simulation_id}, pid={process.pid}, platform={platform}")
            
        except Exception as e:
            state.runner_status = RunnerStatus.FAILED
            state.error = str(e)
            cls._save_run_state(state)
            raise
        
        return state
    
    @classmethod
    def _monitor_simulation(cls, simulation_id: str, locale: str = 'zh'):
        """ç›‘æŽ§æ¨¡æ‹Ÿè¿›ç¨‹ï¼Œè§£æžåŠ¨ä½œæ—¥å¿—"""
        set_locale(locale)
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        # æ–°çš„æ—¥å¿—ç»“æž„ï¼šåˆ†å¹³å°çš„åŠ¨ä½œæ—¥å¿—
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        
        process = cls._processes.get(simulation_id)
        state = cls.get_run_state(simulation_id)
        
        if not process or not state:
            return
        
        twitter_position = 0
        reddit_position = 0
        
        try:
            while process.poll() is None:  # è¿›ç¨‹ä»åœ¨è¿è¡Œ
                # è¯»å– Twitter åŠ¨ä½œæ—¥å¿—
                if os.path.exists(twitter_actions_log):
                    twitter_position = cls._read_action_log(
                        twitter_actions_log, twitter_position, state, "twitter"
                    )
                
                # è¯»å– Reddit åŠ¨ä½œæ—¥å¿—
                if os.path.exists(reddit_actions_log):
                    reddit_position = cls._read_action_log(
                        reddit_actions_log, reddit_position, state, "reddit"
                    )
                
                # æ›´æ–°çŠ¶æ€
                cls._save_run_state(state)
                time.sleep(2)
            
            # è¿›ç¨‹ç»“æŸåŽï¼Œæœ€åŽè¯»å–ä¸€æ¬¡æ—¥å¿—
            if os.path.exists(twitter_actions_log):
                cls._read_action_log(twitter_actions_log, twitter_position, state, "twitter")
            if os.path.exists(reddit_actions_log):
                cls._read_action_log(reddit_actions_log, reddit_position, state, "reddit")
            
            # è¿›ç¨‹ç»“æŸ
            exit_code = process.returncode
            
            if exit_code == 0:
                state.runner_status = RunnerStatus.COMPLETED
                state.completed_at = datetime.now().isoformat()
                logger.info(f"æ¨¡æ‹Ÿå®Œæˆ: {simulation_id}")
            else:
                state.runner_status = RunnerStatus.FAILED
                # ä»Žä¸»æ—¥å¿—æ–‡ä»¶è¯»å–é”™è¯¯ä¿¡æ¯
                main_log_path = os.path.join(sim_dir, "simulation.log")
                error_info = ""
                try:
                    if os.path.exists(main_log_path):
                        with open(main_log_path, 'r', encoding='utf-8') as f:
                            error_info = f.read()[-2000:]  # å–æœ€åŽ2000å­—ç¬¦
                except Exception:
                    pass
                state.error = f"è¿›ç¨‹é€€å‡ºç : {exit_code}, é”™è¯¯: {error_info}"
                logger.error(f"æ¨¡æ‹Ÿå¤±è´¥: {simulation_id}, error={state.error}")
            
            state.twitter_running = False
            state.reddit_running = False
            cls._save_run_state(state)
            
        except Exception as e:
            logger.error(f"ç›‘æŽ§çº¿ç¨‹å¼‚å¸¸: {simulation_id}, error={str(e)}")
            state.runner_status = RunnerStatus.FAILED
            state.error = str(e)
            cls._save_run_state(state)
        
        finally:
            # åœæ­¢å›¾è°±è®°å¿†æ›´æ–°å™¨
            if cls._graph_memory_enabled.get(simulation_id, False):
                try:
                    ZepGraphMemoryManager.stop_updater(simulation_id)
                    logger.info(f"å·²åœæ­¢å›¾è°±è®°å¿†æ›´æ–°: simulation_id={simulation_id}")
                except Exception as e:
                    logger.error(f"åœæ­¢å›¾è°±è®°å¿†æ›´æ–°å™¨å¤±è´¥: {e}")
                cls._graph_memory_enabled.pop(simulation_id, None)
            
            # æ¸…ç†è¿›ç¨‹èµ„æº
            cls._processes.pop(simulation_id, None)
            cls._action_queues.pop(simulation_id, None)
            
            # å…³é—­æ—¥å¿—æ–‡ä»¶å¥æŸ„
            if simulation_id in cls._stdout_files:
                try:
                    cls._stdout_files[simulation_id].close()
                except Exception:
                    pass
                cls._stdout_files.pop(simulation_id, None)
            if simulation_id in cls._stderr_files and cls._stderr_files[simulation_id]:
                try:
                    cls._stderr_files[simulation_id].close()
                except Exception:
                    pass
                cls._stderr_files.pop(simulation_id, None)
    
    @classmethod
    def _read_action_log(
        cls, 
        log_path: str, 
        position: int, 
        state: SimulationRunState,
        platform: str
    ) -> int:
        """
        è¯»å–åŠ¨ä½œæ—¥å¿—æ–‡ä»¶
        
        Args:
            log_path: æ—¥å¿—æ–‡ä»¶è·¯å¾„
            position: ä¸Šæ¬¡è¯»å–ä½ç½®
            state: è¿è¡ŒçŠ¶æ€å¯¹è±¡
            platform: å¹³å°åç§° (twitter/reddit)
            
        Returns:
            æ–°çš„è¯»å–ä½ç½®
        """
        # æ£€æŸ¥æ˜¯å¦å¯ç”¨äº†å›¾è°±è®°å¿†æ›´æ–°
        graph_memory_enabled = cls._graph_memory_enabled.get(state.simulation_id, False)
        graph_updater = None
        if graph_memory_enabled:
            graph_updater = ZepGraphMemoryManager.get_updater(state.simulation_id)
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                f.seek(position)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            action_data = json.loads(line)
                            
                            # å¤„ç†äº‹ä»¶ç±»åž‹çš„æ¡ç›®
                            if "event_type" in action_data:
                                event_type = action_data.get("event_type")
                                
                                # æ£€æµ‹ simulation_end äº‹ä»¶ï¼Œæ ‡è®°å¹³å°å·²å®Œæˆ
                                if event_type == "simulation_end":
                                    if platform == "twitter":
                                        state.twitter_completed = True
                                        state.twitter_running = False
                                        logger.info(f"Twitter æ¨¡æ‹Ÿå·²å®Œæˆ: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")
                                    elif platform == "reddit":
                                        state.reddit_completed = True
                                        state.reddit_running = False
                                        logger.info(f"Reddit æ¨¡æ‹Ÿå·²å®Œæˆ: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")
                                    
                                    # æ£€æŸ¥æ˜¯å¦æ‰€æœ‰å¯ç”¨çš„å¹³å°éƒ½å·²å®Œæˆ
                                    # å¦‚æžœåªè¿è¡Œäº†ä¸€ä¸ªå¹³å°ï¼Œåªæ£€æŸ¥é‚£ä¸ªå¹³å°
                                    # å¦‚æžœè¿è¡Œäº†ä¸¤ä¸ªå¹³å°ï¼Œéœ€è¦ä¸¤ä¸ªéƒ½å®Œæˆ
                                    all_completed = cls._check_all_platforms_completed(state)
                                    if all_completed:
                                        state.runner_status = RunnerStatus.COMPLETED
                                        state.completed_at = datetime.now().isoformat()
                                        logger.info(f"æ‰€æœ‰å¹³å°æ¨¡æ‹Ÿå·²å®Œæˆ: {state.simulation_id}")
                                
                                # æ›´æ–°è½®æ¬¡ä¿¡æ¯ï¼ˆä»Ž round_end äº‹ä»¶ï¼‰
                                elif event_type == "round_end":
                                    round_num = action_data.get("round", 0)
                                    simulated_hours = action_data.get("simulated_hours", 0)
                                    
                                    # æ›´æ–°å„å¹³å°ç‹¬ç«‹çš„è½®æ¬¡å’Œæ—¶é—´
                                    if platform == "twitter":
                                        if round_num > state.twitter_current_round:
                                            state.twitter_current_round = round_num
                                        state.twitter_simulated_hours = simulated_hours
                                    elif platform == "reddit":
                                        if round_num > state.reddit_current_round:
                                            state.reddit_current_round = round_num
                                        state.reddit_simulated_hours = simulated_hours
                                    
                                    # æ€»ä½“è½®æ¬¡å–ä¸¤ä¸ªå¹³å°çš„æœ€å¤§å€¼
                                    if round_num > state.current_round:
                                        state.current_round = round_num
                                    # æ€»ä½“æ—¶é—´å–ä¸¤ä¸ªå¹³å°çš„æœ€å¤§å€¼
                                    state.simulated_hours = max(state.twitter_simulated_hours, state.reddit_simulated_hours)
                                    
                                    # Trigger opinion drift processing at end of round
                                    try:
                                        cls._process_opinion_drift(state, platform, round_num)
                                    except Exception as drift_err:
                                        logger.warning(f"Opinion drift processing failed for round {round_num}: {drift_err}")
                                
                                continue
                            
                            action = AgentAction(
                                round_num=action_data.get("round", 0),
                                timestamp=action_data.get("timestamp", datetime.now().isoformat()),
                                platform=platform,
                                agent_id=action_data.get("agent_id", 0),
                                agent_name=action_data.get("agent_name", ""),
                                action_type=action_data.get("action_type", ""),
                                action_args=action_data.get("action_args", {}),
                                result=action_data.get("result"),
                                success=action_data.get("success", True),
                                hallucination_score=action_data.get("hallucination_score", 0),
                            )
                            state.add_action(action)
                            
                            # æ›´æ–°è½®æ¬¡
                            if action.round_num and action.round_num > state.current_round:
                                state.current_round = action.round_num
                            
                            # å¦‚æžœå¯ç”¨äº†å›¾è°±è®°å¿†æ›´æ–°ï¼Œå°†æ´»åŠ¨å‘é€åˆ°Zep
                            if graph_updater:
                                graph_updater.add_activity_from_dict(action_data, platform)
                            
                        except json.JSONDecodeError:
                            pass
                return f.tell()
        except Exception as e:
            logger.warning(f"è¯»å–åŠ¨ä½œæ—¥å¿—å¤±è´¥: {log_path}, error={e}")
            return position
    
    @classmethod
    def _check_all_platforms_completed(cls, state: SimulationRunState) -> bool:
        """
        æ£€æŸ¥æ‰€æœ‰å¯ç”¨çš„å¹³å°æ˜¯å¦éƒ½å·²å®Œæˆæ¨¡æ‹Ÿ
        
        é€šè¿‡æ£€æŸ¥å¯¹åº”çš„ actions.jsonl æ–‡ä»¶æ˜¯å¦å­˜åœ¨æ¥åˆ¤æ–­å¹³å°æ˜¯å¦è¢«å¯ç”¨
        
        Returns:
            True å¦‚æžœæ‰€æœ‰å¯ç”¨çš„å¹³å°éƒ½å·²å®Œæˆ
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        twitter_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        
        # æ£€æŸ¥å“ªäº›å¹³å°è¢«å¯ç”¨ï¼ˆé€šè¿‡æ–‡ä»¶æ˜¯å¦å­˜åœ¨åˆ¤æ–­ï¼‰
        twitter_enabled = os.path.exists(twitter_log)
        reddit_enabled = os.path.exists(reddit_log)
        
        # å¦‚æžœå¹³å°è¢«å¯ç”¨ä½†æœªå®Œæˆï¼Œåˆ™è¿”å›ž False
        if twitter_enabled and not state.twitter_completed:
            return False
        if reddit_enabled and not state.reddit_completed:
            return False
        
        # è‡³å°‘æœ‰ä¸€ä¸ªå¹³å°è¢«å¯ç”¨ä¸”å·²å®Œæˆ
        return twitter_enabled or reddit_enabled
    
    # Opinion drift state - track last processed round per simulation/platform
    _opinion_drift_last_round: Dict[str, Dict[str, int]] = {}
    
    @classmethod
    def _process_opinion_drift(cls, state: SimulationRunState, platform: str, round_number: int):
        """
        Process opinion drift for agents after a round completes.
        
        This updates agent opinion states based on their exposure to content
        during the round.
        
        Args:
            state: Current simulation run state
            platform: Platform that completed the round (twitter/reddit)
            round_number: The round number that just completed
        """
        from .opinion_drift import OpinionDriftProcessor
        
        sim_id = state.simulation_id
        
        # Track last processed round to avoid duplicate processing
        if sim_id not in cls._opinion_drift_last_round:
            cls._opinion_drift_last_round[sim_id] = {}
        
        platform_last_round = cls._opinion_drift_last_round[sim_id].get(platform, 0)
        if round_number <= platform_last_round:
            return  # Already processed
        
        cls._opinion_drift_last_round[sim_id][platform] = round_number
        
        logger.info(f"Processing opinion drift: simulation={sim_id}, platform={platform}, round={round_number}")
        
        try:
            # Load agent profiles
            sim_dir = os.path.join(cls.RUN_STATE_DIR, sim_id)
            profiles_path = os.path.join(sim_dir, platform, "agent_profiles.json")
            
            if not os.path.exists(profiles_path):
                # Try alternate location
                profiles_path = os.path.join(sim_dir, f"{platform}_profiles.json")
            
            if not os.path.exists(profiles_path):
                logger.debug(f"No agent profiles found for opinion drift: {profiles_path}")
                return
            
            with open(profiles_path, 'r', encoding='utf-8') as f:
                agent_profiles = json.load(f)
            
            if not isinstance(agent_profiles, list):
                agent_profiles = [agent_profiles]
            
            # Collect actions from this round
            actions_path = os.path.join(sim_dir, platform, "actions.jsonl")
            round_actions = []
            
            if os.path.exists(actions_path):
                with open(actions_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                action = json.loads(line)
                                if action.get('round', action.get('round_num', 0)) == round_number:
                                    round_actions.append(action)
                            except json.JSONDecodeError:
                                pass
            
            if not round_actions:
                logger.debug(f"No actions found for round {round_number}")
                return
            
            # Initialize processor and update opinions
            processor = OpinionDriftProcessor()
            
            # Extract topics from simulation config if available
            config_path = os.path.join(sim_dir, "simulation_config.json")
            topics = None
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    topics = config.get('opinion_topics')
            
            # Process opinion drift
            updated_profiles = processor.process_round(
                agent_profiles,
                round_actions,
                round_number,
                topics
            )
            
            # Save updated profiles
            # Use a separate file to track opinion evolution without modifying original
            opinion_state_path = os.path.join(sim_dir, platform, "agent_opinion_state.json")
            with open(opinion_state_path, 'w', encoding='utf-8') as f:
                json.dump(updated_profiles, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Opinion drift processed: {len(updated_profiles)} agents updated for round {round_number}")
            
        except Exception as e:
            logger.error(f"Opinion drift processing error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    @classmethod
    def _terminate_process(cls, process: subprocess.Popen, simulation_id: str, timeout: int = 10):
        """
        è·¨å¹³å°ç»ˆæ­¢è¿›ç¨‹åŠå…¶å­è¿›ç¨‹
        
        Args:
            process: è¦ç»ˆæ­¢çš„è¿›ç¨‹
            simulation_id: æ¨¡æ‹ŸIDï¼ˆç”¨äºŽæ—¥å¿—ï¼‰
            timeout: ç­‰å¾…è¿›ç¨‹é€€å‡ºçš„è¶…æ—¶æ—¶é—´ï¼ˆç§’ï¼‰
        """
        if IS_WINDOWS:
            # Windows: ä½¿ç”¨ taskkill å‘½ä»¤ç»ˆæ­¢è¿›ç¨‹æ ‘
            # /F = å¼ºåˆ¶ç»ˆæ­¢, /T = ç»ˆæ­¢è¿›ç¨‹æ ‘ï¼ˆåŒ…æ‹¬å­è¿›ç¨‹ï¼‰
            logger.info(f"ç»ˆæ­¢è¿›ç¨‹æ ‘ (Windows): simulation={simulation_id}, pid={process.pid}")
            try:
                # å…ˆå°è¯•ä¼˜é›…ç»ˆæ­¢
                subprocess.run(
                    ['taskkill', '/PID', str(process.pid), '/T'],
                    capture_output=True,
                    timeout=5
                )
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # å¼ºåˆ¶ç»ˆæ­¢
                    logger.warning(f"è¿›ç¨‹æœªå“åº”ï¼Œå¼ºåˆ¶ç»ˆæ­¢: {simulation_id}")
                    subprocess.run(
                        ['taskkill', '/F', '/PID', str(process.pid), '/T'],
                        capture_output=True,
                        timeout=5
                    )
                    process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"taskkill å¤±è´¥ï¼Œå°è¯• terminate: {e}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        else:
            # Unix: ä½¿ç”¨è¿›ç¨‹ç»„ç»ˆæ­¢
            # ç”±äºŽä½¿ç”¨äº† start_new_session=Trueï¼Œè¿›ç¨‹ç»„ ID ç­‰äºŽä¸»è¿›ç¨‹ PID
            pgid = os.getpgid(process.pid)
            logger.info(f"ç»ˆæ­¢è¿›ç¨‹ç»„ (Unix): simulation={simulation_id}, pgid={pgid}")
            
            # å…ˆå‘é€ SIGTERM ç»™æ•´ä¸ªè¿›ç¨‹ç»„
            os.killpg(pgid, signal.SIGTERM)
            
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # å¦‚æžœè¶…æ—¶åŽè¿˜æ²¡ç»“æŸï¼Œå¼ºåˆ¶å‘é€ SIGKILL
                logger.warning(f"è¿›ç¨‹ç»„æœªå“åº” SIGTERMï¼Œå¼ºåˆ¶ç»ˆæ­¢: {simulation_id}")
                os.killpg(pgid, signal.SIGKILL)
                process.wait(timeout=5)
    
    @classmethod
    def stop_simulation(cls, simulation_id: str) -> SimulationRunState:
        """åœæ­¢æ¨¡æ‹Ÿ"""
        state = cls.get_run_state(simulation_id)
        if not state:
            raise ValueError(f"æ¨¡æ‹Ÿä¸å­˜åœ¨: {simulation_id}")
        
        if state.runner_status not in [RunnerStatus.RUNNING, RunnerStatus.PAUSED]:
            raise ValueError(f"æ¨¡æ‹Ÿæœªåœ¨è¿è¡Œ: {simulation_id}, status={state.runner_status}")
        
        state.runner_status = RunnerStatus.STOPPING
        cls._save_run_state(state)
        
        # ç»ˆæ­¢è¿›ç¨‹
        process = cls._processes.get(simulation_id)
        if process and process.poll() is None:
            try:
                cls._terminate_process(process, simulation_id)
            except ProcessLookupError:
                # è¿›ç¨‹å·²ç»ä¸å­˜åœ¨
                pass
            except Exception as e:
                logger.error(f"ç»ˆæ­¢è¿›ç¨‹ç»„å¤±è´¥: {simulation_id}, error={e}")
                # å›žé€€åˆ°ç›´æŽ¥ç»ˆæ­¢è¿›ç¨‹
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
        
        state.runner_status = RunnerStatus.STOPPED
        state.twitter_running = False
        state.reddit_running = False
        state.completed_at = datetime.now().isoformat()
        cls._save_run_state(state)
        
        # åœæ­¢å›¾è°±è®°å¿†æ›´æ–°å™¨
        if cls._graph_memory_enabled.get(simulation_id, False):
            try:
                ZepGraphMemoryManager.stop_updater(simulation_id)
                logger.info(f"å·²åœæ­¢å›¾è°±è®°å¿†æ›´æ–°: simulation_id={simulation_id}")
            except Exception as e:
                logger.error(f"åœæ­¢å›¾è°±è®°å¿†æ›´æ–°å™¨å¤±è´¥: {e}")
            cls._graph_memory_enabled.pop(simulation_id, None)
        
        logger.info(f"æ¨¡æ‹Ÿå·²åœæ­¢: {simulation_id}")
        return state
    
    @classmethod
    def _read_actions_from_file(
        cls,
        file_path: str,
        default_platform: Optional[str] = None,
        platform_filter: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        ä»Žå•ä¸ªåŠ¨ä½œæ–‡ä»¶ä¸­è¯»å–åŠ¨ä½œ
        
        Args:
            file_path: åŠ¨ä½œæ—¥å¿—æ–‡ä»¶è·¯å¾„
            default_platform: é»˜è®¤å¹³å°ï¼ˆå½“åŠ¨ä½œè®°å½•ä¸­æ²¡æœ‰ platform å­—æ®µæ—¶ä½¿ç”¨ï¼‰
            platform_filter: è¿‡æ»¤å¹³å°
            agent_id: è¿‡æ»¤ Agent ID
            round_num: è¿‡æ»¤è½®æ¬¡
        """
        if not os.path.exists(file_path):
            return []
        
        actions = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # è·³è¿‡éžåŠ¨ä½œè®°å½•ï¼ˆå¦‚ simulation_start, round_start, round_end ç­‰äº‹ä»¶ï¼‰
                    if "event_type" in data:
                        continue
                    
                    # è·³è¿‡æ²¡æœ‰ agent_id çš„è®°å½•ï¼ˆéž Agent åŠ¨ä½œï¼‰
                    if "agent_id" not in data:
                        continue
                    
                    # èŽ·å–å¹³å°ï¼šä¼˜å…ˆä½¿ç”¨è®°å½•ä¸­çš„ platformï¼Œå¦åˆ™ä½¿ç”¨é»˜è®¤å¹³å°
                    record_platform = data.get("platform") or default_platform or ""
                    
                    # è¿‡æ»¤
                    if platform_filter and record_platform != platform_filter:
                        continue
                    if agent_id is not None and data.get("agent_id") != agent_id:
                        continue
                    if round_num is not None and data.get("round") != round_num:
                        continue
                    
                    actions.append(AgentAction(
                        round_num=data.get("round", 0),
                        timestamp=data.get("timestamp", ""),
                        platform=record_platform,
                        agent_id=data.get("agent_id", 0),
                        agent_name=data.get("agent_name", ""),
                        action_type=data.get("action_type", ""),
                        action_args=data.get("action_args", {}),
                        result=data.get("result"),
                        success=data.get("success", True),
                        hallucination_score=data.get("hallucination_score", 0),
                    ))
                    
                except json.JSONDecodeError:
                    continue
        
        return actions
    
    @classmethod
    def get_all_actions(
        cls,
        simulation_id: str,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        èŽ·å–æ‰€æœ‰å¹³å°çš„å®Œæ•´åŠ¨ä½œåŽ†å²ï¼ˆæ— åˆ†é¡µé™åˆ¶ï¼‰
        
        Args:
            simulation_id: æ¨¡æ‹ŸID
            platform: è¿‡æ»¤å¹³å°ï¼ˆtwitter/redditï¼‰
            agent_id: è¿‡æ»¤Agent
            round_num: è¿‡æ»¤è½®æ¬¡
            
        Returns:
            å®Œæ•´çš„åŠ¨ä½œåˆ—è¡¨ï¼ˆæŒ‰æ—¶é—´æˆ³æŽ’åºï¼Œæ–°çš„åœ¨å‰ï¼‰
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        actions = []
        
        # è¯»å– Twitter åŠ¨ä½œæ–‡ä»¶ï¼ˆæ ¹æ®æ–‡ä»¶è·¯å¾„è‡ªåŠ¨è®¾ç½® platform ä¸º twitterï¼‰
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        if not platform or platform == "twitter":
            actions.extend(cls._read_actions_from_file(
                twitter_actions_log,
                default_platform="twitter",  # è‡ªåŠ¨å¡«å…… platform å­—æ®µ
                platform_filter=platform,
                agent_id=agent_id, 
                round_num=round_num
            ))
        
        # è¯»å– Reddit åŠ¨ä½œæ–‡ä»¶ï¼ˆæ ¹æ®æ–‡ä»¶è·¯å¾„è‡ªåŠ¨è®¾ç½® platform ä¸º redditï¼‰
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        if not platform or platform == "reddit":
            actions.extend(cls._read_actions_from_file(
                reddit_actions_log,
                default_platform="reddit",  # è‡ªåŠ¨å¡«å…… platform å­—æ®µ
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            ))
        
        # å¦‚æžœåˆ†å¹³å°æ–‡ä»¶ä¸å­˜åœ¨ï¼Œå°è¯•è¯»å–æ—§çš„å•ä¸€æ–‡ä»¶æ ¼å¼
        if not actions:
            actions_log = os.path.join(sim_dir, "actions.jsonl")
            actions = cls._read_actions_from_file(
                actions_log,
                default_platform=None,  # æ—§æ ¼å¼æ–‡ä»¶ä¸­åº”è¯¥æœ‰ platform å­—æ®µ
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            )
        
        # æŒ‰æ—¶é—´æˆ³æŽ’åºï¼ˆæ–°çš„åœ¨å‰ï¼‰
        actions.sort(key=lambda x: x.timestamp, reverse=True)
        
        return actions
    
    @classmethod
    def get_actions(
        cls,
        simulation_id: str,
        limit: int = 100,
        offset: int = 0,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        èŽ·å–åŠ¨ä½œåŽ†å²ï¼ˆå¸¦åˆ†é¡µï¼‰
        
        Args:
            simulation_id: æ¨¡æ‹ŸID
            limit: è¿”å›žæ•°é‡é™åˆ¶
            offset: åç§»é‡
            platform: è¿‡æ»¤å¹³å°
            agent_id: è¿‡æ»¤Agent
            round_num: è¿‡æ»¤è½®æ¬¡
            
        Returns:
            åŠ¨ä½œåˆ—è¡¨
        """
        actions = cls.get_all_actions(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )
        
        # åˆ†é¡µ
        return actions[offset:offset + limit]
    
    @classmethod
    def get_timeline(
        cls,
        simulation_id: str,
        start_round: int = 0,
        end_round: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        èŽ·å–æ¨¡æ‹Ÿæ—¶é—´çº¿ï¼ˆæŒ‰è½®æ¬¡æ±‡æ€»ï¼‰
        
        Args:
            simulation_id: æ¨¡æ‹ŸID
            start_round: èµ·å§‹è½®æ¬¡
            end_round: ç»“æŸè½®æ¬¡
            
        Returns:
            æ¯è½®çš„æ±‡æ€»ä¿¡æ¯
        """
        actions = cls.get_actions(simulation_id, limit=10000)
        
        # æŒ‰è½®æ¬¡åˆ†ç»„
        rounds: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            round_num = action.round_num
            
            if round_num < start_round:
                continue
            if end_round is not None and round_num > end_round:
                continue
            
            if round_num not in rounds:
                rounds[round_num] = {
                    "round_num": round_num,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "active_agents": set(),
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            r = rounds[round_num]
            
            if action.platform == "twitter":
                r["twitter_actions"] += 1
            else:
                r["reddit_actions"] += 1
            
            r["active_agents"].add(action.agent_id)
            r["action_types"][action.action_type] = r["action_types"].get(action.action_type, 0) + 1
            r["last_action_time"] = action.timestamp
        
        # è½¬æ¢ä¸ºåˆ—è¡¨
        result = []
        for round_num in sorted(rounds.keys()):
            r = rounds[round_num]
            result.append({
                "round_num": round_num,
                "twitter_actions": r["twitter_actions"],
                "reddit_actions": r["reddit_actions"],
                "total_actions": r["twitter_actions"] + r["reddit_actions"],
                "active_agents_count": len(r["active_agents"]),
                "active_agents": list(r["active_agents"]),
                "action_types": r["action_types"],
                "first_action_time": r["first_action_time"],
                "last_action_time": r["last_action_time"],
            })
        
        return result
    
    @classmethod
    def get_agent_stats(cls, simulation_id: str) -> List[Dict[str, Any]]:
        """
        èŽ·å–æ¯ä¸ªAgentçš„ç»Ÿè®¡ä¿¡æ¯
        
        Returns:
            Agentç»Ÿè®¡åˆ—è¡¨
        """
        actions = cls.get_actions(simulation_id, limit=10000)
        
        agent_stats: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            agent_id = action.agent_id
            
            if agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    "agent_id": agent_id,
                    "agent_name": action.agent_name,
                    "total_actions": 0,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            stats = agent_stats[agent_id]
            stats["total_actions"] += 1
            
            if action.platform == "twitter":
                stats["twitter_actions"] += 1
            else:
                stats["reddit_actions"] += 1
            
            stats["action_types"][action.action_type] = stats["action_types"].get(action.action_type, 0) + 1
            stats["last_action_time"] = action.timestamp
        
        # æŒ‰æ€»åŠ¨ä½œæ•°æŽ’åº
        result = sorted(agent_stats.values(), key=lambda x: x["total_actions"], reverse=True)
        
        return result
    
    @classmethod
    def cleanup_simulation_logs(cls, simulation_id: str) -> Dict[str, Any]:
        """
        æ¸…ç†æ¨¡æ‹Ÿçš„è¿è¡Œæ—¥å¿—ï¼ˆç”¨äºŽå¼ºåˆ¶é‡æ–°å¼€å§‹æ¨¡æ‹Ÿï¼‰
        
        ä¼šåˆ é™¤ä»¥ä¸‹æ–‡ä»¶ï¼š
        - run_state.json
        - twitter/actions.jsonl
        - reddit/actions.jsonl
        - simulation.log
        - stdout.log / stderr.log
        - twitter_simulation.dbï¼ˆæ¨¡æ‹Ÿæ•°æ®åº“ï¼‰
        - reddit_simulation.dbï¼ˆæ¨¡æ‹Ÿæ•°æ®åº“ï¼‰
        - env_status.jsonï¼ˆçŽ¯å¢ƒçŠ¶æ€ï¼‰
        
        æ³¨æ„ï¼šä¸ä¼šåˆ é™¤é…ç½®æ–‡ä»¶ï¼ˆsimulation_config.jsonï¼‰å’Œ profile æ–‡ä»¶
        
        Args:
            simulation_id: æ¨¡æ‹ŸID
            
        Returns:
            æ¸…ç†ç»“æžœä¿¡æ¯
        """
        import shutil
        
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        if not os.path.exists(sim_dir):
            return {"success": True, "message": "æ¨¡æ‹Ÿç›®å½•ä¸å­˜åœ¨ï¼Œæ— éœ€æ¸…ç†"}
        
        cleaned_files = []
        errors = []
        
        # è¦åˆ é™¤çš„æ–‡ä»¶åˆ—è¡¨ï¼ˆåŒ…æ‹¬æ•°æ®åº“æ–‡ä»¶ï¼‰
        files_to_delete = [
            "run_state.json",
            "simulation.log",
            "stdout.log",
            "stderr.log",
            "twitter_simulation.db",  # Twitter å¹³å°æ•°æ®åº“
            "reddit_simulation.db",   # Reddit å¹³å°æ•°æ®åº“
            "env_status.json",        # çŽ¯å¢ƒçŠ¶æ€æ–‡ä»¶
        ]
        
        # è¦åˆ é™¤çš„ç›®å½•åˆ—è¡¨ï¼ˆåŒ…å«åŠ¨ä½œæ—¥å¿—ï¼‰
        dirs_to_clean = ["twitter", "reddit"]
        
        # åˆ é™¤æ–‡ä»¶
        for filename in files_to_delete:
            file_path = os.path.join(sim_dir, filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    cleaned_files.append(filename)
                except Exception as e:
                    errors.append(f"åˆ é™¤ {filename} å¤±è´¥: {str(e)}")
        
        # æ¸…ç†å¹³å°ç›®å½•ä¸­çš„åŠ¨ä½œæ—¥å¿—
        for dir_name in dirs_to_clean:
            dir_path = os.path.join(sim_dir, dir_name)
            if os.path.exists(dir_path):
                actions_file = os.path.join(dir_path, "actions.jsonl")
                if os.path.exists(actions_file):
                    try:
                        os.remove(actions_file)
                        cleaned_files.append(f"{dir_name}/actions.jsonl")
                    except Exception as e:
                        errors.append(f"åˆ é™¤ {dir_name}/actions.jsonl å¤±è´¥: {str(e)}")
        
        # æ¸…ç†å†…å­˜ä¸­çš„è¿è¡ŒçŠ¶æ€
        if simulation_id in cls._run_states:
            del cls._run_states[simulation_id]
        
        logger.info(f"æ¸…ç†æ¨¡æ‹Ÿæ—¥å¿—å®Œæˆ: {simulation_id}, åˆ é™¤æ–‡ä»¶: {cleaned_files}")
        
        return {
            "success": len(errors) == 0,
            "cleaned_files": cleaned_files,
            "errors": errors if errors else None
        }
    
    # é˜²æ­¢é‡å¤æ¸…ç†çš„æ ‡å¿—
    _cleanup_done = False
    
    @classmethod
    def cleanup_all_simulations(cls):
        """
        æ¸…ç†æ‰€æœ‰è¿è¡Œä¸­çš„æ¨¡æ‹Ÿè¿›ç¨‹
        
        åœ¨æœåŠ¡å™¨å…³é—­æ—¶è°ƒç”¨ï¼Œç¡®ä¿æ‰€æœ‰å­è¿›ç¨‹è¢«ç»ˆæ­¢
        """
        # é˜²æ­¢é‡å¤æ¸…ç†
        if cls._cleanup_done:
            return
        cls._cleanup_done = True
        
        # æ£€æŸ¥æ˜¯å¦æœ‰å†…å®¹éœ€è¦æ¸…ç†ï¼ˆé¿å…ç©ºè¿›ç¨‹çš„è¿›ç¨‹æ‰“å°æ— ç”¨æ—¥å¿—ï¼‰
        has_processes = bool(cls._processes)
        has_updaters = bool(cls._graph_memory_enabled)
        
        if not has_processes and not has_updaters:
            return  # æ²¡æœ‰éœ€è¦æ¸…ç†çš„å†…å®¹ï¼Œé™é»˜è¿”å›ž
        
        logger.info("æ­£åœ¨æ¸…ç†æ‰€æœ‰æ¨¡æ‹Ÿè¿›ç¨‹...")
        
        # é¦–å…ˆåœæ­¢æ‰€æœ‰å›¾è°±è®°å¿†æ›´æ–°å™¨ï¼ˆstop_all å†…éƒ¨ä¼šæ‰“å°æ—¥å¿—ï¼‰
        try:
            ZepGraphMemoryManager.stop_all()
        except Exception as e:
            logger.error(f"åœæ­¢å›¾è°±è®°å¿†æ›´æ–°å™¨å¤±è´¥: {e}")
        cls._graph_memory_enabled.clear()
        
        # å¤åˆ¶å­—å…¸ä»¥é¿å…åœ¨è¿­ä»£æ—¶ä¿®æ”¹
        processes = list(cls._processes.items())
        
        for simulation_id, process in processes:
            try:
                if process.poll() is None:  # è¿›ç¨‹ä»åœ¨è¿è¡Œ
                    logger.info(f"ç»ˆæ­¢æ¨¡æ‹Ÿè¿›ç¨‹: {simulation_id}, pid={process.pid}")
                    
                    try:
                        # ä½¿ç”¨è·¨å¹³å°çš„è¿›ç¨‹ç»ˆæ­¢æ–¹æ³•
                        cls._terminate_process(process, simulation_id, timeout=5)
                    except (ProcessLookupError, OSError):
                        # è¿›ç¨‹å¯èƒ½å·²ç»ä¸å­˜åœ¨ï¼Œå°è¯•ç›´æŽ¥ç»ˆæ­¢
                        try:
                            process.terminate()
                            process.wait(timeout=3)
                        except Exception:
                            process.kill()
                    
                    # æ›´æ–° run_state.json
                    state = cls.get_run_state(simulation_id)
                    if state:
                        state.runner_status = RunnerStatus.STOPPED
                        state.twitter_running = False
                        state.reddit_running = False
                        state.completed_at = datetime.now().isoformat()
                        state.error = "æœåŠ¡å™¨å…³é—­ï¼Œæ¨¡æ‹Ÿè¢«ç»ˆæ­¢"
                        cls._save_run_state(state)
                    
                    # åŒæ—¶æ›´æ–° state.jsonï¼Œå°†çŠ¶æ€è®¾ä¸º stopped
                    try:
                        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
                        state_file = os.path.join(sim_dir, "state.json")
                        logger.info(f"å°è¯•æ›´æ–° state.json: {state_file}")
                        if os.path.exists(state_file):
                            with open(state_file, 'r', encoding='utf-8') as f:
                                state_data = json.load(f)
                            state_data['status'] = 'stopped'
                            state_data['updated_at'] = datetime.now().isoformat()
                            with open(state_file, 'w', encoding='utf-8') as f:
                                json.dump(state_data, f, indent=2, ensure_ascii=False)
                            logger.info(f"å·²æ›´æ–° state.json çŠ¶æ€ä¸º stopped: {simulation_id}")
                        else:
                            logger.warning(f"state.json ä¸å­˜åœ¨: {state_file}")
                    except Exception as state_err:
                        logger.warning(f"æ›´æ–° state.json å¤±è´¥: {simulation_id}, error={state_err}")
                        
            except Exception as e:
                logger.error(f"æ¸…ç†è¿›ç¨‹å¤±è´¥: {simulation_id}, error={e}")
        
        # æ¸…ç†æ–‡ä»¶å¥æŸ„
        for simulation_id, file_handle in list(cls._stdout_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stdout_files.clear()
        
        for simulation_id, file_handle in list(cls._stderr_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stderr_files.clear()
        
        # æ¸…ç†å†…å­˜ä¸­çš„çŠ¶æ€
        cls._processes.clear()
        cls._action_queues.clear()
        
        logger.info("æ¨¡æ‹Ÿè¿›ç¨‹æ¸…ç†å®Œæˆ")
    
    @classmethod
    def register_cleanup(cls):
        """
        æ³¨å†Œæ¸…ç†å‡½æ•°
        
        åœ¨ Flask åº”ç”¨å¯åŠ¨æ—¶è°ƒç”¨ï¼Œç¡®ä¿æœåŠ¡å™¨å…³é—­æ—¶æ¸…ç†æ‰€æœ‰æ¨¡æ‹Ÿè¿›ç¨‹
        """
        global _cleanup_registered
        
        if _cleanup_registered:
            return
        
        # Flask debug æ¨¡å¼ä¸‹ï¼Œåªåœ¨ reloader å­è¿›ç¨‹ä¸­æ³¨å†Œæ¸…ç†ï¼ˆå®žé™…è¿è¡Œåº”ç”¨çš„è¿›ç¨‹ï¼‰
        # WERKZEUG_RUN_MAIN=true è¡¨ç¤ºæ˜¯ reloader å­è¿›ç¨‹
        # å¦‚æžœä¸æ˜¯ debug æ¨¡å¼ï¼Œåˆ™æ²¡æœ‰è¿™ä¸ªçŽ¯å¢ƒå˜é‡ï¼Œä¹Ÿéœ€è¦æ³¨å†Œ
        is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        is_debug_mode = os.environ.get('FLASK_DEBUG') == '1' or os.environ.get('WERKZEUG_RUN_MAIN') is not None
        
        # åœ¨ debug æ¨¡å¼ä¸‹ï¼Œåªåœ¨ reloader å­è¿›ç¨‹ä¸­æ³¨å†Œï¼›éž debug æ¨¡å¼ä¸‹å§‹ç»ˆæ³¨å†Œ
        if is_debug_mode and not is_reloader_process:
            _cleanup_registered = True  # æ ‡è®°å·²æ³¨å†Œï¼Œé˜²æ­¢å­è¿›ç¨‹å†æ¬¡å°è¯•
            return
        
        # ä¿å­˜åŽŸæœ‰çš„ä¿¡å·å¤„ç†å™¨
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)
        # SIGHUP åªåœ¨ Unix ç³»ç»Ÿå­˜åœ¨ï¼ˆmacOS/Linuxï¼‰ï¼ŒWindows æ²¡æœ‰
        original_sighup = None
        has_sighup = hasattr(signal, 'SIGHUP')
        if has_sighup:
            original_sighup = signal.getsignal(signal.SIGHUP)
        
        def cleanup_handler(signum=None, frame=None):
            """ä¿¡å·å¤„ç†å™¨ï¼šå…ˆæ¸…ç†æ¨¡æ‹Ÿè¿›ç¨‹ï¼Œå†è°ƒç”¨åŽŸå¤„ç†å™¨"""
            # åªæœ‰åœ¨æœ‰è¿›ç¨‹éœ€è¦æ¸…ç†æ—¶æ‰æ‰“å°æ—¥å¿—
            if cls._processes or cls._graph_memory_enabled:
                logger.info(f"æ”¶åˆ°ä¿¡å· {signum}ï¼Œå¼€å§‹æ¸…ç†...")
            cls.cleanup_all_simulations()
            
            # è°ƒç”¨åŽŸæœ‰çš„ä¿¡å·å¤„ç†å™¨ï¼Œè®© Flask æ­£å¸¸é€€å‡º
            if signum == signal.SIGINT and callable(original_sigint):
                original_sigint(signum, frame)
            elif signum == signal.SIGTERM and callable(original_sigterm):
                original_sigterm(signum, frame)
            elif has_sighup and signum == signal.SIGHUP:
                # SIGHUP: ç»ˆç«¯å…³é—­æ—¶å‘é€
                if callable(original_sighup):
                    original_sighup(signum, frame)
                else:
                    # é»˜è®¤è¡Œä¸ºï¼šæ­£å¸¸é€€å‡º
                    sys.exit(0)
            else:
                # å¦‚æžœåŽŸå¤„ç†å™¨ä¸å¯è°ƒç”¨ï¼ˆå¦‚ SIG_DFLï¼‰ï¼Œåˆ™ä½¿ç”¨é»˜è®¤è¡Œä¸º
                raise KeyboardInterrupt
        
        # æ³¨å†Œ atexit å¤„ç†å™¨ï¼ˆä½œä¸ºå¤‡ç”¨ï¼‰
        atexit.register(cls.cleanup_all_simulations)
        
        # æ³¨å†Œä¿¡å·å¤„ç†å™¨ï¼ˆä»…åœ¨ä¸»çº¿ç¨‹ä¸­ï¼‰
        try:
            # SIGTERM: kill å‘½ä»¤é»˜è®¤ä¿¡å·
            signal.signal(signal.SIGTERM, cleanup_handler)
            # SIGINT: Ctrl+C
            signal.signal(signal.SIGINT, cleanup_handler)
            # SIGHUP: ç»ˆç«¯å…³é—­ï¼ˆä»… Unix ç³»ç»Ÿï¼‰
            if has_sighup:
                signal.signal(signal.SIGHUP, cleanup_handler)
        except ValueError:
            # ä¸åœ¨ä¸»çº¿ç¨‹ä¸­ï¼Œåªèƒ½ä½¿ç”¨ atexit
            logger.warning("æ— æ³•æ³¨å†Œä¿¡å·å¤„ç†å™¨ï¼ˆä¸åœ¨ä¸»çº¿ç¨‹ï¼‰ï¼Œä»…ä½¿ç”¨ atexit")
        
        _cleanup_registered = True
    
    @classmethod
    def get_running_simulations(cls) -> List[str]:
        """
        èŽ·å–æ‰€æœ‰æ­£åœ¨è¿è¡Œçš„æ¨¡æ‹ŸIDåˆ—è¡¨
        """
        running = []
        for sim_id, process in cls._processes.items():
            if process.poll() is None:
                running.append(sim_id)
        return running
    
    # ============== Interview åŠŸèƒ½ ==============
    
    @classmethod
    def check_env_alive(cls, simulation_id: str) -> bool:
        """
        æ£€æŸ¥æ¨¡æ‹ŸçŽ¯å¢ƒæ˜¯å¦å­˜æ´»ï¼ˆå¯ä»¥æŽ¥æ”¶Interviewå‘½ä»¤ï¼‰

        Args:
            simulation_id: æ¨¡æ‹ŸID

        Returns:
            True è¡¨ç¤ºçŽ¯å¢ƒå­˜æ´»ï¼ŒFalse è¡¨ç¤ºçŽ¯å¢ƒå·²å…³é—­
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return False

        ipc_client = SimulationIPCClient(sim_dir)
        return ipc_client.check_env_alive()

    @classmethod
    def get_env_status_detail(cls, simulation_id: str) -> Dict[str, Any]:
        """
        èŽ·å–æ¨¡æ‹ŸçŽ¯å¢ƒçš„è¯¦ç»†çŠ¶æ€ä¿¡æ¯

        Args:
            simulation_id: æ¨¡æ‹ŸID

        Returns:
            çŠ¶æ€è¯¦æƒ…å­—å…¸ï¼ŒåŒ…å« status, twitter_available, reddit_available, timestamp
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        status_file = os.path.join(sim_dir, "env_status.json")
        
        default_status = {
            "status": "stopped",
            "twitter_available": False,
            "reddit_available": False,
            "timestamp": None
        }
        
        if not os.path.exists(status_file):
            return default_status
        
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            return {
                "status": status.get("status", "stopped"),
                "twitter_available": status.get("twitter_available", False),
                "reddit_available": status.get("reddit_available", False),
                "timestamp": status.get("timestamp")
            }
        except (json.JSONDecodeError, OSError):
            return default_status

    @classmethod
    def interview_agent(
        cls,
        simulation_id: str,
        agent_id: int,
        prompt: str,
        platform: str = None,
        timeout: float = 60.0
    ) -> Dict[str, Any]:
        """
        é‡‡è®¿å•ä¸ªAgent

        Args:
            simulation_id: æ¨¡æ‹ŸID
            agent_id: Agent ID
            prompt: é‡‡è®¿é—®é¢˜
            platform: æŒ‡å®šå¹³å°ï¼ˆå¯é€‰ï¼‰
                - "twitter": åªé‡‡è®¿Twitterå¹³å°
                - "reddit": åªé‡‡è®¿Redditå¹³å°
                - None: åŒå¹³å°æ¨¡æ‹Ÿæ—¶åŒæ—¶é‡‡è®¿ä¸¤ä¸ªå¹³å°ï¼Œè¿”å›žæ•´åˆç»“æžœ
            timeout: è¶…æ—¶æ—¶é—´ï¼ˆç§’ï¼‰

        Returns:
            é‡‡è®¿ç»“æžœå­—å…¸

        Raises:
            ValueError: æ¨¡æ‹Ÿä¸å­˜åœ¨æˆ–çŽ¯å¢ƒæœªè¿è¡Œ
            TimeoutError: ç­‰å¾…å“åº”è¶…æ—¶
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"æ¨¡æ‹Ÿä¸å­˜åœ¨: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(f"æ¨¡æ‹ŸçŽ¯å¢ƒæœªè¿è¡Œæˆ–å·²å…³é—­ï¼Œæ— æ³•æ‰§è¡ŒInterview: {simulation_id}")

        logger.info(f"å‘é€Interviewå‘½ä»¤: simulation_id={simulation_id}, agent_id={agent_id}, platform={platform}")

        response = ipc_client.send_interview(
            agent_id=agent_id,
            prompt=prompt,
            platform=platform,
            timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "agent_id": agent_id,
                "prompt": prompt,
                "result": response.result,
                "timestamp": response.timestamp
            }
        else:
            return {
                "success": False,
                "agent_id": agent_id,
                "prompt": prompt,
                "error": response.error,
                "timestamp": response.timestamp
            }
    
    @classmethod
    def interview_agents_batch(
        cls,
        simulation_id: str,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """
        æ‰¹é‡é‡‡è®¿å¤šä¸ªAgent

        Args:
            simulation_id: æ¨¡æ‹ŸID
            interviews: é‡‡è®¿åˆ—è¡¨ï¼Œæ¯ä¸ªå…ƒç´ åŒ…å« {"agent_id": int, "prompt": str, "platform": str(å¯é€‰)}
            platform: é»˜è®¤å¹³å°ï¼ˆå¯é€‰ï¼Œä¼šè¢«æ¯ä¸ªé‡‡è®¿é¡¹çš„platformè¦†ç›–ï¼‰
                - "twitter": é»˜è®¤åªé‡‡è®¿Twitterå¹³å°
                - "reddit": é»˜è®¤åªé‡‡è®¿Redditå¹³å°
                - None: åŒå¹³å°æ¨¡æ‹Ÿæ—¶æ¯ä¸ªAgentåŒæ—¶é‡‡è®¿ä¸¤ä¸ªå¹³å°
            timeout: è¶…æ—¶æ—¶é—´ï¼ˆç§’ï¼‰

        Returns:
            æ‰¹é‡é‡‡è®¿ç»“æžœå­—å…¸

        Raises:
            ValueError: æ¨¡æ‹Ÿä¸å­˜åœ¨æˆ–çŽ¯å¢ƒæœªè¿è¡Œ
            TimeoutError: ç­‰å¾…å“åº”è¶…æ—¶
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"æ¨¡æ‹Ÿä¸å­˜åœ¨: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(f"æ¨¡æ‹ŸçŽ¯å¢ƒæœªè¿è¡Œæˆ–å·²å…³é—­ï¼Œæ— æ³•æ‰§è¡ŒInterview: {simulation_id}")

        logger.info(f"å‘é€æ‰¹é‡Interviewå‘½ä»¤: simulation_id={simulation_id}, count={len(interviews)}, platform={platform}")

        response = ipc_client.send_batch_interview(
            interviews=interviews,
            platform=platform,
            timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "interviews_count": len(interviews),
                "result": response.result,
                "timestamp": response.timestamp
            }
        else:
            return {
                "success": False,
                "interviews_count": len(interviews),
                "error": response.error,
                "timestamp": response.timestamp
            }
    
    @classmethod
    def interview_all_agents(
        cls,
        simulation_id: str,
        prompt: str,
        platform: str = None,
        timeout: float = 180.0
    ) -> Dict[str, Any]:
        """
        é‡‡è®¿æ‰€æœ‰Agentï¼ˆå…¨å±€é‡‡è®¿ï¼‰

        ä½¿ç”¨ç›¸åŒçš„é—®é¢˜é‡‡è®¿æ¨¡æ‹Ÿä¸­çš„æ‰€æœ‰Agent

        Args:
            simulation_id: æ¨¡æ‹ŸID
            prompt: é‡‡è®¿é—®é¢˜ï¼ˆæ‰€æœ‰Agentä½¿ç”¨ç›¸åŒé—®é¢˜ï¼‰
            platform: æŒ‡å®šå¹³å°ï¼ˆå¯é€‰ï¼‰
                - "twitter": åªé‡‡è®¿Twitterå¹³å°
                - "reddit": åªé‡‡è®¿Redditå¹³å°
                - None: åŒå¹³å°æ¨¡æ‹Ÿæ—¶æ¯ä¸ªAgentåŒæ—¶é‡‡è®¿ä¸¤ä¸ªå¹³å°
            timeout: è¶…æ—¶æ—¶é—´ï¼ˆç§’ï¼‰

        Returns:
            å…¨å±€é‡‡è®¿ç»“æžœå­—å…¸
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"æ¨¡æ‹Ÿä¸å­˜åœ¨: {simulation_id}")

        # ä»Žé…ç½®æ–‡ä»¶èŽ·å–æ‰€æœ‰Agentä¿¡æ¯
        config_path = os.path.join(sim_dir, "simulation_config.json")
        if not os.path.exists(config_path):
            raise ValueError(f"æ¨¡æ‹Ÿé…ç½®ä¸å­˜åœ¨: {simulation_id}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        agent_configs = config.get("agent_configs", [])
        if not agent_configs:
            raise ValueError(f"æ¨¡æ‹Ÿé…ç½®ä¸­æ²¡æœ‰Agent: {simulation_id}")

        # æž„å»ºæ‰¹é‡é‡‡è®¿åˆ—è¡¨
        interviews = []
        for agent_config in agent_configs:
            agent_id = agent_config.get("agent_id")
            if agent_id is not None:
                interviews.append({
                    "agent_id": agent_id,
                    "prompt": prompt
                })

        logger.info(f"å‘é€å…¨å±€Interviewå‘½ä»¤: simulation_id={simulation_id}, agent_count={len(interviews)}, platform={platform}")

        return cls.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=interviews,
            platform=platform,
            timeout=timeout
        )
    
    @classmethod
    def close_simulation_env(
        cls,
        simulation_id: str,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        å…³é—­æ¨¡æ‹ŸçŽ¯å¢ƒï¼ˆè€Œä¸æ˜¯åœæ­¢æ¨¡æ‹Ÿè¿›ç¨‹ï¼‰
        
        å‘æ¨¡æ‹Ÿå‘é€å…³é—­çŽ¯å¢ƒå‘½ä»¤ï¼Œä½¿å…¶ä¼˜é›…é€€å‡ºç­‰å¾…å‘½ä»¤æ¨¡å¼
        
        Args:
            simulation_id: æ¨¡æ‹ŸID
            timeout: è¶…æ—¶æ—¶é—´ï¼ˆç§’ï¼‰
            
        Returns:
            æ“ä½œç»“æžœå­—å…¸
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"æ¨¡æ‹Ÿä¸å­˜åœ¨: {simulation_id}")
        
        ipc_client = SimulationIPCClient(sim_dir)
        
        if not ipc_client.check_env_alive():
            return {
                "success": True,
                "message": "çŽ¯å¢ƒå·²ç»å…³é—­"
            }
        
        logger.info(f"å‘é€å…³é—­çŽ¯å¢ƒå‘½ä»¤: simulation_id={simulation_id}")
        
        try:
            response = ipc_client.send_close_env(timeout=timeout)
            
            return {
                "success": response.status.value == "completed",
                "message": "çŽ¯å¢ƒå…³é—­å‘½ä»¤å·²å‘é€",
                "result": response.result,
                "timestamp": response.timestamp
            }
        except TimeoutError:
            # è¶…æ—¶å¯èƒ½æ˜¯å› ä¸ºçŽ¯å¢ƒæ­£åœ¨å…³é—­
            return {
                "success": True,
                "message": "çŽ¯å¢ƒå…³é—­å‘½ä»¤å·²å‘é€ï¼ˆç­‰å¾…å“åº”è¶…æ—¶ï¼ŒçŽ¯å¢ƒå¯èƒ½æ­£åœ¨å…³é—­ï¼‰"
            }
    
    @classmethod
    def _get_interview_history_from_db(
        cls,
        db_path: str,
        platform_name: str,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """ä»Žå•ä¸ªæ•°æ®åº“èŽ·å–InterviewåŽ†å²"""
        import sqlite3
        
        if not os.path.exists(db_path):
            return []
        
        results = []
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if agent_id is not None:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview' AND user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (agent_id, limit))
            else:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview'
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            
            for user_id, info_json, created_at in cursor.fetchall():
                try:
                    info = json.loads(info_json) if info_json else {}
                except json.JSONDecodeError:
                    info = {"raw": info_json}
                
                results.append({
                    "agent_id": user_id,
                    "response": info.get("response", info),
                    "prompt": info.get("prompt", ""),
                    "timestamp": created_at,
                    "platform": platform_name
                })
            
            conn.close()
            
        except Exception as e:
            logger.error(f"è¯»å–InterviewåŽ†å²å¤±è´¥ ({platform_name}): {e}")
        
        return results

    @classmethod
    def get_interview_history(
        cls,
        simulation_id: str,
        platform: str = None,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        èŽ·å–InterviewåŽ†å²è®°å½•ï¼ˆä»Žæ•°æ®åº“è¯»å–ï¼‰
        
        Args:
            simulation_id: æ¨¡æ‹ŸID
            platform: å¹³å°ç±»åž‹ï¼ˆreddit/twitter/Noneï¼‰
                - "reddit": åªèŽ·å–Redditå¹³å°çš„åŽ†å²
                - "twitter": åªèŽ·å–Twitterå¹³å°çš„åŽ†å²
                - None: èŽ·å–ä¸¤ä¸ªå¹³å°çš„æ‰€æœ‰åŽ†å²
            agent_id: æŒ‡å®šAgent IDï¼ˆå¯é€‰ï¼ŒåªèŽ·å–è¯¥Agentçš„åŽ†å²ï¼‰
            limit: æ¯ä¸ªå¹³å°è¿”å›žæ•°é‡é™åˆ¶
            
        Returns:
            InterviewåŽ†å²è®°å½•åˆ—è¡¨
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        results = []
        
        # ç¡®å®šè¦æŸ¥è¯¢çš„å¹³å°
        if platform in ("reddit", "twitter"):
            platforms = [platform]
        else:
            # ä¸æŒ‡å®šplatformæ—¶ï¼ŒæŸ¥è¯¢ä¸¤ä¸ªå¹³å°
            platforms = ["twitter", "reddit"]
        
        for p in platforms:
            db_path = os.path.join(sim_dir, f"{p}_simulation.db")
            platform_results = cls._get_interview_history_from_db(
                db_path=db_path,
                platform_name=p,
                agent_id=agent_id,
                limit=limit
            )
            results.extend(platform_results)
        
        # æŒ‰æ—¶é—´é™åºæŽ’åº
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # å¦‚æžœæŸ¥è¯¢äº†å¤šä¸ªå¹³å°ï¼Œé™åˆ¶æ€»æ•°
        if len(platforms) > 1 and len(results) > limit:
            results = results[:limit]
        
        return results


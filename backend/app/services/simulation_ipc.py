"""
æ¨¡æ‹ŸIPCé€šä¿¡æ¨¡å—
ç”¨äºŽFlaskåŽç«¯å’Œæ¨¡æ‹Ÿè„šæœ¬ä¹‹é—´çš„è¿›ç¨‹é—´é€šä¿¡

é€šè¿‡æ–‡ä»¶ç³»ç»Ÿå®žçŽ°ç®€å•çš„å‘½ä»¤/å“åº”æ¨¡å¼ï¼š
1. Flaskå†™å…¥å‘½ä»¤åˆ° commands/ ç›®å½•
2. æ¨¡æ‹Ÿè„šæœ¬è½®è¯¢å‘½ä»¤ç›®å½•ï¼Œæ‰§è¡Œå‘½ä»¤å¹¶å†™å…¥å“åº”åˆ° responses/ ç›®å½•
3. Flaskè½®è¯¢å“åº”ç›®å½•èŽ·å–ç»“æžœ
"""

import os
import json
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger('posiedon.simulation_ipc')


class CommandType(str, Enum):
    """å‘½ä»¤ç±»åž‹"""
    INTERVIEW = "interview"           # å•ä¸ªAgenté‡‡è®¿
    BATCH_INTERVIEW = "batch_interview"  # æ‰¹é‡é‡‡è®¿
    CLOSE_ENV = "close_env"           # å…³é—­çŽ¯å¢ƒ


class CommandStatus(str, Enum):
    """å‘½ä»¤çŠ¶æ€"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IPCCommand:
    """IPCå‘½ä»¤"""
    command_id: str
    command_type: CommandType
    args: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "command_type": self.command_type.value,
            "args": self.args,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCCommand':
        return cls(
            command_id=data["command_id"],
            command_type=CommandType(data["command_type"]),
            args=data.get("args", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


@dataclass
class IPCResponse:
    """IPCå“åº”"""
    command_id: str
    status: CommandStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCResponse':
        return cls(
            command_id=data["command_id"],
            status=CommandStatus(data["status"]),
            result=data.get("result"),
            error=data.get("error"),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


class SimulationIPCClient:
    """
    æ¨¡æ‹ŸIPCå®¢æˆ·ç«¯ï¼ˆFlaskç«¯ä½¿ç”¨ï¼‰
    
    ç”¨äºŽå‘æ¨¡æ‹Ÿè¿›ç¨‹å‘é€å‘½ä»¤å¹¶ç­‰å¾…å“åº”
    """
    
    def __init__(self, simulation_dir: str):
        """
        åˆå§‹åŒ–IPCå®¢æˆ·ç«¯
        
        Args:
            simulation_dir: æ¨¡æ‹Ÿæ•°æ®ç›®å½•
        """
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")
        
        # ç¡®ä¿ç›®å½•å­˜åœ¨
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
    
    def send_command(
        self,
        command_type: CommandType,
        args: Dict[str, Any],
        timeout: float = 60.0,
        poll_interval: float = 0.5
    ) -> IPCResponse:
        """
        å‘é€å‘½ä»¤å¹¶ç­‰å¾…å“åº”
        
        Args:
            command_type: å‘½ä»¤ç±»åž‹
            args: å‘½ä»¤å‚æ•°
            timeout: è¶…æ—¶æ—¶é—´ï¼ˆç§’ï¼‰
            poll_interval: è½®è¯¢é—´éš”ï¼ˆç§’ï¼‰
            
        Returns:
            IPCResponse
            
        Raises:
            TimeoutError: ç­‰å¾…å“åº”è¶…æ—¶
        """
        command_id = str(uuid.uuid4())
        command = IPCCommand(
            command_id=command_id,
            command_type=command_type,
            args=args
        )
        
        # å†™å…¥å‘½ä»¤æ–‡ä»¶
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        with open(command_file, 'w', encoding='utf-8') as f:
            json.dump(command.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"å‘é€IPCå‘½ä»¤: {command_type.value}, command_id={command_id}")
        
        # ç­‰å¾…å“åº”
        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if os.path.exists(response_file):
                try:
                    with open(response_file, 'r', encoding='utf-8') as f:
                        response_data = json.load(f)
                    response = IPCResponse.from_dict(response_data)
                    
                    # æ¸…ç†å‘½ä»¤å’Œå“åº”æ–‡ä»¶
                    try:
                        os.remove(command_file)
                        os.remove(response_file)
                    except OSError:
                        pass
                    
                    logger.info(f"æ”¶åˆ°IPCå“åº”: command_id={command_id}, status={response.status.value}")
                    return response
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"è§£æžå“åº”å¤±è´¥: {e}")
            
            time.sleep(poll_interval)
        
        # è¶…æ—¶
        logger.error(f"ç­‰å¾…IPCå“åº”è¶…æ—¶: command_id={command_id}")
        
        # æ¸…ç†å‘½ä»¤æ–‡ä»¶
        try:
            os.remove(command_file)
        except OSError:
            pass
        
        raise TimeoutError(f"ç­‰å¾…å‘½ä»¤å“åº”è¶…æ—¶ ({timeout}ç§’)")
    
    def send_interview(
        self,
        agent_id: int,
        prompt: str,
        platform: str = None,
        timeout: float = 60.0
    ) -> IPCResponse:
        """
        å‘é€å•ä¸ªAgenté‡‡è®¿å‘½ä»¤
        
        Args:
            agent_id: Agent ID
            prompt: é‡‡è®¿é—®é¢˜
            platform: æŒ‡å®šå¹³å°ï¼ˆå¯é€‰ï¼‰
                - "twitter": åªé‡‡è®¿Twitterå¹³å°
                - "reddit": åªé‡‡è®¿Redditå¹³å°  
                - None: åŒå¹³å°æ¨¡æ‹Ÿæ—¶åŒæ—¶é‡‡è®¿ä¸¤ä¸ªå¹³å°ï¼Œå•å¹³å°æ¨¡æ‹Ÿæ—¶é‡‡è®¿è¯¥å¹³å°
            timeout: è¶…æ—¶æ—¶é—´
            
        Returns:
            IPCResponseï¼Œresultå­—æ®µåŒ…å«é‡‡è®¿ç»“æžœ
        """
        args = {
            "agent_id": agent_id,
            "prompt": prompt
        }
        if platform:
            args["platform"] = platform
            
        return self.send_command(
            command_type=CommandType.INTERVIEW,
            args=args,
            timeout=timeout
        )
    
    def send_batch_interview(
        self,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 120.0
    ) -> IPCResponse:
        """
        å‘é€æ‰¹é‡é‡‡è®¿å‘½ä»¤
        
        Args:
            interviews: é‡‡è®¿åˆ—è¡¨ï¼Œæ¯ä¸ªå…ƒç´ åŒ…å« {"agent_id": int, "prompt": str, "platform": str(å¯é€‰)}
            platform: é»˜è®¤å¹³å°ï¼ˆå¯é€‰ï¼Œä¼šè¢«æ¯ä¸ªé‡‡è®¿é¡¹çš„platformè¦†ç›–ï¼‰
                - "twitter": é»˜è®¤åªé‡‡è®¿Twitterå¹³å°
                - "reddit": é»˜è®¤åªé‡‡è®¿Redditå¹³å°
                - None: åŒå¹³å°æ¨¡æ‹Ÿæ—¶æ¯ä¸ªAgentåŒæ—¶é‡‡è®¿ä¸¤ä¸ªå¹³å°
            timeout: è¶…æ—¶æ—¶é—´
            
        Returns:
            IPCResponseï¼Œresultå­—æ®µåŒ…å«æ‰€æœ‰é‡‡è®¿ç»“æžœ
        """
        args = {"interviews": interviews}
        if platform:
            args["platform"] = platform
            
        return self.send_command(
            command_type=CommandType.BATCH_INTERVIEW,
            args=args,
            timeout=timeout
        )
    
    def send_close_env(self, timeout: float = 30.0) -> IPCResponse:
        """
        å‘é€å…³é—­çŽ¯å¢ƒå‘½ä»¤
        
        Args:
            timeout: è¶…æ—¶æ—¶é—´
            
        Returns:
            IPCResponse
        """
        return self.send_command(
            command_type=CommandType.CLOSE_ENV,
            args={},
            timeout=timeout
        )
    
    def check_env_alive(self) -> bool:
        """
        æ£€æŸ¥æ¨¡æ‹ŸçŽ¯å¢ƒæ˜¯å¦å­˜æ´»
        
        é€šè¿‡æ£€æŸ¥ env_status.json æ–‡ä»¶æ¥åˆ¤æ–­
        """
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        if not os.path.exists(status_file):
            return False
        
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            return status.get("status") == "alive"
        except (json.JSONDecodeError, OSError):
            return False


class SimulationIPCServer:
    """
    æ¨¡æ‹ŸIPCæœåŠ¡å™¨ï¼ˆæ¨¡æ‹Ÿè„šæœ¬ç«¯ä½¿ç”¨ï¼‰
    
    è½®è¯¢å‘½ä»¤ç›®å½•ï¼Œæ‰§è¡Œå‘½ä»¤å¹¶è¿”å›žå“åº”
    """
    
    def __init__(self, simulation_dir: str):
        """
        åˆå§‹åŒ–IPCæœåŠ¡å™¨
        
        Args:
            simulation_dir: æ¨¡æ‹Ÿæ•°æ®ç›®å½•
        """
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")
        
        # ç¡®ä¿ç›®å½•å­˜åœ¨
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
        
        # çŽ¯å¢ƒçŠ¶æ€
        self._running = False
    
    def start(self):
        """æ ‡è®°æœåŠ¡å™¨ä¸ºè¿è¡ŒçŠ¶æ€"""
        self._running = True
        self._update_env_status("alive")
    
    def stop(self):
        """æ ‡è®°æœåŠ¡å™¨ä¸ºåœæ­¢çŠ¶æ€"""
        self._running = False
        self._update_env_status("stopped")
    
    def _update_env_status(self, status: str):
        """æ›´æ–°çŽ¯å¢ƒçŠ¶æ€æ–‡ä»¶"""
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "status": status,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def poll_commands(self) -> Optional[IPCCommand]:
        """
        è½®è¯¢å‘½ä»¤ç›®å½•ï¼Œè¿”å›žç¬¬ä¸€ä¸ªå¾…å¤„ç†çš„å‘½ä»¤
        
        Returns:
            IPCCommand æˆ– None
        """
        if not os.path.exists(self.commands_dir):
            return None
        
        # æŒ‰æ—¶é—´æŽ’åºèŽ·å–å‘½ä»¤æ–‡ä»¶
        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.commands_dir, filename)
                command_files.append((filepath, os.path.getmtime(filepath)))
        
        command_files.sort(key=lambda x: x[1])
        
        for filepath, _ in command_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return IPCCommand.from_dict(data)
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"è¯»å–å‘½ä»¤æ–‡ä»¶å¤±è´¥: {filepath}, {e}")
                continue
        
        return None
    
    def send_response(self, response: IPCResponse):
        """
        å‘é€å“åº”
        
        Args:
            response: IPCå“åº”
        """
        response_file = os.path.join(self.responses_dir, f"{response.command_id}.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response.to_dict(), f, ensure_ascii=False, indent=2)
        
        # åˆ é™¤å‘½ä»¤æ–‡ä»¶
        command_file = os.path.join(self.commands_dir, f"{response.command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass
    
    def send_success(self, command_id: str, result: Dict[str, Any]):
        """å‘é€æˆåŠŸå“åº”"""
        self.send_response(IPCResponse(
            command_id=command_id,
            status=CommandStatus.COMPLETED,
            result=result
        ))
    
    def send_error(self, command_id: str, error: str):
        """å‘é€é”™è¯¯å“åº”"""
        self.send_response(IPCResponse(
            command_id=command_id,
            status=CommandStatus.FAILED,
            error=error
        ))

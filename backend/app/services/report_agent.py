"""

"""

import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from ..utils.locale import get_language_instruction, t
from .zep_tools import (
    ZepToolsService, 
    SearchResult, 
    InsightForgeResult, 
    PanoramaResult,
    InterviewResult
)

logger = get_logger('posiedon.report_agent')


class ReportLogger:
    """
    
    """
    
    def __init__(self, report_id: str):
        """
        
        Args:
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'agent_log.jsonl'
        )
        self.start_time = datetime.now()
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """ç¡®ä¿æ—¥å¿—æ–‡ä»¶æ‰€åœ¨ç›®å½•å­˜åœ¨"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _get_elapsed_time(self) -> float:
        """èŽ·å–ä»Žå¼€å§‹åˆ°çŽ°åœ¨çš„è€—æ—¶ï¼ˆç§’ï¼‰"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def log(
        self, 
        action: str, 
        stage: str,
        details: Dict[str, Any],
        section_title: str = None,
        section_index: int = None
    ):
        """
        
        Args:
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(self._get_elapsed_time(), 2),
            "report_id": self.report_id,
            "action": action,
            "stage": stage,
            "section_title": section_title,
            "section_index": section_index,
            "details": details
        }
        
        with open(self.log_file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def log_start(self, simulation_id: str, graph_id: str, simulation_requirement: str):
        """è®°å½•æŠ¥å‘Šç”Ÿæˆå¼€å§‹"""
        self.log(
            action="report_start",
            stage="pending",
            details={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "simulation_requirement": simulation_requirement,
                "message": t('report.taskStarted')
            }
        )
    
    def log_planning_start(self):
        """è®°å½•å¤§çº²è§„åˆ’å¼€å§‹"""
        self.log(
            action="planning_start",
            stage="planning",
            details={"message": t('report.planningStart')}
        )
    
    def log_planning_context(self, context: Dict[str, Any]):
        """è®°å½•è§„åˆ’æ—¶èŽ·å–çš„ä¸Šä¸‹æ–‡ä¿¡æ¯"""
        self.log(
            action="planning_context",
            stage="planning",
            details={
                "message": t('report.fetchSimContext'),
                "context": context
            }
        )
    
    def log_planning_complete(self, outline_dict: Dict[str, Any]):
        """è®°å½•å¤§çº²è§„åˆ’å®Œæˆ"""
        self.log(
            action="planning_complete",
            stage="planning",
            details={
                "message": t('report.planningComplete'),
                "outline": outline_dict
            }
        )
    
    def log_section_start(self, section_title: str, section_index: int):
        """è®°å½•ç« èŠ‚ç”Ÿæˆå¼€å§‹"""
        self.log(
            action="section_start",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={"message": t('report.sectionStart', title=section_title)}
        )
    
    def log_react_thought(self, section_title: str, section_index: int, iteration: int, thought: str):
        """è®°å½• ReACT æ€è€ƒè¿‡ç¨‹"""
        self.log(
            action="react_thought",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "thought": thought,
                "message": t('report.reactThought', iteration=iteration)
            }
        )
    
    def log_tool_call(
        self, 
        section_title: str, 
        section_index: int,
        tool_name: str, 
        parameters: Dict[str, Any],
        iteration: int
    ):
        """è®°å½•å·¥å…·è°ƒç”¨"""
        self.log(
            action="tool_call",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "parameters": parameters,
                "message": t('report.toolCall', toolName=tool_name)
            }
        )
    
    def log_tool_result(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        result: str,
        iteration: int
    ):
        """è®°å½•å·¥å…·è°ƒç”¨ç»“æžœï¼ˆå®Œæ•´å†…å®¹ï¼Œä¸æˆªæ–­ï¼‰"""
        self.log(
            action="tool_result",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "result": result,  # å®Œæ•´ç»“æžœï¼Œä¸æˆªæ–­
                "result_length": len(result),
                "message": t('report.toolResult', toolName=tool_name)
            }
        )
    
    def log_llm_response(
        self,
        section_title: str,
        section_index: int,
        response: str,
        iteration: int,
        has_tool_calls: bool,
        has_final_answer: bool
    ):
        """è®°å½• LLM å“åº”ï¼ˆå®Œæ•´å†…å®¹ï¼Œä¸æˆªæ–­ï¼‰"""
        self.log(
            action="llm_response",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "response": response,  # å®Œæ•´å“åº”ï¼Œä¸æˆªæ–­
                "response_length": len(response),
                "has_tool_calls": has_tool_calls,
                "has_final_answer": has_final_answer,
                "message": t('report.llmResponse', hasToolCalls=has_tool_calls, hasFinalAnswer=has_final_answer)
            }
        )
    
    def log_section_content(
        self,
        section_title: str,
        section_index: int,
        content: str,
        tool_calls_count: int
    ):
        """è®°å½•ç« èŠ‚å†…å®¹ç”Ÿæˆå®Œæˆï¼ˆä»…è®°å½•å†…å®¹ï¼Œä¸ä»£è¡¨æ•´ä¸ªç« èŠ‚å®Œæˆï¼‰"""
        self.log(
            action="section_content",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": content,  # å®Œæ•´å†…å®¹ï¼Œä¸æˆªæ–­
                "content_length": len(content),
                "tool_calls_count": tool_calls_count,
                "message": t('report.sectionContentDone', title=section_title)
            }
        )
    
    def log_section_full_complete(
        self,
        section_title: str,
        section_index: int,
        full_content: str
    ):
        """

        """
        self.log(
            action="section_complete",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": full_content,
                "content_length": len(full_content),
                "message": t('report.sectionComplete', title=section_title)
            }
        )
    
    def log_report_complete(self, total_sections: int, total_time_seconds: float):
        """è®°å½•æŠ¥å‘Šç”Ÿæˆå®Œæˆ"""
        self.log(
            action="report_complete",
            stage="completed",
            details={
                "total_sections": total_sections,
                "total_time_seconds": round(total_time_seconds, 2),
                "message": t('report.reportComplete')
            }
        )
    
    def log_error(self, error_message: str, stage: str, section_title: str = None):
        """è®°å½•é”™è¯¯"""
        self.log(
            action="error",
            stage=stage,
            section_title=section_title,
            section_index=None,
            details={
                "error": error_message,
                "message": t('report.errorOccurred', error=error_message)
            }
        )


class ReportConsoleLogger:
    """
    
    """
    
    def __init__(self, report_id: str):
        """
        
        Args:
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'console_log.txt'
        )
        self._ensure_log_file()
        self._file_handler = None
        self._setup_file_handler()
    
    def _ensure_log_file(self):
        """ç¡®ä¿æ—¥å¿—æ–‡ä»¶æ‰€åœ¨ç›®å½•å­˜åœ¨"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _setup_file_handler(self):
        """è®¾ç½®æ–‡ä»¶å¤„ç†å™¨ï¼Œå°†æ—¥å¿—åŒæ—¶å†™å…¥æ–‡ä»¶"""
        import logging
        
        self._file_handler = logging.FileHandler(
            self.log_file_path,
            mode='a',
            encoding='utf-8'
        )
        self._file_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        self._file_handler.setFormatter(formatter)
        
        loggers_to_attach = [
            'posiedon.report_agent',
            'posiedon.zep_tools',
        ]
        
        for logger_name in loggers_to_attach:
            target_logger = logging.getLogger(logger_name)
            if self._file_handler not in target_logger.handlers:
                target_logger.addHandler(self._file_handler)
    
    def close(self):
        """å…³é—­æ–‡ä»¶å¤„ç†å™¨å¹¶ä»Ž logger ä¸­ç§»é™¤"""
        import logging
        
        if self._file_handler:
            loggers_to_detach = [
                'posiedon.report_agent',
                'posiedon.zep_tools',
            ]
            
            for logger_name in loggers_to_detach:
                target_logger = logging.getLogger(logger_name)
                if self._file_handler in target_logger.handlers:
                    target_logger.removeHandler(self._file_handler)
            
            self._file_handler.close()
            self._file_handler = None
    
    def __del__(self):
        """æžæž„æ—¶ç¡®ä¿å…³é—­æ–‡ä»¶å¤„ç†å™¨"""
        self.close()


class ReportStatus(str, Enum):
    """æŠ¥å‘ŠçŠ¶æ€"""
    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """æŠ¥å‘Šç« èŠ‚"""
    title: str
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content
        }

    def to_markdown(self, level: int = 2) -> str:
        """è½¬æ¢ä¸ºMarkdownæ ¼å¼"""
        md = f"{'#' * level} {self.title}\n\n"
        if self.content:
            md += f"{self.content}\n\n"
        return md


@dataclass
class ReportOutline:
    """æŠ¥å‘Šå¤§çº²"""
    title: str
    summary: str
    sections: List[ReportSection]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections]
        }
    
    def to_markdown(self) -> str:
        """è½¬æ¢ä¸ºMarkdownæ ¼å¼"""
        md = f"# {self.title}\n\n"
        md += f"> {self.summary}\n\n"
        for section in self.sections:
            md += section.to_markdown()
        return md


@dataclass
class Report:
    """å®Œæ•´æŠ¥å‘Š"""
    report_id: str
    simulation_id: str
    graph_id: str
    simulation_requirement: str
    status: ReportStatus
    outline: Optional[ReportOutline] = None
    markdown_content: str = ""
    created_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "status": self.status.value,
            "outline": self.outline.to_dict() if self.outline else None,
            "markdown_content": self.markdown_content,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error
        }




TOOL_DESC_INSIGHT_FORGE = """\
ã€æ·±åº¦æ´žå¯Ÿæ£€ç´¢ - å¼ºå¤§çš„æ£€ç´¢å·¥å…·ã€‘
è¿™æ˜¯æˆ‘ä»¬å¼ºå¤§çš„æ£€ç´¢å‡½æ•°ï¼Œä¸“ä¸ºæ·±åº¦åˆ†æžè®¾è®¡ã€‚å®ƒä¼šï¼š
1. è‡ªåŠ¨å°†ä½ çš„é—®é¢˜åˆ†è§£ä¸ºå¤šä¸ªå­é—®é¢˜
2. ä»Žå¤šä¸ªç»´åº¦æ£€ç´¢æ¨¡æ‹Ÿå›¾è°±ä¸­çš„ä¿¡æ¯
3. æ•´åˆè¯­ä¹‰æœç´¢ã€å®žä½“åˆ†æžã€å…³ç³»é“¾è¿½è¸ªçš„ç»“æžœ
4. è¿”å›žæœ€å…¨é¢ã€æœ€æ·±åº¦çš„æ£€ç´¢å†…å®¹

ã€ä½¿ç”¨åœºæ™¯ã€‘
- éœ€è¦æ·±å…¥åˆ†æžæŸä¸ªè¯é¢˜
- éœ€è¦äº†è§£äº‹ä»¶çš„å¤šä¸ªæ–¹é¢
- éœ€è¦èŽ·å–æ”¯æ’‘æŠ¥å‘Šç« èŠ‚çš„ä¸°å¯Œç´ æ

ã€è¿”å›žå†…å®¹ã€‘
- ç›¸å…³äº‹å®žåŽŸæ–‡ï¼ˆå¯ç›´æŽ¥å¼•ç”¨ï¼‰
- æ ¸å¿ƒå®žä½“æ´žå¯Ÿ
- å…³ç³»é“¾åˆ†æž"""

TOOL_DESC_PANORAMA_SEARCH = """\
ã€å¹¿åº¦æœç´¢ - èŽ·å–å…¨è²Œè§†å›¾ã€‘
è¿™ä¸ªå·¥å…·ç”¨äºŽèŽ·å–æ¨¡æ‹Ÿç»“æžœçš„å®Œæ•´å…¨è²Œï¼Œç‰¹åˆ«é€‚åˆäº†è§£äº‹ä»¶æ¼”å˜è¿‡ç¨‹ã€‚å®ƒä¼šï¼š
1. èŽ·å–æ‰€æœ‰ç›¸å…³èŠ‚ç‚¹å’Œå…³ç³»
2. åŒºåˆ†å½“å‰æœ‰æ•ˆçš„äº‹å®žå’ŒåŽ†å²/è¿‡æœŸçš„äº‹å®ž
3. å¸®åŠ©ä½ äº†è§£èˆ†æƒ…æ˜¯å¦‚ä½•æ¼”å˜çš„

ã€ä½¿ç”¨åœºæ™¯ã€‘
- éœ€è¦äº†è§£äº‹ä»¶çš„å®Œæ•´å‘å±•è„‰ç»œ
- éœ€è¦å¯¹æ¯”ä¸åŒé˜¶æ®µçš„èˆ†æƒ…å˜åŒ–
- éœ€è¦èŽ·å–å…¨é¢çš„å®žä½“å’Œå…³ç³»ä¿¡æ¯

ã€è¿”å›žå†…å®¹ã€‘
- å½“å‰æœ‰æ•ˆäº‹å®žï¼ˆæ¨¡æ‹Ÿæœ€æ–°ç»“æžœï¼‰
- åŽ†å²/è¿‡æœŸäº‹å®žï¼ˆæ¼”å˜è®°å½•ï¼‰
- æ‰€æœ‰æ¶‰åŠçš„å®žä½“"""

TOOL_DESC_QUICK_SEARCH = """\
ã€ç®€å•æœç´¢ - å¿«é€Ÿæ£€ç´¢ã€‘
è½»é‡çº§çš„å¿«é€Ÿæ£€ç´¢å·¥å…·ï¼Œé€‚åˆç®€å•ã€ç›´æŽ¥çš„ä¿¡æ¯æŸ¥è¯¢ã€‚

ã€ä½¿ç”¨åœºæ™¯ã€‘
- éœ€è¦å¿«é€ŸæŸ¥æ‰¾æŸä¸ªå…·ä½“ä¿¡æ¯
- éœ€è¦éªŒè¯æŸä¸ªäº‹å®ž
- ç®€å•çš„ä¿¡æ¯æ£€ç´¢

ã€è¿”å›žå†…å®¹ã€‘
- ä¸ŽæŸ¥è¯¢æœ€ç›¸å…³çš„äº‹å®žåˆ—è¡¨"""

TOOL_DESC_INTERVIEW_AGENTS = """\
ã€æ·±åº¦é‡‡è®¿ - çœŸå®žAgenté‡‡è®¿ï¼ˆåŒå¹³å°ï¼‰ã€‘
è°ƒç”¨OASISæ¨¡æ‹ŸçŽ¯å¢ƒçš„é‡‡è®¿APIï¼Œå¯¹æ­£åœ¨è¿è¡Œçš„æ¨¡æ‹ŸAgentè¿›è¡ŒçœŸå®žé‡‡è®¿ï¼
è¿™ä¸æ˜¯LLMæ¨¡æ‹Ÿï¼Œè€Œæ˜¯è°ƒç”¨çœŸå®žçš„é‡‡è®¿æŽ¥å£èŽ·å–æ¨¡æ‹ŸAgentçš„åŽŸå§‹å›žç­”ã€‚
é»˜è®¤åœ¨Twitterå’ŒRedditä¸¤ä¸ªå¹³å°åŒæ—¶é‡‡è®¿ï¼ŒèŽ·å–æ›´å…¨é¢çš„è§‚ç‚¹ã€‚

åŠŸèƒ½æµç¨‹ï¼š
1. è‡ªåŠ¨è¯»å–äººè®¾æ–‡ä»¶ï¼Œäº†è§£æ‰€æœ‰æ¨¡æ‹ŸAgent
2. æ™ºèƒ½é€‰æ‹©ä¸Žé‡‡è®¿ä¸»é¢˜æœ€ç›¸å…³çš„Agentï¼ˆå¦‚å­¦ç”Ÿã€åª’ä½“ã€å®˜æ–¹ç­‰ï¼‰
3. è‡ªåŠ¨ç”Ÿæˆé‡‡è®¿é—®é¢˜
4. è°ƒç”¨ /api/simulation/interview/batch æŽ¥å£åœ¨åŒå¹³å°è¿›è¡ŒçœŸå®žé‡‡è®¿
5. æ•´åˆæ‰€æœ‰é‡‡è®¿ç»“æžœï¼Œæä¾›å¤šè§†è§’åˆ†æž

ã€ä½¿ç”¨åœºæ™¯ã€‘
- éœ€è¦ä»Žä¸åŒè§’è‰²è§†è§’äº†è§£äº‹ä»¶çœ‹æ³•ï¼ˆå­¦ç”Ÿæ€Žä¹ˆçœ‹ï¼Ÿåª’ä½“æ€Žä¹ˆçœ‹ï¼Ÿå®˜æ–¹æ€Žä¹ˆè¯´ï¼Ÿï¼‰
- éœ€è¦æ”¶é›†å¤šæ–¹æ„è§å’Œç«‹åœº
- éœ€è¦èŽ·å–æ¨¡æ‹ŸAgentçš„çœŸå®žå›žç­”ï¼ˆæ¥è‡ªOASISæ¨¡æ‹ŸçŽ¯å¢ƒï¼‰
- æƒ³è®©æŠ¥å‘Šæ›´ç”ŸåŠ¨ï¼ŒåŒ…å«"é‡‡è®¿å®žå½•"

ã€è¿”å›žå†…å®¹ã€‘
- è¢«é‡‡è®¿Agentçš„èº«ä»½ä¿¡æ¯
- å„Agentåœ¨Twitterå’ŒRedditä¸¤ä¸ªå¹³å°çš„é‡‡è®¿å›žç­”
- å…³é”®å¼•è¨€ï¼ˆå¯ç›´æŽ¥å¼•ç”¨ï¼‰
- é‡‡è®¿æ‘˜è¦å’Œè§‚ç‚¹å¯¹æ¯”

ã€é‡è¦ã€‘éœ€è¦OASISæ¨¡æ‹ŸçŽ¯å¢ƒæ­£åœ¨è¿è¡Œæ‰èƒ½ä½¿ç”¨æ­¤åŠŸèƒ½ï¼"""


PLAN_SYSTEM_PROMPT = """\
ä½ æ˜¯ä¸€ä¸ªã€Œæœªæ¥é¢„æµ‹æŠ¥å‘Šã€çš„æ’°å†™ä¸“å®¶ï¼Œæ‹¥æœ‰å¯¹æ¨¡æ‹Ÿä¸–ç•Œçš„ã€Œä¸Šå¸è§†è§’ã€â€”â€”ä½ å¯ä»¥æ´žå¯Ÿæ¨¡æ‹Ÿä¸­æ¯ä¸€ä½Agentçš„è¡Œä¸ºã€è¨€è®ºå’Œäº’åŠ¨ã€‚

ã€æ ¸å¿ƒç†å¿µã€‘
æˆ‘ä»¬æž„å»ºäº†ä¸€ä¸ªæ¨¡æ‹Ÿä¸–ç•Œï¼Œå¹¶å‘å…¶ä¸­æ³¨å…¥äº†ç‰¹å®šçš„ã€Œæ¨¡æ‹Ÿéœ€æ±‚ã€ä½œä¸ºå˜é‡ã€‚æ¨¡æ‹Ÿä¸–ç•Œçš„æ¼”åŒ–ç»“æžœï¼Œå°±æ˜¯å¯¹æœªæ¥å¯èƒ½å‘ç”Ÿæƒ…å†µçš„é¢„æµ‹ã€‚ä½ æ­£åœ¨è§‚å¯Ÿçš„ä¸æ˜¯"å®žéªŒæ•°æ®"ï¼Œè€Œæ˜¯"æœªæ¥çš„é¢„æ¼”"ã€‚

ã€ä½ çš„ä»»åŠ¡ã€‘
æ’°å†™ä¸€ä»½ã€Œæœªæ¥é¢„æµ‹æŠ¥å‘Šã€ï¼Œå›žç­”ï¼š
1. åœ¨æˆ‘ä»¬è®¾å®šçš„æ¡ä»¶ä¸‹ï¼Œæœªæ¥å‘ç”Ÿäº†ä»€ä¹ˆï¼Ÿ
2. å„ç±»Agentï¼ˆäººç¾¤ï¼‰æ˜¯å¦‚ä½•ååº”å’Œè¡ŒåŠ¨ï¼Ÿ
3. è¿™ä¸ªæ¨¡æ‹Ÿæ­ç¤ºäº†å“ªäº›å€¼å¾—å…³æ³¨çš„æœªæ¥è¶‹åŠ¿å’Œé£Žé™©ï¼Ÿ

ã€æŠ¥å‘Šå®šä½ã€‘
- âœ… è¿™æ˜¯ä¸€ä»½åŸºäºŽæ¨¡æ‹Ÿçš„æœªæ¥é¢„æµ‹æŠ¥å‘Šï¼Œæ­ç¤º"å¦‚æžœè¿™æ ·ï¼Œæœªæ¥ä¼šæ€Žæ ·"
- âœ… èšç„¦äºŽé¢„æµ‹ç»“æžœï¼šäº‹ä»¶èµ°å‘ã€ç¾¤ä½“ååº”ã€æ¶ŒçŽ°çŽ°è±¡ã€æ½œåœ¨é£Žé™©
- âœ… æ¨¡æ‹Ÿä¸–ç•Œä¸­çš„Agentè¨€è¡Œå°±æ˜¯å¯¹æœªæ¥äººç¾¤è¡Œä¸ºçš„é¢„æµ‹
- âŒ ä¸æ˜¯å¯¹çŽ°å®žä¸–ç•ŒçŽ°çŠ¶çš„åˆ†æž
- âŒ ä¸æ˜¯æ³›æ³›è€Œè°ˆçš„èˆ†æƒ…ç»¼è¿°

ã€ç« èŠ‚æ•°é‡é™åˆ¶ã€‘
- æœ€å°‘2ä¸ªç« èŠ‚ï¼Œæœ€å¤š5ä¸ªç« èŠ‚
- ä¸éœ€è¦å­ç« èŠ‚ï¼Œæ¯ä¸ªç« èŠ‚ç›´æŽ¥æ’°å†™å®Œæ•´å†…å®¹
- å†…å®¹è¦ç²¾ç‚¼ï¼Œèšç„¦äºŽæ ¸å¿ƒé¢„æµ‹å‘çŽ°
- ç« èŠ‚ç»“æž„ç”±ä½ æ ¹æ®é¢„æµ‹ç»“æžœè‡ªä¸»è®¾è®¡

è¯·è¾“å‡ºJSONæ ¼å¼çš„æŠ¥å‘Šå¤§çº²ï¼Œæ ¼å¼å¦‚ä¸‹ï¼š
{
    "title": "æŠ¥å‘Šæ ‡é¢˜",
    "summary": "æŠ¥å‘Šæ‘˜è¦ï¼ˆä¸€å¥è¯æ¦‚æ‹¬æ ¸å¿ƒé¢„æµ‹å‘çŽ°ï¼‰",
    "sections": [
        {
            "title": "ç« èŠ‚æ ‡é¢˜",
            "description": "ç« èŠ‚å†…å®¹æè¿°"
        }
    ]
}

æ³¨æ„ï¼šsectionsæ•°ç»„æœ€å°‘2ä¸ªï¼Œæœ€å¤š5ä¸ªå…ƒç´ ï¼"""

PLAN_USER_PROMPT_TEMPLATE = """\
ã€é¢„æµ‹åœºæ™¯è®¾å®šã€‘
æˆ‘ä»¬å‘æ¨¡æ‹Ÿä¸–ç•Œæ³¨å…¥çš„å˜é‡ï¼ˆæ¨¡æ‹Ÿéœ€æ±‚ï¼‰ï¼š{simulation_requirement}

ã€æ¨¡æ‹Ÿä¸–ç•Œè§„æ¨¡ã€‘
- å‚ä¸Žæ¨¡æ‹Ÿçš„å®žä½“æ•°é‡: {total_nodes}
- å®žä½“é—´äº§ç”Ÿçš„å…³ç³»æ•°é‡: {total_edges}
- å®žä½“ç±»åž‹åˆ†å¸ƒ: {entity_types}
- æ´»è·ƒAgentæ•°é‡: {total_entities}

ã€æ¨¡æ‹Ÿé¢„æµ‹åˆ°çš„éƒ¨åˆ†æœªæ¥äº‹å®žæ ·æœ¬ã€‘
{related_facts_json}

è¯·ä»¥ã€Œä¸Šå¸è§†è§’ã€å®¡è§†è¿™ä¸ªæœªæ¥é¢„æ¼”ï¼š
1. åœ¨æˆ‘ä»¬è®¾å®šçš„æ¡ä»¶ä¸‹ï¼Œæœªæ¥å‘ˆçŽ°å‡ºäº†ä»€ä¹ˆæ ·çš„çŠ¶æ€ï¼Ÿ
2. å„ç±»äººç¾¤ï¼ˆAgentï¼‰æ˜¯å¦‚ä½•ååº”å’Œè¡ŒåŠ¨çš„ï¼Ÿ
3. è¿™ä¸ªæ¨¡æ‹Ÿæ­ç¤ºäº†å“ªäº›å€¼å¾—å…³æ³¨çš„æœªæ¥è¶‹åŠ¿ï¼Ÿ

æ ¹æ®é¢„æµ‹ç»“æžœï¼Œè®¾è®¡æœ€åˆé€‚çš„æŠ¥å‘Šç« èŠ‚ç»“æž„ã€‚

ã€å†æ¬¡æé†’ã€‘æŠ¥å‘Šç« èŠ‚æ•°é‡ï¼šæœ€å°‘2ä¸ªï¼Œæœ€å¤š5ä¸ªï¼Œå†…å®¹è¦ç²¾ç‚¼èšç„¦äºŽæ ¸å¿ƒé¢„æµ‹å‘çŽ°ã€‚"""


SECTION_SYSTEM_PROMPT_TEMPLATE = """\
ä½ æ˜¯ä¸€ä¸ªã€Œæœªæ¥é¢„æµ‹æŠ¥å‘Šã€çš„æ’°å†™ä¸“å®¶ï¼Œæ­£åœ¨æ’°å†™æŠ¥å‘Šçš„ä¸€ä¸ªç« èŠ‚ã€‚

æŠ¥å‘Šæ ‡é¢˜: {report_title}
æŠ¥å‘Šæ‘˜è¦: {report_summary}
é¢„æµ‹åœºæ™¯ï¼ˆæ¨¡æ‹Ÿéœ€æ±‚ï¼‰: {simulation_requirement}

å½“å‰è¦æ’°å†™çš„ç« èŠ‚: {section_title}

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
ã€æ ¸å¿ƒç†å¿µã€‘
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

æ¨¡æ‹Ÿä¸–ç•Œæ˜¯å¯¹æœªæ¥çš„é¢„æ¼”ã€‚æˆ‘ä»¬å‘æ¨¡æ‹Ÿä¸–ç•Œæ³¨å…¥äº†ç‰¹å®šæ¡ä»¶ï¼ˆæ¨¡æ‹Ÿéœ€æ±‚ï¼‰ï¼Œ
æ¨¡æ‹Ÿä¸­Agentçš„è¡Œä¸ºå’Œäº’åŠ¨ï¼Œå°±æ˜¯å¯¹æœªæ¥äººç¾¤è¡Œä¸ºçš„é¢„æµ‹ã€‚

ä½ çš„ä»»åŠ¡æ˜¯ï¼š
- æ­ç¤ºåœ¨è®¾å®šæ¡ä»¶ä¸‹ï¼Œæœªæ¥å‘ç”Ÿäº†ä»€ä¹ˆ
- é¢„æµ‹å„ç±»äººç¾¤ï¼ˆAgentï¼‰æ˜¯å¦‚ä½•ååº”å’Œè¡ŒåŠ¨çš„
- å‘çŽ°å€¼å¾—å…³æ³¨çš„æœªæ¥è¶‹åŠ¿ã€é£Žé™©å’Œæœºä¼š

âŒ ä¸è¦å†™æˆå¯¹çŽ°å®žä¸–ç•ŒçŽ°çŠ¶çš„åˆ†æž
âœ… è¦èšç„¦äºŽ"æœªæ¥ä¼šæ€Žæ ·"â€”â€”æ¨¡æ‹Ÿç»“æžœå°±æ˜¯é¢„æµ‹çš„æœªæ¥

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
ã€æœ€é‡è¦çš„è§„åˆ™ - å¿…é¡»éµå®ˆã€‘
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

1. ã€å¿…é¡»è°ƒç”¨å·¥å…·è§‚å¯Ÿæ¨¡æ‹Ÿä¸–ç•Œã€‘
   - ä½ æ­£åœ¨ä»¥ã€Œä¸Šå¸è§†è§’ã€è§‚å¯Ÿæœªæ¥çš„é¢„æ¼”
   - æ‰€æœ‰å†…å®¹å¿…é¡»æ¥è‡ªæ¨¡æ‹Ÿä¸–ç•Œä¸­å‘ç”Ÿçš„äº‹ä»¶å’ŒAgentè¨€è¡Œ
   - ç¦æ­¢ä½¿ç”¨ä½ è‡ªå·±çš„çŸ¥è¯†æ¥ç¼–å†™æŠ¥å‘Šå†…å®¹
   - æ¯ä¸ªç« èŠ‚è‡³å°‘è°ƒç”¨3æ¬¡å·¥å…·ï¼ˆæœ€å¤š5æ¬¡ï¼‰æ¥è§‚å¯Ÿæ¨¡æ‹Ÿçš„ä¸–ç•Œï¼Œå®ƒä»£è¡¨äº†æœªæ¥

2. ã€å¿…é¡»å¼•ç”¨Agentçš„åŽŸå§‹è¨€è¡Œã€‘
   - Agentçš„å‘è¨€å’Œè¡Œä¸ºæ˜¯å¯¹æœªæ¥äººç¾¤è¡Œä¸ºçš„é¢„æµ‹
   - åœ¨æŠ¥å‘Šä¸­ä½¿ç”¨å¼•ç”¨æ ¼å¼å±•ç¤ºè¿™äº›é¢„æµ‹ï¼Œä¾‹å¦‚ï¼š
     > "æŸç±»äººç¾¤ä¼šè¡¨ç¤ºï¼šåŽŸæ–‡å†…å®¹..."
   - è¿™äº›å¼•ç”¨æ˜¯æ¨¡æ‹Ÿé¢„æµ‹çš„æ ¸å¿ƒè¯æ®

3. ã€è¯­è¨€ä¸€è‡´æ€§ - å¼•ç”¨å†…å®¹å¿…é¡»ç¿»è¯‘ä¸ºæŠ¥å‘Šè¯­è¨€ã€‘
   - å·¥å…·è¿”å›žçš„å†…å®¹å¯èƒ½åŒ…å«ä¸ŽæŠ¥å‘Šè¯­è¨€ä¸åŒçš„è¡¨è¿°
   - æŠ¥å‘Šå¿…é¡»å…¨éƒ¨ä½¿ç”¨ä¸Žç”¨æˆ·æŒ‡å®šè¯­è¨€ä¸€è‡´çš„è¯­è¨€æ’°å†™
   - å½“ä½ å¼•ç”¨å·¥å…·è¿”å›žçš„å…¶ä»–è¯­è¨€å†…å®¹æ—¶ï¼Œå¿…é¡»å°†å…¶ç¿»è¯‘ä¸ºæŠ¥å‘Šè¯­è¨€åŽå†å†™å…¥
   - ç¿»è¯‘æ—¶ä¿æŒåŽŸæ„ä¸å˜ï¼Œç¡®ä¿è¡¨è¿°è‡ªç„¶é€šé¡º
   - è¿™ä¸€è§„åˆ™åŒæ—¶é€‚ç”¨äºŽæ­£æ–‡å’Œå¼•ç”¨å—ï¼ˆ> æ ¼å¼ï¼‰ä¸­çš„å†…å®¹

4. ã€å¿ å®žå‘ˆçŽ°é¢„æµ‹ç»“æžœã€‘
   - æŠ¥å‘Šå†…å®¹å¿…é¡»åæ˜ æ¨¡æ‹Ÿä¸–ç•Œä¸­çš„ä»£è¡¨æœªæ¥çš„æ¨¡æ‹Ÿç»“æžœ
   - ä¸è¦æ·»åŠ æ¨¡æ‹Ÿä¸­ä¸å­˜åœ¨çš„ä¿¡æ¯
   - å¦‚æžœæŸæ–¹é¢ä¿¡æ¯ä¸è¶³ï¼Œå¦‚å®žè¯´æ˜Ž

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
ã€âš ï¸ æ ¼å¼è§„èŒƒ - æžå…¶é‡è¦ï¼ã€‘
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

ã€ä¸€ä¸ªç« èŠ‚ = æœ€å°å†…å®¹å•ä½ã€‘
- æ¯ä¸ªç« èŠ‚æ˜¯æŠ¥å‘Šçš„æœ€å°åˆ†å—å•ä½
- âŒ ç¦æ­¢åœ¨ç« èŠ‚å†…ä½¿ç”¨ä»»ä½• Markdown æ ‡é¢˜ï¼ˆ#ã€##ã€###ã€#### ç­‰ï¼‰
- âŒ ç¦æ­¢åœ¨å†…å®¹å¼€å¤´æ·»åŠ ç« èŠ‚ä¸»æ ‡é¢˜
- âœ… ç« èŠ‚æ ‡é¢˜ç”±ç³»ç»Ÿè‡ªåŠ¨æ·»åŠ ï¼Œä½ åªéœ€æ’°å†™çº¯æ­£æ–‡å†…å®¹
- âœ… ä½¿ç”¨**ç²—ä½“**ã€æ®µè½åˆ†éš”ã€å¼•ç”¨ã€åˆ—è¡¨æ¥ç»„ç»‡å†…å®¹ï¼Œä½†ä¸è¦ç”¨æ ‡é¢˜

ã€æ­£ç¡®ç¤ºä¾‹ã€‘
```
æœ¬ç« èŠ‚åˆ†æžäº†äº‹ä»¶çš„èˆ†è®ºä¼ æ’­æ€åŠ¿ã€‚é€šè¿‡å¯¹æ¨¡æ‹Ÿæ•°æ®çš„æ·±å…¥åˆ†æžï¼Œæˆ‘ä»¬å‘çŽ°...

**é¦–å‘å¼•çˆ†é˜¶æ®µ**

å¾®åšä½œä¸ºèˆ†æƒ…çš„ç¬¬ä¸€çŽ°åœºï¼Œæ‰¿æ‹…äº†ä¿¡æ¯é¦–å‘çš„æ ¸å¿ƒåŠŸèƒ½ï¼š

> "å¾®åšè´¡çŒ®äº†68%çš„é¦–å‘å£°é‡..."

**æƒ…ç»ªæ”¾å¤§é˜¶æ®µ**

æŠ–éŸ³å¹³å°è¿›ä¸€æ­¥æ”¾å¤§äº†äº‹ä»¶å½±å“åŠ›ï¼š

- è§†è§‰å†²å‡»åŠ›å¼º
- æƒ…ç»ªå…±é¸£åº¦é«˜
```

ã€é”™è¯¯ç¤ºä¾‹ã€‘
```

æœ¬ç« èŠ‚åˆ†æžäº†...
```

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
ã€å¯ç”¨æ£€ç´¢å·¥å…·ã€‘ï¼ˆæ¯ç« èŠ‚è°ƒç”¨3-5æ¬¡ï¼‰
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

{tools_description}

ã€å·¥å…·ä½¿ç”¨å»ºè®® - è¯·æ··åˆä½¿ç”¨ä¸åŒå·¥å…·ï¼Œä¸è¦åªç”¨ä¸€ç§ã€‘
- insight_forge: æ·±åº¦æ´žå¯Ÿåˆ†æžï¼Œè‡ªåŠ¨åˆ†è§£é—®é¢˜å¹¶å¤šç»´åº¦æ£€ç´¢äº‹å®žå’Œå…³ç³»
- panorama_search: å¹¿è§’å…¨æ™¯æœç´¢ï¼Œäº†è§£äº‹ä»¶å…¨è²Œã€æ—¶é—´çº¿å’Œæ¼”å˜è¿‡ç¨‹
- quick_search: å¿«é€ŸéªŒè¯æŸä¸ªå…·ä½“ä¿¡æ¯ç‚¹
- interview_agents: é‡‡è®¿æ¨¡æ‹ŸAgentï¼ŒèŽ·å–ä¸åŒè§’è‰²çš„ç¬¬ä¸€äººç§°è§‚ç‚¹å’ŒçœŸå®žååº”

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
ã€å·¥ä½œæµç¨‹ã€‘
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

æ¯æ¬¡å›žå¤ä½ åªèƒ½åšä»¥ä¸‹ä¸¤ä»¶äº‹ä¹‹ä¸€ï¼ˆä¸å¯åŒæ—¶åšï¼‰ï¼š

é€‰é¡¹A - è°ƒç”¨å·¥å…·ï¼š
è¾“å‡ºä½ çš„æ€è€ƒï¼Œç„¶åŽç”¨ä»¥ä¸‹æ ¼å¼è°ƒç”¨ä¸€ä¸ªå·¥å…·ï¼š
<tool_call>
{{"name": "å·¥å…·åç§°", "parameters": {{"å‚æ•°å": "å‚æ•°å€¼"}}}}
</tool_call>
ç³»ç»Ÿä¼šæ‰§è¡Œå·¥å…·å¹¶æŠŠç»“æžœè¿”å›žç»™ä½ ã€‚ä½ ä¸éœ€è¦ä¹Ÿä¸èƒ½è‡ªå·±ç¼–å†™å·¥å…·è¿”å›žç»“æžœã€‚

é€‰é¡¹B - è¾“å‡ºæœ€ç»ˆå†…å®¹ï¼š
å½“ä½ å·²é€šè¿‡å·¥å…·èŽ·å–äº†è¶³å¤Ÿä¿¡æ¯ï¼Œä»¥ "Final Answer:" å¼€å¤´è¾“å‡ºç« èŠ‚å†…å®¹ã€‚

âš ï¸ ä¸¥æ ¼ç¦æ­¢ï¼š
- ç¦æ­¢åœ¨ä¸€æ¬¡å›žå¤ä¸­åŒæ—¶åŒ…å«å·¥å…·è°ƒç”¨å’Œ Final Answer
- ç¦æ­¢è‡ªå·±ç¼–é€ å·¥å…·è¿”å›žç»“æžœï¼ˆObservationï¼‰ï¼Œæ‰€æœ‰å·¥å…·ç»“æžœç”±ç³»ç»Ÿæ³¨å…¥
- æ¯æ¬¡å›žå¤æœ€å¤šè°ƒç”¨ä¸€ä¸ªå·¥å…·

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
ã€ç« èŠ‚å†…å®¹è¦æ±‚ã€‘
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

1. å†…å®¹å¿…é¡»åŸºäºŽå·¥å…·æ£€ç´¢åˆ°çš„æ¨¡æ‹Ÿæ•°æ®
2. å¤§é‡å¼•ç”¨åŽŸæ–‡æ¥å±•ç¤ºæ¨¡æ‹Ÿæ•ˆæžœ
3. ä½¿ç”¨Markdownæ ¼å¼ï¼ˆä½†ç¦æ­¢ä½¿ç”¨æ ‡é¢˜ï¼‰ï¼š
   - ä½¿ç”¨ **ç²—ä½“æ–‡å­—** æ ‡è®°é‡ç‚¹ï¼ˆä»£æ›¿å­æ ‡é¢˜ï¼‰
   - ä½¿ç”¨åˆ—è¡¨ï¼ˆ-æˆ–1.2.3.ï¼‰ç»„ç»‡è¦ç‚¹
   - ä½¿ç”¨ç©ºè¡Œåˆ†éš”ä¸åŒæ®µè½
   - âŒ ç¦æ­¢ä½¿ç”¨ #ã€##ã€###ã€#### ç­‰ä»»ä½•æ ‡é¢˜è¯­æ³•
4. ã€å¼•ç”¨æ ¼å¼è§„èŒƒ - å¿…é¡»å•ç‹¬æˆæ®µã€‘
   å¼•ç”¨å¿…é¡»ç‹¬ç«‹æˆæ®µï¼Œå‰åŽå„æœ‰ä¸€ä¸ªç©ºè¡Œï¼Œä¸èƒ½æ··åœ¨æ®µè½ä¸­ï¼š

   âœ… æ­£ç¡®æ ¼å¼ï¼š
   ```
   æ ¡æ–¹çš„å›žåº”è¢«è®¤ä¸ºç¼ºä¹å®žè´¨å†…å®¹ã€‚

   > "æ ¡æ–¹çš„åº”å¯¹æ¨¡å¼åœ¨çž¬æ¯ä¸‡å˜çš„ç¤¾äº¤åª’ä½“çŽ¯å¢ƒä¸­æ˜¾å¾—åƒµåŒ–å’Œè¿Ÿç¼“ã€‚"

   è¿™ä¸€è¯„ä»·åæ˜ äº†å…¬ä¼—çš„æ™®éä¸æ»¡ã€‚
   ```

   âŒ é”™è¯¯æ ¼å¼ï¼š
   ```
   æ ¡æ–¹çš„å›žåº”è¢«è®¤ä¸ºç¼ºä¹å®žè´¨å†…å®¹ã€‚> "æ ¡æ–¹çš„åº”å¯¹æ¨¡å¼..." è¿™ä¸€è¯„ä»·åæ˜ äº†...
   ```
5. ä¿æŒä¸Žå…¶ä»–ç« èŠ‚çš„é€»è¾‘è¿žè´¯æ€§
6. ã€é¿å…é‡å¤ã€‘ä»”ç»†é˜…è¯»ä¸‹æ–¹å·²å®Œæˆçš„ç« èŠ‚å†…å®¹ï¼Œä¸è¦é‡å¤æè¿°ç›¸åŒçš„ä¿¡æ¯
7. ã€å†æ¬¡å¼ºè°ƒã€‘ä¸è¦æ·»åŠ ä»»ä½•æ ‡é¢˜ï¼ç”¨**ç²—ä½“**ä»£æ›¿å°èŠ‚æ ‡é¢˜"""

SECTION_USER_PROMPT_TEMPLATE = """\
å·²å®Œæˆçš„ç« èŠ‚å†…å®¹ï¼ˆè¯·ä»”ç»†é˜…è¯»ï¼Œé¿å…é‡å¤ï¼‰ï¼š
{previous_content}

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
ã€å½“å‰ä»»åŠ¡ã€‘æ’°å†™ç« èŠ‚: {section_title}
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

ã€é‡è¦æé†’ã€‘
1. ä»”ç»†é˜…è¯»ä¸Šæ–¹å·²å®Œæˆçš„ç« èŠ‚ï¼Œé¿å…é‡å¤ç›¸åŒçš„å†…å®¹ï¼
2. å¼€å§‹å‰å¿…é¡»å…ˆè°ƒç”¨å·¥å…·èŽ·å–æ¨¡æ‹Ÿæ•°æ®
3. è¯·æ··åˆä½¿ç”¨ä¸åŒå·¥å…·ï¼Œä¸è¦åªç”¨ä¸€ç§
4. æŠ¥å‘Šå†…å®¹å¿…é¡»æ¥è‡ªæ£€ç´¢ç»“æžœï¼Œä¸è¦ä½¿ç”¨è‡ªå·±çš„çŸ¥è¯†

ã€âš ï¸ æ ¼å¼è­¦å‘Š - å¿…é¡»éµå®ˆã€‘
- âŒ ä¸è¦å†™ä»»ä½•æ ‡é¢˜ï¼ˆ#ã€##ã€###ã€####éƒ½ä¸è¡Œï¼‰
- âŒ ä¸è¦å†™"{section_title}"ä½œä¸ºå¼€å¤´
- âœ… ç« èŠ‚æ ‡é¢˜ç”±ç³»ç»Ÿè‡ªåŠ¨æ·»åŠ 
- âœ… ç›´æŽ¥å†™æ­£æ–‡ï¼Œç”¨**ç²—ä½“**ä»£æ›¿å°èŠ‚æ ‡é¢˜

è¯·å¼€å§‹ï¼š
1. é¦–å…ˆæ€è€ƒï¼ˆThoughtï¼‰è¿™ä¸ªç« èŠ‚éœ€è¦ä»€ä¹ˆä¿¡æ¯
2. ç„¶åŽè°ƒç”¨å·¥å…·ï¼ˆActionï¼‰èŽ·å–æ¨¡æ‹Ÿæ•°æ®
3. æ”¶é›†è¶³å¤Ÿä¿¡æ¯åŽè¾“å‡º Final Answerï¼ˆçº¯æ­£æ–‡ï¼Œæ— ä»»ä½•æ ‡é¢˜ï¼‰"""


REACT_OBSERVATION_TEMPLATE = """\
Observationï¼ˆæ£€ç´¢ç»“æžœï¼‰:

â•â•â• å·¥å…· {tool_name} è¿”å›ž â•â•â•
{result}

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
å·²è°ƒç”¨å·¥å…· {tool_calls_count}/{max_tool_calls} æ¬¡ï¼ˆå·²ç”¨: {used_tools_str}ï¼‰{unused_hint}
- å¦‚æžœä¿¡æ¯å……åˆ†ï¼šä»¥ "Final Answer:" å¼€å¤´è¾“å‡ºç« èŠ‚å†…å®¹ï¼ˆå¿…é¡»å¼•ç”¨ä¸Šè¿°åŽŸæ–‡ï¼‰
- å¦‚æžœéœ€è¦æ›´å¤šä¿¡æ¯ï¼šè°ƒç”¨ä¸€ä¸ªå·¥å…·ç»§ç»­æ£€ç´¢
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"""

REACT_INSUFFICIENT_TOOLS_MSG = (
    "ã€æ³¨æ„ã€‘ä½ åªè°ƒç”¨äº†{tool_calls_count}æ¬¡å·¥å…·ï¼Œè‡³å°‘éœ€è¦{min_tool_calls}æ¬¡ã€‚"
    "è¯·å†è°ƒç”¨å·¥å…·èŽ·å–æ›´å¤šæ¨¡æ‹Ÿæ•°æ®ï¼Œç„¶åŽå†è¾“å‡º Final Answerã€‚{unused_hint}"
)

REACT_INSUFFICIENT_TOOLS_MSG_ALT = (
    "å½“å‰åªè°ƒç”¨äº† {tool_calls_count} æ¬¡å·¥å…·ï¼Œè‡³å°‘éœ€è¦ {min_tool_calls} æ¬¡ã€‚"
    "è¯·è°ƒç”¨å·¥å…·èŽ·å–æ¨¡æ‹Ÿæ•°æ®ã€‚{unused_hint}"
)

REACT_TOOL_LIMIT_MSG = (
    "å·¥å…·è°ƒç”¨æ¬¡æ•°å·²è¾¾ä¸Šé™ï¼ˆ{tool_calls_count}/{max_tool_calls}ï¼‰ï¼Œä¸èƒ½å†è°ƒç”¨å·¥å…·ã€‚"
    'è¯·ç«‹å³åŸºäºŽå·²èŽ·å–çš„ä¿¡æ¯ï¼Œä»¥ "Final Answer:" å¼€å¤´è¾“å‡ºç« èŠ‚å†…å®¹ã€‚'
)

REACT_UNUSED_TOOLS_HINT = "\nðŸ’¡ ä½ è¿˜æ²¡æœ‰ä½¿ç”¨è¿‡: {unused_list}ï¼Œå»ºè®®å°è¯•ä¸åŒå·¥å…·èŽ·å–å¤šè§’åº¦ä¿¡æ¯"

REACT_FORCE_FINAL_MSG = "å·²è¾¾åˆ°å·¥å…·è°ƒç”¨é™åˆ¶ï¼Œè¯·ç›´æŽ¥è¾“å‡º Final Answer: å¹¶ç”Ÿæˆç« èŠ‚å†…å®¹ã€‚"


CHAT_SYSTEM_PROMPT_TEMPLATE = """\
ä½ æ˜¯ä¸€ä¸ªç®€æ´é«˜æ•ˆçš„æ¨¡æ‹Ÿé¢„æµ‹åŠ©æ‰‹ã€‚

ã€èƒŒæ™¯ã€‘
é¢„æµ‹æ¡ä»¶: {simulation_requirement}

ã€å·²ç”Ÿæˆçš„åˆ†æžæŠ¥å‘Šã€‘
{report_content}

ã€è§„åˆ™ã€‘
1. ä¼˜å…ˆåŸºäºŽä¸Šè¿°æŠ¥å‘Šå†…å®¹å›žç­”é—®é¢˜
2. ç›´æŽ¥å›žç­”é—®é¢˜ï¼Œé¿å…å†—é•¿çš„æ€è€ƒè®ºè¿°
3. ä»…åœ¨æŠ¥å‘Šå†…å®¹ä¸è¶³ä»¥å›žç­”æ—¶ï¼Œæ‰è°ƒç”¨å·¥å…·æ£€ç´¢æ›´å¤šæ•°æ®
4. å›žç­”è¦ç®€æ´ã€æ¸…æ™°ã€æœ‰æ¡ç†

ã€å¯ç”¨å·¥å…·ã€‘ï¼ˆä»…åœ¨éœ€è¦æ—¶ä½¿ç”¨ï¼Œæœ€å¤šè°ƒç”¨1-2æ¬¡ï¼‰
{tools_description}

ã€å·¥å…·è°ƒç”¨æ ¼å¼ã€‘
<tool_call>
{{"name": "å·¥å…·åç§°", "parameters": {{"å‚æ•°å": "å‚æ•°å€¼"}}}}
</tool_call>

ã€å›žç­”é£Žæ ¼ã€‘
- ç®€æ´ç›´æŽ¥ï¼Œä¸è¦é•¿ç¯‡å¤§è®º
- ä½¿ç”¨ > æ ¼å¼å¼•ç”¨å…³é”®å†…å®¹
- ä¼˜å…ˆç»™å‡ºç»“è®ºï¼Œå†è§£é‡ŠåŽŸå› """

CHAT_OBSERVATION_SUFFIX = "\n\nè¯·ç®€æ´å›žç­”é—®é¢˜ã€‚"




class ReportAgent:
    """

    """
    
    MAX_TOOL_CALLS_PER_SECTION = 5
    
    MAX_REFLECTION_ROUNDS = 3
    
    MAX_TOOL_CALLS_PER_CHAT = 2
    
    def __init__(
        self, 
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: Optional[LLMClient] = None,
        zep_tools: Optional[ZepToolsService] = None
    ):
        """
        
        Args:
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement
        
        self.llm = llm_client or LLMClient()
        self.zep_tools = zep_tools or ZepToolsService()
        
        self.tools = self._define_tools()
        
        self.report_logger: Optional[ReportLogger] = None
        self.console_logger: Optional[ReportConsoleLogger] = None
        
        logger.info(t('report.agentInitDone', graphId=graph_id, simulationId=simulation_id))
    
    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """å®šä¹‰å¯ç”¨å·¥å…·"""
        return {
            "insight_forge": {
                "name": "insight_forge",
                "description": TOOL_DESC_INSIGHT_FORGE,
                "parameters": {
                    "query": "ä½ æƒ³æ·±å…¥åˆ†æžçš„é—®é¢˜æˆ–è¯é¢˜",
                    "report_context": "å½“å‰æŠ¥å‘Šç« èŠ‚çš„ä¸Šä¸‹æ–‡ï¼ˆå¯é€‰ï¼Œæœ‰åŠ©äºŽç”Ÿæˆæ›´ç²¾å‡†çš„å­é—®é¢˜ï¼‰"
                }
            },
            "panorama_search": {
                "name": "panorama_search",
                "description": TOOL_DESC_PANORAMA_SEARCH,
                "parameters": {
                    "query": "æœç´¢æŸ¥è¯¢ï¼Œç”¨äºŽç›¸å…³æ€§æŽ’åº",
                    "include_expired": "æ˜¯å¦åŒ…å«è¿‡æœŸ/åŽ†å²å†…å®¹ï¼ˆé»˜è®¤Trueï¼‰"
                }
            },
            "quick_search": {
                "name": "quick_search",
                "description": TOOL_DESC_QUICK_SEARCH,
                "parameters": {
                    "query": "æœç´¢æŸ¥è¯¢å­—ç¬¦ä¸²",
                    "limit": "è¿”å›žç»“æžœæ•°é‡ï¼ˆå¯é€‰ï¼Œé»˜è®¤10ï¼‰"
                }
            },
            "interview_agents": {
                "name": "interview_agents",
                "description": TOOL_DESC_INTERVIEW_AGENTS,
                "parameters": {
                    "interview_topic": "é‡‡è®¿ä¸»é¢˜æˆ–éœ€æ±‚æè¿°ï¼ˆå¦‚ï¼š'äº†è§£å­¦ç”Ÿå¯¹å®¿èˆç”²é†›äº‹ä»¶çš„çœ‹æ³•'ï¼‰",
                    "max_agents": "æœ€å¤šé‡‡è®¿çš„Agentæ•°é‡ï¼ˆå¯é€‰ï¼Œé»˜è®¤5ï¼Œæœ€å¤§10ï¼‰"
                }
            }
        }
    
    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any], report_context: str = "") -> str:
        """
        
        Args:
            
        Returns:
        """
        logger.info(t('report.executingTool', toolName=tool_name, params=parameters))
        
        try:
            if tool_name == "insight_forge":
                query = parameters.get("query", "")
                ctx = parameters.get("report_context", "") or report_context
                result = self.zep_tools.insight_forge(
                    graph_id=self.graph_id,
                    query=query,
                    simulation_requirement=self.simulation_requirement,
                    report_context=ctx
                )
                return result.to_text()
            
            elif tool_name == "panorama_search":
                query = parameters.get("query", "")
                include_expired = parameters.get("include_expired", True)
                if isinstance(include_expired, str):
                    include_expired = include_expired.lower() in ['true', '1', 'yes']
                result = self.zep_tools.panorama_search(
                    graph_id=self.graph_id,
                    query=query,
                    include_expired=include_expired
                )
                return result.to_text()
            
            elif tool_name == "quick_search":
                query = parameters.get("query", "")
                limit = parameters.get("limit", 10)
                if isinstance(limit, str):
                    limit = int(limit)
                result = self.zep_tools.quick_search(
                    graph_id=self.graph_id,
                    query=query,
                    limit=limit
                )
                return result.to_text()
            
            elif tool_name == "interview_agents":
                interview_topic = parameters.get("interview_topic", parameters.get("query", ""))
                max_agents = parameters.get("max_agents", 5)
                if isinstance(max_agents, str):
                    max_agents = int(max_agents)
                max_agents = min(max_agents, 10)
                result = self.zep_tools.interview_agents(
                    simulation_id=self.simulation_id,
                    interview_requirement=interview_topic,
                    simulation_requirement=self.simulation_requirement,
                    max_agents=max_agents
                )
                return result.to_text()
            
            
            elif tool_name == "search_graph":
                logger.info(t('report.redirectToQuickSearch'))
                return self._execute_tool("quick_search", parameters, report_context)
            
            elif tool_name == "get_graph_statistics":
                result = self.zep_tools.get_graph_statistics(self.graph_id)
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_entity_summary":
                entity_name = parameters.get("entity_name", "")
                result = self.zep_tools.get_entity_summary(
                    graph_id=self.graph_id,
                    entity_name=entity_name
                )
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_simulation_context":
                logger.info(t('report.redirectToInsightForge'))
                query = parameters.get("query", self.simulation_requirement)
                return self._execute_tool("insight_forge", {"query": query}, report_context)
            
            elif tool_name == "get_entities_by_type":
                entity_type = parameters.get("entity_type", "")
                nodes = self.zep_tools.get_entities_by_type(
                    graph_id=self.graph_id,
                    entity_type=entity_type
                )
                result = [n.to_dict() for n in nodes]
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            else:
                return f"æœªçŸ¥å·¥å…·: {tool_name}ã€‚è¯·ä½¿ç”¨ä»¥ä¸‹å·¥å…·ä¹‹ä¸€: insight_forge, panorama_search, quick_search"
                
        except Exception as e:
            logger.error(t('report.toolExecFailed', toolName=tool_name, error=str(e)))
            return f"å·¥å…·æ‰§è¡Œå¤±è´¥: {str(e)}"
    
    VALID_TOOL_NAMES = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """

        1. <tool_call>{"name": "tool_name", "parameters": {...}}</tool_call>
        """
        tool_calls = []

        xml_pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        for match in re.finditer(xml_pattern, response, re.DOTALL):
            try:
                call_data = json.loads(match.group(1))
                tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        if tool_calls:
            return tool_calls

        stripped = response.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                call_data = json.loads(stripped)
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
                    return tool_calls
            except json.JSONDecodeError:
                pass

        json_pattern = r'(\{"(?:name|tool)"\s*:.*?\})\s*$'
        match = re.search(json_pattern, stripped, re.DOTALL)
        if match:
            try:
                call_data = json.loads(match.group(1))
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        return tool_calls

    def _is_valid_tool_call(self, data: dict) -> bool:
        """æ ¡éªŒè§£æžå‡ºçš„ JSON æ˜¯å¦æ˜¯åˆæ³•çš„å·¥å…·è°ƒç”¨"""
        tool_name = data.get("name") or data.get("tool")
        if tool_name and tool_name in self.VALID_TOOL_NAMES:
            if "tool" in data:
                data["name"] = data.pop("tool")
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")
            return True
        return False
    
    def _get_tools_description(self) -> str:
        """ç”Ÿæˆå·¥å…·æè¿°æ–‡æœ¬"""
        desc_parts = ["å¯ç”¨å·¥å…·ï¼š"]
        for name, tool in self.tools.items():
            params_desc = ", ".join([f"{k}: {v}" for k, v in tool["parameters"].items()])
            desc_parts.append(f"- {name}: {tool['description']}")
            if params_desc:
                desc_parts.append(f"  å‚æ•°: {params_desc}")
        return "\n".join(desc_parts)
    
    def plan_outline(
        self, 
        progress_callback: Optional[Callable] = None
    ) -> ReportOutline:
        """
        
        
        Args:
            
        Returns:
        """
        logger.info(t('report.startPlanningOutline'))
        
        if progress_callback:
            progress_callback("planning", 0, t('progress.analyzingRequirements'))
        
        context = self.zep_tools.get_simulation_context(
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement
        )
        
        if progress_callback:
            progress_callback("planning", 30, t('progress.generatingOutline'))
        
        system_prompt = f"{PLAN_SYSTEM_PROMPT}\n\n{get_language_instruction()}"
        user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            total_nodes=context.get('graph_statistics', {}).get('total_nodes', 0),
            total_edges=context.get('graph_statistics', {}).get('total_edges', 0),
            entity_types=list(context.get('graph_statistics', {}).get('entity_types', {}).keys()),
            total_entities=context.get('total_entities', 0),
            related_facts_json=json.dumps(context.get('related_facts', [])[:10], ensure_ascii=False, indent=2),
        )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            if progress_callback:
                progress_callback("planning", 80, t('progress.parsingOutline'))
            
            sections = []
            for section_data in response.get("sections", []):
                sections.append(ReportSection(
                    title=section_data.get("title", ""),
                    content=""
                ))
            
            outline = ReportOutline(
                title=response.get("title", "æ¨¡æ‹Ÿåˆ†æžæŠ¥å‘Š"),
                summary=response.get("summary", ""),
                sections=sections
            )
            
            if progress_callback:
                progress_callback("planning", 100, t('progress.outlinePlanComplete'))
            
            logger.info(t('report.outlinePlanDone', count=len(sections)))
            return outline
            
        except Exception as e:
            logger.error(t('report.outlinePlanFailed', error=str(e)))
            return ReportOutline(
                title="æœªæ¥é¢„æµ‹æŠ¥å‘Š",
                summary="åŸºäºŽæ¨¡æ‹Ÿé¢„æµ‹çš„æœªæ¥è¶‹åŠ¿ä¸Žé£Žé™©åˆ†æž",
                sections=[
                    ReportSection(title="é¢„æµ‹åœºæ™¯ä¸Žæ ¸å¿ƒå‘çŽ°"),
                    ReportSection(title="äººç¾¤è¡Œä¸ºé¢„æµ‹åˆ†æž"),
                    ReportSection(title="è¶‹åŠ¿å±•æœ›ä¸Žé£Žé™©æç¤º")
                ]
            )
    
    def _generate_section_react(
        self, 
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0
    ) -> str:
        """
        
        
        Args:
            
        Returns:
        """
        logger.info(t('report.reactGenerateSection', title=section.title))
        
        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)
        
        system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
            report_title=outline.title,
            report_summary=outline.summary,
            simulation_requirement=self.simulation_requirement,
            section_title=section.title,
            tools_description=self._get_tools_description(),
        )
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}"

        if previous_sections:
            previous_parts = []
            for sec in previous_sections:
                truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
                previous_parts.append(truncated)
            previous_content = "\n\n---\n\n".join(previous_parts)
        else:
            previous_content = "ï¼ˆè¿™æ˜¯ç¬¬ä¸€ä¸ªç« èŠ‚ï¼‰"
        
        user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
            previous_content=previous_content,
            section_title=section.title,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        tool_calls_count = 0
        max_iterations = 5  # æœ€å¤§è¿­ä»£è½®æ•°
        min_tool_calls = 3  # æœ€å°‘å·¥å…·è°ƒç”¨æ¬¡æ•°
        conflict_retries = 0  # å·¥å…·è°ƒç”¨ä¸ŽFinal AnsweråŒæ—¶å‡ºçŽ°çš„è¿žç»­å†²çªæ¬¡æ•°
        used_tools = set()  # è®°å½•å·²è°ƒç”¨è¿‡çš„å·¥å…·å
        all_tools = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

        report_context = f"ç« èŠ‚æ ‡é¢˜: {section.title}\næ¨¡æ‹Ÿéœ€æ±‚: {self.simulation_requirement}"
        
        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    "generating", 
                    int((iteration / max_iterations) * 100),
                    t('progress.deepSearchAndWrite', current=tool_calls_count, max=self.MAX_TOOL_CALLS_PER_SECTION)
                )
            
            response = self.llm.chat(
                messages=messages,
                temperature=0.5,
                max_tokens=4096
            )

            if response is None:
                logger.warning(t('report.sectionIterNone', title=section.title, iteration=iteration + 1))
                if iteration < max_iterations - 1:
                    messages.append({"role": "assistant", "content": "ï¼ˆå“åº”ä¸ºç©ºï¼‰"})
                    messages.append({"role": "user", "content": "è¯·ç»§ç»­ç”Ÿæˆå†…å®¹ã€‚"})
                    continue
                break

            logger.debug(f"LLMå“åº”: {response[:200]}...")

            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = "Final Answer:" in response

            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                logger.warning(
                    t('report.sectionConflict', title=section.title, iteration=iteration+1, conflictCount=conflict_retries)
                )

                if conflict_retries <= 2:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": (
                            "ã€æ ¼å¼é”™è¯¯ã€‘ä½ åœ¨ä¸€æ¬¡å›žå¤ä¸­åŒæ—¶åŒ…å«äº†å·¥å…·è°ƒç”¨å’Œ Final Answerï¼Œè¿™æ˜¯ä¸å…è®¸çš„ã€‚\n"
                            "æ¯æ¬¡å›žå¤åªèƒ½åšä»¥ä¸‹ä¸¤ä»¶äº‹ä¹‹ä¸€ï¼š\n"
                            "- è°ƒç”¨ä¸€ä¸ªå·¥å…·ï¼ˆè¾“å‡ºä¸€ä¸ª <tool_call> å—ï¼Œä¸è¦å†™ Final Answerï¼‰\n"
                            "- è¾“å‡ºæœ€ç»ˆå†…å®¹ï¼ˆä»¥ 'Final Answer:' å¼€å¤´ï¼Œä¸è¦åŒ…å« <tool_call>ï¼‰\n"
                            "è¯·é‡æ–°å›žå¤ï¼Œåªåšå…¶ä¸­ä¸€ä»¶äº‹ã€‚"
                        ),
                    })
                    continue
                else:
                    logger.warning(
                        t('report.sectionConflictDowngrade', title=section.title, conflictCount=conflict_retries)
                    )
                    first_tool_end = response.find('</tool_call>')
                    if first_tool_end != -1:
                        response = response[:first_tool_end + len('</tool_call>')]
                        tool_calls = self._parse_tool_calls(response)
                        has_tool_calls = bool(tool_calls)
                    has_final_answer = False
                    conflict_retries = 0

            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer
                )

            if has_final_answer:
                if tool_calls_count < min_tool_calls:
                    messages.append({"role": "assistant", "content": response})
                    unused_tools = all_tools - used_tools
                    unused_hint = f"ï¼ˆè¿™äº›å·¥å…·è¿˜æœªä½¿ç”¨ï¼ŒæŽ¨èç”¨ä¸€ä¸‹ä»–ä»¬: {', '.join(unused_tools)}ï¼‰" if unused_tools else ""
                    messages.append({
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    })
                    continue

                final_answer = response.split("Final Answer:")[-1].strip()
                logger.info(t('report.sectionGenDone', title=section.title, count=tool_calls_count))

                if self.report_logger:
                    self.report_logger.log_section_content(
                        section_title=section.title,
                        section_index=section_index,
                        content=final_answer,
                        tool_calls_count=tool_calls_count
                    )
                return final_answer

            if has_tool_calls:
                if tool_calls_count >= self.MAX_TOOL_CALLS_PER_SECTION:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": REACT_TOOL_LIMIT_MSG.format(
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        ),
                    })
                    continue

                call = tool_calls[0]
                if len(tool_calls) > 1:
                    logger.info(t('report.multiToolOnlyFirst', total=len(tool_calls), toolName=call['name']))

                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        parameters=call.get("parameters", {}),
                        iteration=iteration + 1
                    )

                result = self._execute_tool(
                    call["name"],
                    call.get("parameters", {}),
                    report_context=report_context
                )

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        result=result,
                        iteration=iteration + 1
                    )

                tool_calls_count += 1
                used_tools.add(call['name'])

                unused_tools = all_tools - used_tools
                unused_hint = ""
                if unused_tools and tool_calls_count < self.MAX_TOOL_CALLS_PER_SECTION:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(unused_list="ã€".join(unused_tools))

                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": REACT_OBSERVATION_TEMPLATE.format(
                        tool_name=call["name"],
                        result=result,
                        tool_calls_count=tool_calls_count,
                        max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        used_tools_str=", ".join(used_tools),
                        unused_hint=unused_hint,
                    ),
                })
                continue

            messages.append({"role": "assistant", "content": response})

            if tool_calls_count < min_tool_calls:
                unused_tools = all_tools - used_tools
                unused_hint = f"ï¼ˆè¿™äº›å·¥å…·è¿˜æœªä½¿ç”¨ï¼ŒæŽ¨èç”¨ä¸€ä¸‹ä»–ä»¬: {', '.join(unused_tools)}ï¼‰" if unused_tools else ""

                messages.append({
                    "role": "user",
                    "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                        tool_calls_count=tool_calls_count,
                        min_tool_calls=min_tool_calls,
                        unused_hint=unused_hint,
                    ),
                })
                continue

            logger.info(t('report.sectionNoPrefix', title=section.title, count=tool_calls_count))
            final_answer = response.strip()

            if self.report_logger:
                self.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count
                )
            return final_answer
        
        logger.warning(t('report.sectionMaxIter', title=section.title))
        messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})
        
        response = self.llm.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=4096
        )

        if response is None:
            logger.error(t('report.sectionForceFailed', title=section.title))
            final_answer = t('report.sectionGenFailedContent')
        elif "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
        else:
            final_answer = response
        
        if self.report_logger:
            self.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count
            )
        
        return final_answer
    
    def generate_report(
        self, 
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None
    ) -> Report:
        """
        
        reports/{report_id}/
            ...
        
        Args:
            
        Returns:
        """
        import uuid
        
        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()
        
        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=datetime.now().isoformat()
        )
        
        completed_section_titles = []
        
        try:
            ReportManager._ensure_report_folder(report_id)
            
            self.report_logger = ReportLogger(report_id)
            self.report_logger.log_start(
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement
            )
            
            self.console_logger = ReportConsoleLogger(report_id)
            
            ReportManager.update_progress(
                report_id, "pending", 0, t('progress.initReport'),
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            report.status = ReportStatus.PLANNING
            ReportManager.update_progress(
                report_id, "planning", 5, t('progress.startPlanningOutline'),
                completed_sections=[]
            )
            
            self.report_logger.log_planning_start()
            
            if progress_callback:
                progress_callback("planning", 0, t('progress.startPlanningOutline'))
            
            outline = self.plan_outline(
                progress_callback=lambda stage, prog, msg: 
                    progress_callback(stage, prog // 5, msg) if progress_callback else None
            )
            report.outline = outline
            
            self.report_logger.log_planning_complete(outline.to_dict())
            
            ReportManager.save_outline(report_id, outline)
            ReportManager.update_progress(
                report_id, "planning", 15, t('progress.outlineDone', count=len(outline.sections)),
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            logger.info(t('report.outlineSavedToFile', reportId=report_id))
            
            report.status = ReportStatus.GENERATING
            
            total_sections = len(outline.sections)
            generated_sections = []  # ä¿å­˜å†…å®¹ç”¨äºŽä¸Šä¸‹æ–‡
            
            for i, section in enumerate(outline.sections):
                section_num = i + 1
                base_progress = 20 + int((i / total_sections) * 70)
                
                ReportManager.update_progress(
                    report_id, "generating", base_progress,
                    t('progress.generatingSection', title=section.title, current=section_num, total=total_sections),
                    current_section=section.title,
                    completed_sections=completed_section_titles
                )

                if progress_callback:
                    progress_callback(
                        "generating",
                        base_progress,
                        t('progress.generatingSection', title=section.title, current=section_num, total=total_sections)
                    )
                
                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, prog, msg:
                        progress_callback(
                            stage, 
                            base_progress + int(prog * 0.7 / total_sections),
                            msg
                        ) if progress_callback else None,
                    section_index=section_num
                )
                
                section.content = section_content
                generated_sections.append(f"## {section.title}\n\n{section_content}")

                ReportManager.save_section(report_id, section_num, section)
                completed_section_titles.append(section.title)

                full_section_content = f"## {section.title}\n\n{section_content}"

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=full_section_content.strip()
                    )

                logger.info(t('report.sectionSaved', reportId=report_id, sectionNum=f"{section_num:02d}"))
                
                ReportManager.update_progress(
                    report_id, "generating", 
                    base_progress + int(70 / total_sections),
                    t('progress.sectionDone', title=section.title),
                    current_section=None,
                    completed_sections=completed_section_titles
                )
            
            if progress_callback:
                progress_callback("generating", 95, t('progress.assemblingReport'))
            
            ReportManager.update_progress(
                report_id, "generating", 95, t('progress.assemblingReport'),
                completed_sections=completed_section_titles
            )
            
            report.markdown_content = ReportManager.assemble_full_report(report_id, outline)
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.now().isoformat()
            
            total_time_seconds = (datetime.now() - start_time).total_seconds()
            
            if self.report_logger:
                self.report_logger.log_report_complete(
                    total_sections=total_sections,
                    total_time_seconds=total_time_seconds
                )
            
            ReportManager.save_report(report)
            ReportManager.update_progress(
                report_id, "completed", 100, t('progress.reportComplete'),
                completed_sections=completed_section_titles
            )
            
            if progress_callback:
                progress_callback("completed", 100, t('progress.reportComplete'))
            
            logger.info(t('report.reportGenDone', reportId=report_id))
            
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
            
        except Exception as e:
            logger.error(t('report.reportGenFailed', error=str(e)))
            report.status = ReportStatus.FAILED
            report.error = str(e)
            
            if self.report_logger:
                self.report_logger.log_error(str(e), "failed")
            
            try:
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id, "failed", -1, t('progress.reportFailed', error=str(e)),
                    completed_sections=completed_section_titles
                )
            except Exception:
                pass  # å¿½ç•¥ä¿å­˜å¤±è´¥çš„é”™è¯¯
            
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
    
    def chat(
        self, 
        message: str,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        
        
        Args:
            
        Returns:
            {
            }
        """
        logger.info(t('report.agentChat', message=message[:50]))
        
        chat_history = chat_history or []
        
        report_content = ""
        try:
            report = ReportManager.get_report_by_simulation(self.simulation_id)
            if report and report.markdown_content:
                report_content = report.markdown_content[:15000]
                if len(report.markdown_content) > 15000:
                    report_content += "\n\n... [æŠ¥å‘Šå†…å®¹å·²æˆªæ–­] ..."
        except Exception as e:
            logger.warning(t('report.fetchReportFailed', error=e))
        
        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "ï¼ˆæš‚æ— æŠ¥å‘Šï¼‰",
            tools_description=self._get_tools_description(),
        )
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}"

        messages = [{"role": "system", "content": system_prompt}]
        
        for h in chat_history[-10:]:  # é™åˆ¶åŽ†å²é•¿åº¦
            messages.append(h)
        
        messages.append({
            "role": "user", 
            "content": message
        })
        
        tool_calls_made = []
        max_iterations = 2  # å‡å°‘è¿­ä»£è½®æ•°
        
        for iteration in range(max_iterations):
            response = self.llm.chat(
                messages=messages,
                temperature=0.5
            )
            
            tool_calls = self._parse_tool_calls(response)
            
            if not tool_calls:
                clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', response, flags=re.DOTALL)
                clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
                
                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
                }
            
            tool_results = []
            for call in tool_calls[:1]:  # æ¯è½®æœ€å¤šæ‰§è¡Œ1æ¬¡å·¥å…·è°ƒç”¨
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                result = self._execute_tool(call["name"], call.get("parameters", {}))
                tool_results.append({
                    "tool": call["name"],
                    "result": result[:1500]  # é™åˆ¶ç»“æžœé•¿åº¦
                })
                tool_calls_made.append(call)
            
            messages.append({"role": "assistant", "content": response})
            observation = "\n".join([f"[{r['tool']}ç»“æžœ]\n{r['result']}" for r in tool_results])
            messages.append({
                "role": "user",
                "content": observation + CHAT_OBSERVATION_SUFFIX
            })
        
        final_response = self.llm.chat(
            messages=messages,
            temperature=0.5
        )
        
        clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', final_response, flags=re.DOTALL)
        clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
        
        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
        }


class ReportManager:
    """
    
    
    reports/
      {report_id}/
        ...
    """
    
    REPORTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'reports')
    
    @classmethod
    def _ensure_reports_dir(cls):
        """ç¡®ä¿æŠ¥å‘Šæ ¹ç›®å½•å­˜åœ¨"""
        os.makedirs(cls.REPORTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_report_folder(cls, report_id: str) -> str:
        """èŽ·å–æŠ¥å‘Šæ–‡ä»¶å¤¹è·¯å¾„"""
        return os.path.join(cls.REPORTS_DIR, report_id)
    
    @classmethod
    def _ensure_report_folder(cls, report_id: str) -> str:
        """ç¡®ä¿æŠ¥å‘Šæ–‡ä»¶å¤¹å­˜åœ¨å¹¶è¿”å›žè·¯å¾„"""
        folder = cls._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        return folder
    
    @classmethod
    def _get_report_path(cls, report_id: str) -> str:
        """èŽ·å–æŠ¥å‘Šå…ƒä¿¡æ¯æ–‡ä»¶è·¯å¾„"""
        return os.path.join(cls._get_report_folder(report_id), "meta.json")
    
    @classmethod
    def _get_report_markdown_path(cls, report_id: str) -> str:
        """èŽ·å–å®Œæ•´æŠ¥å‘ŠMarkdownæ–‡ä»¶è·¯å¾„"""
        return os.path.join(cls._get_report_folder(report_id), "full_report.md")
    
    @classmethod
    def _get_outline_path(cls, report_id: str) -> str:
        """èŽ·å–å¤§çº²æ–‡ä»¶è·¯å¾„"""
        return os.path.join(cls._get_report_folder(report_id), "outline.json")
    
    @classmethod
    def _get_progress_path(cls, report_id: str) -> str:
        """èŽ·å–è¿›åº¦æ–‡ä»¶è·¯å¾„"""
        return os.path.join(cls._get_report_folder(report_id), "progress.json")
    
    @classmethod
    def _get_section_path(cls, report_id: str, section_index: int) -> str:
        """èŽ·å–ç« èŠ‚Markdownæ–‡ä»¶è·¯å¾„"""
        return os.path.join(cls._get_report_folder(report_id), f"section_{section_index:02d}.md")
    
    @classmethod
    def _get_agent_log_path(cls, report_id: str) -> str:
        """èŽ·å– Agent æ—¥å¿—æ–‡ä»¶è·¯å¾„"""
        return os.path.join(cls._get_report_folder(report_id), "agent_log.jsonl")
    
    @classmethod
    def _get_console_log_path(cls, report_id: str) -> str:
        """èŽ·å–æŽ§åˆ¶å°æ—¥å¿—æ–‡ä»¶è·¯å¾„"""
        return os.path.join(cls._get_report_folder(report_id), "console_log.txt")
    
    @classmethod
    def get_console_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        
        
        Args:
            
        Returns:
            {
            }
        """
        log_path = cls._get_console_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    logs.append(line.rstrip('\n\r'))
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # å·²è¯»å–åˆ°æœ«å°¾
        }
    
    @classmethod
    def get_console_log_stream(cls, report_id: str) -> List[str]:
        """
        
        Args:
            
        Returns:
        """
        result = cls.get_console_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def get_agent_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        
        Args:
            
        Returns:
            {
            }
        """
        log_path = cls._get_agent_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        continue
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # å·²è¯»å–åˆ°æœ«å°¾
        }
    
    @classmethod
    def get_agent_log_stream(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        
        Args:
            
        Returns:
        """
        result = cls.get_agent_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def save_outline(cls, report_id: str, outline: ReportOutline) -> None:
        """
        
        """
        cls._ensure_report_folder(report_id)
        
        with open(cls._get_outline_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(outline.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(t('report.outlineSaved', reportId=report_id))
    
    @classmethod
    def save_section(
        cls,
        report_id: str,
        section_index: int,
        section: ReportSection
    ) -> str:
        """


        Args:

        Returns:
        """
        cls._ensure_report_folder(report_id)

        cleaned_content = cls._clean_section_content(section.content, section.title)
        md_content = f"## {section.title}\n\n"
        if cleaned_content:
            md_content += f"{cleaned_content}\n\n"

        file_suffix = f"section_{section_index:02d}.md"
        file_path = os.path.join(cls._get_report_folder(report_id), file_suffix)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        logger.info(t('report.sectionFileSaved', reportId=report_id, fileSuffix=file_suffix))
        return file_path
    
    @classmethod
    def _clean_section_content(cls, content: str, section_title: str) -> str:
        """
        
        
        Args:
            
        Returns:
        """
        import re
        
        if not content:
            return content
        
        content = content.strip()
        lines = content.split('\n')
        cleaned_lines = []
        skip_next_empty = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title_text = heading_match.group(2).strip()
                
                if i < 5:
                    if title_text == section_title or title_text.replace(' ', '') == section_title.replace(' ', ''):
                        skip_next_empty = True
                        continue
                
                cleaned_lines.append(f"**{title_text}**")
                cleaned_lines.append("")  # æ·»åŠ ç©ºè¡Œ
                continue
            
            if skip_next_empty and stripped == '':
                skip_next_empty = False
                continue
            
            skip_next_empty = False
            cleaned_lines.append(line)
        
        while cleaned_lines and cleaned_lines[0].strip() == '':
            cleaned_lines.pop(0)
        
        while cleaned_lines and cleaned_lines[0].strip() in ['---', '***', '___']:
            cleaned_lines.pop(0)
            while cleaned_lines and cleaned_lines[0].strip() == '':
                cleaned_lines.pop(0)
        
        return '\n'.join(cleaned_lines)
    
    @classmethod
    def update_progress(
        cls, 
        report_id: str, 
        status: str, 
        progress: int, 
        message: str,
        current_section: str = None,
        completed_sections: List[str] = None
    ) -> None:
        """
        
        """
        cls._ensure_report_folder(report_id)
        
        progress_data = {
            "status": status,
            "progress": progress,
            "message": message,
            "current_section": current_section,
            "completed_sections": completed_sections or [],
            "updated_at": datetime.now().isoformat()
        }
        
        with open(cls._get_progress_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def get_progress(cls, report_id: str) -> Optional[Dict[str, Any]]:
        """èŽ·å–æŠ¥å‘Šç”Ÿæˆè¿›åº¦"""
        path = cls._get_progress_path(report_id)
        
        if not os.path.exists(path):
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @classmethod
    def get_generated_sections(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        
        """
        folder = cls._get_report_folder(report_id)
        
        if not os.path.exists(folder):
            return []
        
        sections = []
        for filename in sorted(os.listdir(folder)):
            if filename.startswith('section_') and filename.endswith('.md'):
                file_path = os.path.join(folder, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                parts = filename.replace('.md', '').split('_')
                section_index = int(parts[1])

                sections.append({
                    "filename": filename,
                    "section_index": section_index,
                    "content": content
                })

        return sections
    
    @classmethod
    def assemble_full_report(cls, report_id: str, outline: ReportOutline) -> str:
        """
        
        """
        folder = cls._get_report_folder(report_id)
        
        md_content = f"# {outline.title}\n\n"
        md_content += f"> {outline.summary}\n\n"
        md_content += f"---\n\n"
        
        sections = cls.get_generated_sections(report_id)
        for section_info in sections:
            md_content += section_info["content"]
        
        md_content = cls._post_process_report(md_content, outline)
        
        full_path = cls._get_report_markdown_path(report_id)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(t('report.fullReportAssembled', reportId=report_id))
        return md_content
    
    @classmethod
    def _post_process_report(cls, content: str, outline: ReportOutline) -> str:
        """
        
        
        Args:
            
        Returns:
        """
        import re
        
        lines = content.split('\n')
        processed_lines = []
        prev_was_heading = False
        
        section_titles = set()
        for section in outline.sections:
            section_titles.add(section.title)
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                is_duplicate = False
                for j in range(max(0, len(processed_lines) - 5), len(processed_lines)):
                    prev_line = processed_lines[j].strip()
                    prev_match = re.match(r'^(#{1,6})\s+(.+)$', prev_line)
                    if prev_match:
                        prev_title = prev_match.group(2).strip()
                        if prev_title == title:
                            is_duplicate = True
                            break
                
                if is_duplicate:
                    i += 1
                    while i < len(lines) and lines[i].strip() == '':
                        i += 1
                    continue
                
                
                if level == 1:
                    if title == outline.title:
                        processed_lines.append(line)
                        prev_was_heading = True
                    elif title in section_titles:
                        processed_lines.append(f"## {title}")
                        prev_was_heading = True
                    else:
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                elif level == 2:
                    if title in section_titles or title == outline.title:
                        processed_lines.append(line)
                        prev_was_heading = True
                    else:
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                else:
                    processed_lines.append(f"**{title}**")
                    processed_lines.append("")
                    prev_was_heading = False
                
                i += 1
                continue
            
            elif stripped == '---' and prev_was_heading:
                i += 1
                continue
            
            elif stripped == '' and prev_was_heading:
                if processed_lines and processed_lines[-1].strip() != '':
                    processed_lines.append(line)
                prev_was_heading = False
            
            else:
                processed_lines.append(line)
                prev_was_heading = False
            
            i += 1
        
        result_lines = []
        empty_count = 0
        for line in processed_lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= 2:
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    @classmethod
    def save_report(cls, report: Report) -> None:
        """ä¿å­˜æŠ¥å‘Šå…ƒä¿¡æ¯å’Œå®Œæ•´æŠ¥å‘Š"""
        cls._ensure_report_folder(report.report_id)
        
        with open(cls._get_report_path(report.report_id), 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        
        if report.outline:
            cls.save_outline(report.report_id, report.outline)
        
        if report.markdown_content:
            with open(cls._get_report_markdown_path(report.report_id), 'w', encoding='utf-8') as f:
                f.write(report.markdown_content)
        
        logger.info(t('report.reportSaved', reportId=report.report_id))
    
    @classmethod
    def get_report(cls, report_id: str) -> Optional[Report]:
        """èŽ·å–æŠ¥å‘Š"""
        path = cls._get_report_path(report_id)
        
        if not os.path.exists(path):
            old_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
            if os.path.exists(old_path):
                path = old_path
            else:
                return None
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        outline = None
        if data.get('outline'):
            outline_data = data['outline']
            sections = []
            for s in outline_data.get('sections', []):
                sections.append(ReportSection(
                    title=s['title'],
                    content=s.get('content', '')
                ))
            outline = ReportOutline(
                title=outline_data['title'],
                summary=outline_data['summary'],
                sections=sections
            )
        
        markdown_content = data.get('markdown_content', '')
        if not markdown_content:
            full_report_path = cls._get_report_markdown_path(report_id)
            if os.path.exists(full_report_path):
                with open(full_report_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
        
        return Report(
            report_id=data['report_id'],
            simulation_id=data['simulation_id'],
            graph_id=data['graph_id'],
            simulation_requirement=data['simulation_requirement'],
            status=ReportStatus(data['status']),
            outline=outline,
            markdown_content=markdown_content,
            created_at=data.get('created_at', ''),
            completed_at=data.get('completed_at', ''),
            error=data.get('error')
        )
    
    @classmethod
    def get_report_by_simulation(cls, simulation_id: str) -> Optional[Report]:
        """æ ¹æ®æ¨¡æ‹ŸIDèŽ·å–æŠ¥å‘Š"""
        cls._ensure_reports_dir()
        
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report and report.simulation_id == simulation_id:
                    return report
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report and report.simulation_id == simulation_id:
                    return report
        
        return None
    
    @classmethod
    def list_reports(cls, simulation_id: Optional[str] = None, limit: int = 50) -> List[Report]:
        """åˆ—å‡ºæŠ¥å‘Š"""
        cls._ensure_reports_dir()
        
        reports = []
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
        
        reports.sort(key=lambda r: r.created_at, reverse=True)
        
        return reports[:limit]
    
    @classmethod
    def delete_report(cls, report_id: str) -> bool:
        """åˆ é™¤æŠ¥å‘Šï¼ˆæ•´ä¸ªæ–‡ä»¶å¤¹ï¼‰"""
        import shutil
        
        folder_path = cls._get_report_folder(report_id)
        
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            logger.info(t('report.reportFolderDeleted', reportId=report_id))
            return True
        
        deleted = False
        old_json_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
        old_md_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.md")
        
        if os.path.exists(old_json_path):
            os.remove(old_json_path)
            deleted = True
        if os.path.exists(old_md_path):
            os.remove(old_md_path)
            deleted = True
        
        return deleted

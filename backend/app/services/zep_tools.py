"""
Zepæ£€ç´¢å·¥å…·æœåŠ¡
å°è£…å›¾è°±æœç´¢ã€èŠ‚ç‚¹è¯»å–ã€è¾¹æŸ¥è¯¢ç­‰å·¥å…·ï¼Œä¾›Report Agentä½¿ç”¨

æ ¸å¿ƒæ£€ç´¢å·¥å…·ï¼ˆä¼˜åŒ–åŽï¼‰ï¼š
1. InsightForgeï¼ˆæ·±åº¦æ´žå¯Ÿæ£€ç´¢ï¼‰- æœ€å¼ºå¤§çš„æ··åˆæ£€ç´¢ï¼Œè‡ªåŠ¨ç”Ÿæˆå­é—®é¢˜å¹¶å¤šç»´åº¦æ£€ç´¢
2. PanoramaSearchï¼ˆå¹¿åº¦æœç´¢ï¼‰- èŽ·å–å…¨è²Œï¼ŒåŒ…æ‹¬è¿‡æœŸå†…å®¹
3. QuickSearchï¼ˆç®€å•æœç´¢ï¼‰- å¿«é€Ÿæ£€ç´¢
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.locale import get_locale, t
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger('posiedon.zep_tools')


@dataclass
class SearchResult:
    """æœç´¢ç»“æžœ"""
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count
        }
    
    def to_text(self) -> str:
        """è½¬æ¢ä¸ºæ–‡æœ¬æ ¼å¼ï¼Œä¾›LLMç†è§£"""
        text_parts = [f"æœç´¢æŸ¥è¯¢: {self.query}", f"æ‰¾åˆ° {self.total_count} æ¡ç›¸å…³ä¿¡æ¯"]
        
        if self.facts:
            text_parts.append("\n### ç›¸å…³äº‹å®ž:")
            for i, fact in enumerate(self.facts, 1):
                text_parts.append(f"{i}. {fact}")
        
        return "\n".join(text_parts)


@dataclass
class NodeInfo:
    """èŠ‚ç‚¹ä¿¡æ¯"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes
        }
    
    def to_text(self) -> str:
        """è½¬æ¢ä¸ºæ–‡æœ¬æ ¼å¼"""
        entity_type = next((l for l in self.labels if l not in ["Entity", "Node"]), "æœªçŸ¥ç±»åž‹")
        return f"å®žä½“: {self.name} (ç±»åž‹: {entity_type})\næ‘˜è¦: {self.summary}"


@dataclass
class EdgeInfo:
    """è¾¹ä¿¡æ¯"""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
    # æ—¶é—´ä¿¡æ¯
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at
        }
    
    def to_text(self, include_temporal: bool = False) -> str:
        """è½¬æ¢ä¸ºæ–‡æœ¬æ ¼å¼"""
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        base_text = f"å…³ç³»: {source} --[{self.name}]--> {target}\näº‹å®ž: {self.fact}"
        
        if include_temporal:
            valid_at = self.valid_at or "æœªçŸ¥"
            invalid_at = self.invalid_at or "è‡³ä»Š"
            base_text += f"\næ—¶æ•ˆ: {valid_at} - {invalid_at}"
            if self.expired_at:
                base_text += f" (å·²è¿‡æœŸ: {self.expired_at})"
        
        return base_text
    
    @property
    def is_expired(self) -> bool:
        """æ˜¯å¦å·²è¿‡æœŸ"""
        return self.expired_at is not None
    
    @property
    def is_invalid(self) -> bool:
        """æ˜¯å¦å·²å¤±æ•ˆ"""
        return self.invalid_at is not None


@dataclass
class InsightForgeResult:
    """
    æ·±åº¦æ´žå¯Ÿæ£€ç´¢ç»“æžœ (InsightForge)
    åŒ…å«å¤šä¸ªå­é—®é¢˜çš„æ£€ç´¢ç»“æžœï¼Œä»¥åŠç»¼åˆåˆ†æž
    """
    query: str
    simulation_requirement: str
    sub_queries: List[str]
    
    # å„ç»´åº¦æ£€ç´¢ç»“æžœ
    semantic_facts: List[str] = field(default_factory=list)  # è¯­ä¹‰æœç´¢ç»“æžœ
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)  # å®žä½“æ´žå¯Ÿ
    relationship_chains: List[str] = field(default_factory=list)  # å…³ç³»é“¾
    
    # ç»Ÿè®¡ä¿¡æ¯
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships
        }
    
    def to_text(self) -> str:
        """è½¬æ¢ä¸ºè¯¦ç»†çš„æ–‡æœ¬æ ¼å¼ï¼Œä¾›LLMç†è§£"""
        text_parts = [
            f"## æœªæ¥é¢„æµ‹æ·±åº¦åˆ†æž",
            f"åˆ†æžé—®é¢˜: {self.query}",
            f"é¢„æµ‹åœºæ™¯: {self.simulation_requirement}",
            f"\n### é¢„æµ‹æ•°æ®ç»Ÿè®¡",
            f"- ç›¸å…³é¢„æµ‹äº‹å®ž: {self.total_facts}æ¡",
            f"- æ¶‰åŠå®žä½“: {self.total_entities}ä¸ª",
            f"- å…³ç³»é“¾: {self.total_relationships}æ¡"
        ]
        
        # å­é—®é¢˜
        if self.sub_queries:
            text_parts.append(f"\n### åˆ†æžçš„å­é—®é¢˜")
            for i, sq in enumerate(self.sub_queries, 1):
                text_parts.append(f"{i}. {sq}")
        
        # è¯­ä¹‰æœç´¢ç»“æžœ
        if self.semantic_facts:
            text_parts.append(f"\n### ã€å…³é”®äº‹å®žã€‘(è¯·åœ¨æŠ¥å‘Šä¸­å¼•ç”¨è¿™äº›åŽŸæ–‡)")
            for i, fact in enumerate(self.semantic_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # å®žä½“æ´žå¯Ÿ
        if self.entity_insights:
            text_parts.append(f"\n### ã€æ ¸å¿ƒå®žä½“ã€‘")
            for entity in self.entity_insights:
                text_parts.append(f"- **{entity.get('name', 'æœªçŸ¥')}** ({entity.get('type', 'å®žä½“')})")
                if entity.get('summary'):
                    text_parts.append(f"  æ‘˜è¦: \"{entity.get('summary')}\"")
                if entity.get('related_facts'):
                    text_parts.append(f"  ç›¸å…³äº‹å®ž: {len(entity.get('related_facts', []))}æ¡")
        
        # å…³ç³»é“¾
        if self.relationship_chains:
            text_parts.append(f"\n### ã€å…³ç³»é“¾ã€‘")
            for chain in self.relationship_chains:
                text_parts.append(f"- {chain}")
        
        return "\n".join(text_parts)


@dataclass
class PanoramaResult:
    """
    å¹¿åº¦æœç´¢ç»“æžœ (Panorama)
    åŒ…å«æ‰€æœ‰ç›¸å…³ä¿¡æ¯ï¼ŒåŒ…æ‹¬è¿‡æœŸå†…å®¹
    """
    query: str
    
    # å…¨éƒ¨èŠ‚ç‚¹
    all_nodes: List[NodeInfo] = field(default_factory=list)
    # å…¨éƒ¨è¾¹ï¼ˆåŒ…æ‹¬è¿‡æœŸçš„ï¼‰
    all_edges: List[EdgeInfo] = field(default_factory=list)
    # å½“å‰æœ‰æ•ˆçš„äº‹å®ž
    active_facts: List[str] = field(default_factory=list)
    # å·²è¿‡æœŸ/å¤±æ•ˆçš„äº‹å®žï¼ˆåŽ†å²è®°å½•ï¼‰
    historical_facts: List[str] = field(default_factory=list)
    
    # ç»Ÿè®¡
    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [n.to_dict() for n in self.all_nodes],
            "all_edges": [e.to_dict() for e in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count
        }
    
    def to_text(self) -> str:
        """è½¬æ¢ä¸ºæ–‡æœ¬æ ¼å¼ï¼ˆå®Œæ•´ç‰ˆæœ¬ï¼Œä¸æˆªæ–­ï¼‰"""
        text_parts = [
            f"## å¹¿åº¦æœç´¢ç»“æžœï¼ˆæœªæ¥å…¨æ™¯è§†å›¾ï¼‰",
            f"æŸ¥è¯¢: {self.query}",
            f"\n### ç»Ÿè®¡ä¿¡æ¯",
            f"- æ€»èŠ‚ç‚¹æ•°: {self.total_nodes}",
            f"- æ€»è¾¹æ•°: {self.total_edges}",
            f"- å½“å‰æœ‰æ•ˆäº‹å®ž: {self.active_count}æ¡",
            f"- åŽ†å²/è¿‡æœŸäº‹å®ž: {self.historical_count}æ¡"
        ]
        
        # å½“å‰æœ‰æ•ˆçš„äº‹å®žï¼ˆå®Œæ•´è¾“å‡ºï¼Œä¸æˆªæ–­ï¼‰
        if self.active_facts:
            text_parts.append(f"\n### ã€å½“å‰æœ‰æ•ˆäº‹å®žã€‘(æ¨¡æ‹Ÿç»“æžœåŽŸæ–‡)")
            for i, fact in enumerate(self.active_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # åŽ†å²/è¿‡æœŸäº‹å®žï¼ˆå®Œæ•´è¾“å‡ºï¼Œä¸æˆªæ–­ï¼‰
        if self.historical_facts:
            text_parts.append(f"\n### ã€åŽ†å²/è¿‡æœŸäº‹å®žã€‘(æ¼”å˜è¿‡ç¨‹è®°å½•)")
            for i, fact in enumerate(self.historical_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # å…³é”®å®žä½“ï¼ˆå®Œæ•´è¾“å‡ºï¼Œä¸æˆªæ–­ï¼‰
        if self.all_nodes:
            text_parts.append(f"\n### ã€æ¶‰åŠå®žä½“ã€‘")
            for node in self.all_nodes:
                entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "å®žä½“")
                text_parts.append(f"- **{node.name}** ({entity_type})")
        
        return "\n".join(text_parts)


@dataclass
class AgentInterview:
    """å•ä¸ªAgentçš„é‡‡è®¿ç»“æžœ"""
    agent_name: str
    agent_role: str  # è§’è‰²ç±»åž‹ï¼ˆå¦‚ï¼šå­¦ç”Ÿã€æ•™å¸ˆã€åª’ä½“ç­‰ï¼‰
    agent_bio: str  # ç®€ä»‹
    question: str  # é‡‡è®¿é—®é¢˜
    response: str  # é‡‡è®¿å›žç­”
    key_quotes: List[str] = field(default_factory=list)  # å…³é”®å¼•è¨€
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes
        }
    
    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        # æ˜¾ç¤ºå®Œæ•´çš„agent_bioï¼Œä¸æˆªæ–­
        text += f"_ç®€ä»‹: {self.agent_bio}_\n\n"
        text += f"**Q:** {self.question}\n\n"
        text += f"**A:** {self.response}\n"
        if self.key_quotes:
            text += "\n**å…³é”®å¼•è¨€:**\n"
            for quote in self.key_quotes:
                # æ¸…ç†å„ç§å¼•å·
                clean_quote = quote.replace('\u201c', '').replace('\u201d', '').replace('"', '')
                clean_quote = clean_quote.replace('\u300c', '').replace('\u300d', '')
                clean_quote = clean_quote.strip()
                # åŽ»æŽ‰å¼€å¤´çš„æ ‡ç‚¹
                while clean_quote and clean_quote[0] in 'ï¼Œ,ï¼›;ï¼š:ã€ã€‚ï¼ï¼Ÿ\n\r\t ':
                    clean_quote = clean_quote[1:]
                # è¿‡æ»¤åŒ…å«é—®é¢˜ç¼–å·çš„åžƒåœ¾å†…å®¹ï¼ˆé—®é¢˜1-9ï¼‰
                skip = False
                for d in '123456789':
                    if f'\u95ee\u9898{d}' in clean_quote:
                        skip = True
                        break
                if skip:
                    continue
                # æˆªæ–­è¿‡é•¿å†…å®¹ï¼ˆæŒ‰å¥å·æˆªæ–­ï¼Œè€Œéžç¡¬æˆªæ–­ï¼‰
                if len(clean_quote) > 150:
                    dot_pos = clean_quote.find('\u3002', 80)
                    if dot_pos > 0:
                        clean_quote = clean_quote[:dot_pos + 1]
                    else:
                        clean_quote = clean_quote[:147] + "..."
                if clean_quote and len(clean_quote) >= 10:
                    text += f'> "{clean_quote}"\n'
        return text


@dataclass
class InterviewResult:
    """
    é‡‡è®¿ç»“æžœ (Interview)
    åŒ…å«å¤šä¸ªæ¨¡æ‹ŸAgentçš„é‡‡è®¿å›žç­”
    """
    interview_topic: str  # é‡‡è®¿ä¸»é¢˜
    interview_questions: List[str]  # é‡‡è®¿é—®é¢˜åˆ—è¡¨
    
    # é‡‡è®¿é€‰æ‹©çš„Agent
    selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    # å„Agentçš„é‡‡è®¿å›žç­”
    interviews: List[AgentInterview] = field(default_factory=list)
    
    # é€‰æ‹©Agentçš„ç†ç”±
    selection_reasoning: str = ""
    # æ•´åˆåŽçš„é‡‡è®¿æ‘˜è¦
    summary: str = ""
    
    # ç»Ÿè®¡
    total_agents: int = 0
    interviewed_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "selected_agents": self.selected_agents,
            "interviews": [i.to_dict() for i in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count
        }
    
    def to_text(self) -> str:
        """è½¬æ¢ä¸ºè¯¦ç»†çš„æ–‡æœ¬æ ¼å¼ï¼Œä¾›LLMç†è§£å’ŒæŠ¥å‘Šå¼•ç”¨"""
        text_parts = [
            "## æ·±åº¦é‡‡è®¿æŠ¥å‘Š",
            f"**é‡‡è®¿ä¸»é¢˜:** {self.interview_topic}",
            f"**é‡‡è®¿äººæ•°:** {self.interviewed_count} / {self.total_agents} ä½æ¨¡æ‹ŸAgent",
            "\n### é‡‡è®¿å¯¹è±¡é€‰æ‹©ç†ç”±",
            self.selection_reasoning or "ï¼ˆè‡ªåŠ¨é€‰æ‹©ï¼‰",
            "\n---",
            "\n### é‡‡è®¿å®žå½•",
        ]

        if self.interviews:
            for i, interview in enumerate(self.interviews, 1):
                text_parts.append(f"\n#### é‡‡è®¿ #{i}: {interview.agent_name}")
                text_parts.append(interview.to_text())
                text_parts.append("\n---")
        else:
            text_parts.append("ï¼ˆæ— é‡‡è®¿è®°å½•ï¼‰\n\n---")

        text_parts.append("\n### é‡‡è®¿æ‘˜è¦ä¸Žæ ¸å¿ƒè§‚ç‚¹")
        text_parts.append(self.summary or "ï¼ˆæ— æ‘˜è¦ï¼‰")

        return "\n".join(text_parts)


class ZepToolsService:
    """
    Zepæ£€ç´¢å·¥å…·æœåŠ¡
    
    ã€æ ¸å¿ƒæ£€ç´¢å·¥å…· - ä¼˜åŒ–åŽã€‘
    1. insight_forge - æ·±åº¦æ´žå¯Ÿæ£€ç´¢ï¼ˆæœ€å¼ºå¤§ï¼Œè‡ªåŠ¨ç”Ÿæˆå­é—®é¢˜ï¼Œå¤šç»´åº¦æ£€ç´¢ï¼‰
    2. panorama_search - å¹¿åº¦æœç´¢ï¼ˆèŽ·å–å…¨è²Œï¼ŒåŒ…æ‹¬è¿‡æœŸå†…å®¹ï¼‰
    3. quick_search - ç®€å•æœç´¢ï¼ˆå¿«é€Ÿæ£€ç´¢ï¼‰
    4. interview_agents - æ·±åº¦é‡‡è®¿ï¼ˆé‡‡è®¿æ¨¡æ‹ŸAgentï¼ŒèŽ·å–å¤šè§†è§’è§‚ç‚¹ï¼‰
    
    ã€åŸºç¡€å·¥å…·ã€‘
    - search_graph - å›¾è°±è¯­ä¹‰æœç´¢
    - get_all_nodes - èŽ·å–å›¾è°±æ‰€æœ‰èŠ‚ç‚¹
    - get_all_edges - èŽ·å–å›¾è°±æ‰€æœ‰è¾¹ï¼ˆå«æ—¶é—´ä¿¡æ¯ï¼‰
    - get_node_detail - èŽ·å–èŠ‚ç‚¹è¯¦ç»†ä¿¡æ¯
    - get_node_edges - èŽ·å–èŠ‚ç‚¹ç›¸å…³çš„è¾¹
    - get_entities_by_type - æŒ‰ç±»åž‹èŽ·å–å®žä½“
    - get_entity_summary - èŽ·å–å®žä½“çš„å…³ç³»æ‘˜è¦
    """
    
    # é‡è¯•é…ç½®
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    
    def __init__(self, api_key: Optional[str] = None, llm_client: Optional[LLMClient] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY æœªé…ç½®")
        
        self.client = Zep(api_key=self.api_key)
        # LLMå®¢æˆ·ç«¯ç”¨äºŽInsightForgeç”Ÿæˆå­é—®é¢˜
        self._llm_client = llm_client
        logger.info(t("console.zepToolsInitialized"))
    
    @property
    def llm(self) -> LLMClient:
        """å»¶è¿Ÿåˆå§‹åŒ–LLMå®¢æˆ·ç«¯"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client
    
    def _call_with_retry(self, func, operation_name: str, max_retries: int = None):
        """å¸¦é‡è¯•æœºåˆ¶çš„APIè°ƒç”¨"""
        max_retries = max_retries or self.MAX_RETRIES
        last_exception = None
        delay = self.RETRY_DELAY
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        t("console.zepRetryAttempt", operation=operation_name, attempt=attempt + 1, error=str(e)[:100], delay=f"{delay:.1f}")
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(t("console.zepAllRetriesFailed", operation=operation_name, retries=max_retries, error=str(e)))
        
        raise last_exception
    
    def search_graph(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        å›¾è°±è¯­ä¹‰æœç´¢
        
        ä½¿ç”¨æ··åˆæœç´¢ï¼ˆè¯­ä¹‰+BM25ï¼‰åœ¨å›¾è°±ä¸­æœç´¢ç›¸å…³ä¿¡æ¯ã€‚
        å¦‚æžœZep Cloudçš„search APIä¸å¯ç”¨ï¼Œåˆ™é™çº§ä¸ºæœ¬åœ°å…³é”®è¯åŒ¹é…ã€‚
        
        Args:
            graph_id: å›¾è°±ID (Standalone Graph)
            query: æœç´¢æŸ¥è¯¢
            limit: è¿”å›žç»“æžœæ•°é‡
            scope: æœç´¢èŒƒå›´ï¼Œ"edges" æˆ– "nodes"
            
        Returns:
            SearchResult: æœç´¢ç»“æžœ
        """
        logger.info(t("console.graphSearch", graphId=graph_id, query=query[:50]))
        
        # å°è¯•ä½¿ç”¨Zep Cloud Search API
        try:
            search_results = self._call_with_retry(
                func=lambda: self.client.graph.search(
                    graph_id=graph_id,
                    query=query,
                    limit=limit,
                    scope=scope,
                    reranker="cross_encoder"
                ),
                operation_name=t("console.graphSearchOp", graphId=graph_id)
            )
            
            facts = []
            edges = []
            nodes = []
            
            # è§£æžè¾¹æœç´¢ç»“æžœ
            if hasattr(search_results, 'edges') and search_results.edges:
                for edge in search_results.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        facts.append(edge.fact)
                    edges.append({
                        "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                        "name": getattr(edge, 'name', ''),
                        "fact": getattr(edge, 'fact', ''),
                        "source_node_uuid": getattr(edge, 'source_node_uuid', ''),
                        "target_node_uuid": getattr(edge, 'target_node_uuid', ''),
                    })
            
            # è§£æžèŠ‚ç‚¹æœç´¢ç»“æžœ
            if hasattr(search_results, 'nodes') and search_results.nodes:
                for node in search_results.nodes:
                    nodes.append({
                        "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                        "name": getattr(node, 'name', ''),
                        "labels": getattr(node, 'labels', []),
                        "summary": getattr(node, 'summary', ''),
                    })
                    # èŠ‚ç‚¹æ‘˜è¦ä¹Ÿç®—ä½œäº‹å®ž
                    if hasattr(node, 'summary') and node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(t("console.searchComplete", count=len(facts)))
            
            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=nodes,
                query=query,
                total_count=len(facts)
            )
            
        except Exception as e:
            logger.warning(t("console.zepSearchApiFallback", error=str(e)))
            # é™çº§ï¼šä½¿ç”¨æœ¬åœ°å…³é”®è¯åŒ¹é…æœç´¢
            return self._local_search(graph_id, query, limit, scope)
    
    def _local_search(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        æœ¬åœ°å…³é”®è¯åŒ¹é…æœç´¢ï¼ˆä½œä¸ºZep Search APIçš„é™çº§æ–¹æ¡ˆï¼‰
        
        èŽ·å–æ‰€æœ‰è¾¹/èŠ‚ç‚¹ï¼Œç„¶åŽåœ¨æœ¬åœ°è¿›è¡Œå…³é”®è¯åŒ¹é…
        
        Args:
            graph_id: å›¾è°±ID
            query: æœç´¢æŸ¥è¯¢
            limit: è¿”å›žç»“æžœæ•°é‡
            scope: æœç´¢èŒƒå›´
            
        Returns:
            SearchResult: æœç´¢ç»“æžœ
        """
        logger.info(t("console.usingLocalSearch", query=query[:30]))
        
        facts = []
        edges_result = []
        nodes_result = []
        
        # æå–æŸ¥è¯¢å…³é”®è¯ï¼ˆç®€å•åˆ†è¯ï¼‰
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('ï¼Œ', ' ').split() if len(w.strip()) > 1]
        
        def match_score(text: str) -> int:
            """è®¡ç®—æ–‡æœ¬ä¸ŽæŸ¥è¯¢çš„åŒ¹é…åˆ†æ•°"""
            if not text:
                return 0
            text_lower = text.lower()
            # å®Œå…¨åŒ¹é…æŸ¥è¯¢
            if query_lower in text_lower:
                return 100
            # å…³é”®è¯åŒ¹é…
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 10
            return score
        
        try:
            if scope in ["edges", "both"]:
                # èŽ·å–æ‰€æœ‰è¾¹å¹¶åŒ¹é…
                all_edges = self.get_all_edges(graph_id)
                scored_edges = []
                for edge in all_edges:
                    score = match_score(edge.fact) + match_score(edge.name)
                    if score > 0:
                        scored_edges.append((score, edge))
                
                # æŒ‰åˆ†æ•°æŽ’åº
                scored_edges.sort(key=lambda x: x[0], reverse=True)
                
                for score, edge in scored_edges[:limit]:
                    if edge.fact:
                        facts.append(edge.fact)
                    edges_result.append({
                        "uuid": edge.uuid,
                        "name": edge.name,
                        "fact": edge.fact,
                        "source_node_uuid": edge.source_node_uuid,
                        "target_node_uuid": edge.target_node_uuid,
                    })
            
            if scope in ["nodes", "both"]:
                # èŽ·å–æ‰€æœ‰èŠ‚ç‚¹å¹¶åŒ¹é…
                all_nodes = self.get_all_nodes(graph_id)
                scored_nodes = []
                for node in all_nodes:
                    score = match_score(node.name) + match_score(node.summary)
                    if score > 0:
                        scored_nodes.append((score, node))
                
                scored_nodes.sort(key=lambda x: x[0], reverse=True)
                
                for score, node in scored_nodes[:limit]:
                    nodes_result.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "labels": node.labels,
                        "summary": node.summary,
                    })
                    if node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(t("console.localSearchComplete", count=len(facts)))
            
        except Exception as e:
            logger.error(t("console.localSearchFailed", error=str(e)))
        
        return SearchResult(
            facts=facts,
            edges=edges_result,
            nodes=nodes_result,
            query=query,
            total_count=len(facts)
        )
    
    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """
        èŽ·å–å›¾è°±çš„æ‰€æœ‰èŠ‚ç‚¹ï¼ˆåˆ†é¡µèŽ·å–ï¼‰

        Args:
            graph_id: å›¾è°±ID

        Returns:
            èŠ‚ç‚¹åˆ—è¡¨
        """
        logger.info(t("console.fetchingAllNodes", graphId=graph_id))

        nodes = fetch_all_nodes(self.client, graph_id)

        result = []
        for node in nodes:
            node_uuid = getattr(node, 'uuid_', None) or getattr(node, 'uuid', None) or ""
            result.append(NodeInfo(
                uuid=str(node_uuid) if node_uuid else "",
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            ))

        logger.info(t("console.fetchedNodes", count=len(result)))
        return result

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        """
        èŽ·å–å›¾è°±çš„æ‰€æœ‰è¾¹ï¼ˆåˆ†é¡µèŽ·å–ï¼ŒåŒ…å«æ—¶é—´ä¿¡æ¯ï¼‰

        Args:
            graph_id: å›¾è°±ID
            include_temporal: æ˜¯å¦åŒ…å«æ—¶é—´ä¿¡æ¯ï¼ˆé»˜è®¤Trueï¼‰

        Returns:
            è¾¹åˆ—è¡¨ï¼ˆåŒ…å«created_at, valid_at, invalid_at, expired_atï¼‰
        """
        logger.info(t("console.fetchingAllEdges", graphId=graph_id))

        edges = fetch_all_edges(self.client, graph_id)

        result = []
        for edge in edges:
            edge_uuid = getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', None) or ""
            edge_info = EdgeInfo(
                uuid=str(edge_uuid) if edge_uuid else "",
                name=edge.name or "",
                fact=edge.fact or "",
                source_node_uuid=edge.source_node_uuid or "",
                target_node_uuid=edge.target_node_uuid or ""
            )

            # æ·»åŠ æ—¶é—´ä¿¡æ¯
            if include_temporal:
                edge_info.created_at = getattr(edge, 'created_at', None)
                edge_info.valid_at = getattr(edge, 'valid_at', None)
                edge_info.invalid_at = getattr(edge, 'invalid_at', None)
                edge_info.expired_at = getattr(edge, 'expired_at', None)

            result.append(edge_info)

        logger.info(t("console.fetchedEdges", count=len(result)))
        return result
    
    def get_node_detail(self, node_uuid: str) -> Optional[NodeInfo]:
        """
        èŽ·å–å•ä¸ªèŠ‚ç‚¹çš„è¯¦ç»†ä¿¡æ¯
        
        Args:
            node_uuid: èŠ‚ç‚¹UUID
            
        Returns:
            èŠ‚ç‚¹ä¿¡æ¯æˆ–None
        """
        logger.info(t("console.fetchingNodeDetail", uuid=node_uuid[:8]))
        
        try:
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=node_uuid),
                operation_name=t("console.fetchNodeDetailOp", uuid=node_uuid[:8])
            )
            
            if not node:
                return None
            
            return NodeInfo(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            )
        except Exception as e:
            logger.error(t("console.fetchNodeDetailFailed", error=str(e)))
            return None
    
    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """
        èŽ·å–èŠ‚ç‚¹ç›¸å…³çš„æ‰€æœ‰è¾¹
        
        é€šè¿‡èŽ·å–å›¾è°±æ‰€æœ‰è¾¹ï¼Œç„¶åŽè¿‡æ»¤å‡ºä¸ŽæŒ‡å®šèŠ‚ç‚¹ç›¸å…³çš„è¾¹
        
        Args:
            graph_id: å›¾è°±ID
            node_uuid: èŠ‚ç‚¹UUID
            
        Returns:
            è¾¹åˆ—è¡¨
        """
        logger.info(t("console.fetchingNodeEdges", uuid=node_uuid[:8]))
        
        try:
            # èŽ·å–å›¾è°±æ‰€æœ‰è¾¹ï¼Œç„¶åŽè¿‡æ»¤
            all_edges = self.get_all_edges(graph_id)
            
            result = []
            for edge in all_edges:
                # æ£€æŸ¥è¾¹æ˜¯å¦ä¸ŽæŒ‡å®šèŠ‚ç‚¹ç›¸å…³ï¼ˆä½œä¸ºæºæˆ–ç›®æ ‡ï¼‰
                if edge.source_node_uuid == node_uuid or edge.target_node_uuid == node_uuid:
                    result.append(edge)
            
            logger.info(t("console.foundNodeEdges", count=len(result)))
            return result
            
        except Exception as e:
            logger.warning(t("console.fetchNodeEdgesFailed", error=str(e)))
            return []
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str
    ) -> List[NodeInfo]:
        """
        æŒ‰ç±»åž‹èŽ·å–å®žä½“
        
        Args:
            graph_id: å›¾è°±ID
            entity_type: å®žä½“ç±»åž‹ï¼ˆå¦‚ Student, PublicFigure ç­‰ï¼‰
            
        Returns:
            ç¬¦åˆç±»åž‹çš„å®žä½“åˆ—è¡¨
        """
        logger.info(t("console.fetchingEntitiesByType", type=entity_type))
        
        all_nodes = self.get_all_nodes(graph_id)
        
        filtered = []
        for node in all_nodes:
            # æ£€æŸ¥labelsæ˜¯å¦åŒ…å«æŒ‡å®šç±»åž‹
            if entity_type in node.labels:
                filtered.append(node)
        
        logger.info(t("console.foundEntitiesByType", count=len(filtered), type=entity_type))
        return filtered
    
    def get_entity_summary(
        self, 
        graph_id: str, 
        entity_name: str
    ) -> Dict[str, Any]:
        """
        èŽ·å–æŒ‡å®šå®žä½“çš„å…³ç³»æ‘˜è¦
        
        æœç´¢ä¸Žè¯¥å®žä½“ç›¸å…³çš„æ‰€æœ‰ä¿¡æ¯ï¼Œå¹¶ç”Ÿæˆæ‘˜è¦
        
        Args:
            graph_id: å›¾è°±ID
            entity_name: å®žä½“åç§°
            
        Returns:
            å®žä½“æ‘˜è¦ä¿¡æ¯
        """
        logger.info(t("console.fetchingEntitySummary", name=entity_name))
        
        # å…ˆæœç´¢è¯¥å®žä½“ç›¸å…³çš„ä¿¡æ¯
        search_result = self.search_graph(
            graph_id=graph_id,
            query=entity_name,
            limit=20
        )
        
        # å°è¯•åœ¨æ‰€æœ‰èŠ‚ç‚¹ä¸­æ‰¾åˆ°è¯¥å®žä½“
        all_nodes = self.get_all_nodes(graph_id)
        entity_node = None
        for node in all_nodes:
            if node.name.lower() == entity_name.lower():
                entity_node = node
                break
        
        related_edges = []
        if entity_node:
            # ä¼ å…¥graph_idå‚æ•°
            related_edges = self.get_node_edges(graph_id, entity_node.uuid)
        
        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges)
        }
    
    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        """
        èŽ·å–å›¾è°±çš„ç»Ÿè®¡ä¿¡æ¯
        
        Args:
            graph_id: å›¾è°±ID
            
        Returns:
            ç»Ÿè®¡ä¿¡æ¯
        """
        logger.info(t("console.fetchingGraphStats", graphId=graph_id))
        
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)
        
        # ç»Ÿè®¡å®žä½“ç±»åž‹åˆ†å¸ƒ
        entity_types = {}
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types[label] = entity_types.get(label, 0) + 1
        
        # ç»Ÿè®¡å…³ç³»ç±»åž‹åˆ†å¸ƒ
        relation_types = {}
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1
        
        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types
        }
    
    def get_simulation_context(
        self, 
        graph_id: str,
        simulation_requirement: str,
        limit: int = 30
    ) -> Dict[str, Any]:
        """
        èŽ·å–æ¨¡æ‹Ÿç›¸å…³çš„ä¸Šä¸‹æ–‡ä¿¡æ¯
        
        ç»¼åˆæœç´¢ä¸Žæ¨¡æ‹Ÿéœ€æ±‚ç›¸å…³çš„æ‰€æœ‰ä¿¡æ¯
        
        Args:
            graph_id: å›¾è°±ID
            simulation_requirement: æ¨¡æ‹Ÿéœ€æ±‚æè¿°
            limit: æ¯ç±»ä¿¡æ¯çš„æ•°é‡é™åˆ¶
            
        Returns:
            æ¨¡æ‹Ÿä¸Šä¸‹æ–‡ä¿¡æ¯
        """
        logger.info(t("console.fetchingSimContext", requirement=simulation_requirement[:50]))
        
        # æœç´¢ä¸Žæ¨¡æ‹Ÿéœ€æ±‚ç›¸å…³çš„ä¿¡æ¯
        search_result = self.search_graph(
            graph_id=graph_id,
            query=simulation_requirement,
            limit=limit
        )
        
        # èŽ·å–å›¾è°±ç»Ÿè®¡
        stats = self.get_graph_statistics(graph_id)
        
        # èŽ·å–æ‰€æœ‰å®žä½“èŠ‚ç‚¹
        all_nodes = self.get_all_nodes(graph_id)
        
        # ç­›é€‰æœ‰å®žé™…ç±»åž‹çš„å®žä½“ï¼ˆéžçº¯EntityèŠ‚ç‚¹ï¼‰
        entities = []
        for node in all_nodes:
            custom_labels = [l for l in node.labels if l not in ["Entity", "Node"]]
            if custom_labels:
                entities.append({
                    "name": node.name,
                    "type": custom_labels[0],
                    "summary": node.summary
                })
        
        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": stats,
            "entities": entities[:limit],  # é™åˆ¶æ•°é‡
            "total_entities": len(entities)
        }
    
    # ========== æ ¸å¿ƒæ£€ç´¢å·¥å…·ï¼ˆä¼˜åŒ–åŽï¼‰ ==========
    
    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5
    ) -> InsightForgeResult:
        """
        ã€InsightForge - æ·±åº¦æ´žå¯Ÿæ£€ç´¢ã€‘
        
        æœ€å¼ºå¤§çš„æ··åˆæ£€ç´¢å‡½æ•°ï¼Œè‡ªåŠ¨åˆ†è§£é—®é¢˜å¹¶å¤šç»´åº¦æ£€ç´¢ï¼š
        1. ä½¿ç”¨LLMå°†é—®é¢˜åˆ†è§£ä¸ºå¤šä¸ªå­é—®é¢˜
        2. å¯¹æ¯ä¸ªå­é—®é¢˜è¿›è¡Œè¯­ä¹‰æœç´¢
        3. æå–ç›¸å…³å®žä½“å¹¶èŽ·å–å…¶è¯¦ç»†ä¿¡æ¯
        4. è¿½è¸ªå…³ç³»é“¾
        5. æ•´åˆæ‰€æœ‰ç»“æžœï¼Œç”Ÿæˆæ·±åº¦æ´žå¯Ÿ
        
        Args:
            graph_id: å›¾è°±ID
            query: ç”¨æˆ·é—®é¢˜
            simulation_requirement: æ¨¡æ‹Ÿéœ€æ±‚æè¿°
            report_context: æŠ¥å‘Šä¸Šä¸‹æ–‡ï¼ˆå¯é€‰ï¼Œç”¨äºŽæ›´ç²¾å‡†çš„å­é—®é¢˜ç”Ÿæˆï¼‰
            max_sub_queries: æœ€å¤§å­é—®é¢˜æ•°é‡
            
        Returns:
            InsightForgeResult: æ·±åº¦æ´žå¯Ÿæ£€ç´¢ç»“æžœ
        """
        logger.info(t("console.insightForgeStart", query=query[:50]))
        
        result = InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[]
        )
        
        # Step 1: ä½¿ç”¨LLMç”Ÿæˆå­é—®é¢˜
        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries
        )
        result.sub_queries = sub_queries
        logger.info(t("console.generatedSubQueries", count=len(sub_queries)))
        
        # Step 2: å¯¹æ¯ä¸ªå­é—®é¢˜è¿›è¡Œè¯­ä¹‰æœç´¢
        all_facts = []
        all_edges = []
        seen_facts = set()
        
        for sub_query in sub_queries:
            search_result = self.search_graph(
                graph_id=graph_id,
                query=sub_query,
                limit=15,
                scope="edges"
            )
            
            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)
            
            all_edges.extend(search_result.edges)
        
        # å¯¹åŽŸå§‹é—®é¢˜ä¹Ÿè¿›è¡Œæœç´¢
        main_search = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=20,
            scope="edges"
        )
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)
        
        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)
        
        # Step 3: ä»Žè¾¹ä¸­æå–ç›¸å…³å®žä½“UUIDï¼ŒåªèŽ·å–è¿™äº›å®žä½“çš„ä¿¡æ¯ï¼ˆä¸èŽ·å–å…¨éƒ¨èŠ‚ç‚¹ï¼‰
        entity_uuids = set()
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                if source_uuid:
                    entity_uuids.add(source_uuid)
                if target_uuid:
                    entity_uuids.add(target_uuid)
        
        # èŽ·å–æ‰€æœ‰ç›¸å…³å®žä½“çš„è¯¦æƒ…ï¼ˆä¸é™åˆ¶æ•°é‡ï¼Œå®Œæ•´è¾“å‡ºï¼‰
        entity_insights = []
        node_map = {}  # ç”¨äºŽåŽç»­å…³ç³»é“¾æž„å»º
        
        for uuid in list(entity_uuids):  # å¤„ç†æ‰€æœ‰å®žä½“ï¼Œä¸æˆªæ–­
            if not uuid:
                continue
            try:
                # å•ç‹¬èŽ·å–æ¯ä¸ªç›¸å…³èŠ‚ç‚¹çš„ä¿¡æ¯
                node = self.get_node_detail(uuid)
                if node:
                    node_map[uuid] = node
                    entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "å®žä½“")
                    
                    # èŽ·å–è¯¥å®žä½“ç›¸å…³çš„æ‰€æœ‰äº‹å®žï¼ˆä¸æˆªæ–­ï¼‰
                    related_facts = [
                        f for f in all_facts 
                        if node.name.lower() in f.lower()
                    ]
                    
                    entity_insights.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "type": entity_type,
                        "summary": node.summary,
                        "related_facts": related_facts  # å®Œæ•´è¾“å‡ºï¼Œä¸æˆªæ–­
                    })
            except Exception as e:
                logger.debug(f"èŽ·å–èŠ‚ç‚¹ {uuid} å¤±è´¥: {e}")
                continue
        
        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)
        
        # Step 4: æž„å»ºæ‰€æœ‰å…³ç³»é“¾ï¼ˆä¸é™åˆ¶æ•°é‡ï¼‰
        relationship_chains = []
        for edge_data in all_edges:  # å¤„ç†æ‰€æœ‰è¾¹ï¼Œä¸æˆªæ–­
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                relation_name = edge_data.get('name', '')
                
                source_name = node_map.get(source_uuid, NodeInfo('', '', [], '', {})).name or source_uuid[:8]
                target_name = node_map.get(target_uuid, NodeInfo('', '', [], '', {})).name or target_uuid[:8]
                
                chain = f"{source_name} --[{relation_name}]--> {target_name}"
                if chain not in relationship_chains:
                    relationship_chains.append(chain)
        
        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)
        
        logger.info(t("console.insightForgeComplete", facts=result.total_facts, entities=result.total_entities, relationships=result.total_relationships))
        return result
    
    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 5
    ) -> List[str]:
        """
        ä½¿ç”¨LLMç”Ÿæˆå­é—®é¢˜
        
        å°†å¤æ‚é—®é¢˜åˆ†è§£ä¸ºå¤šä¸ªå¯ä»¥ç‹¬ç«‹æ£€ç´¢çš„å­é—®é¢˜
        """
        system_prompt = """ä½ æ˜¯ä¸€ä¸ªä¸“ä¸šçš„é—®é¢˜åˆ†æžä¸“å®¶ã€‚ä½ çš„ä»»åŠ¡æ˜¯å°†ä¸€ä¸ªå¤æ‚é—®é¢˜åˆ†è§£ä¸ºå¤šä¸ªå¯ä»¥åœ¨æ¨¡æ‹Ÿä¸–ç•Œä¸­ç‹¬ç«‹è§‚å¯Ÿçš„å­é—®é¢˜ã€‚

è¦æ±‚ï¼š
1. æ¯ä¸ªå­é—®é¢˜åº”è¯¥è¶³å¤Ÿå…·ä½“ï¼Œå¯ä»¥åœ¨æ¨¡æ‹Ÿä¸–ç•Œä¸­æ‰¾åˆ°ç›¸å…³çš„Agentè¡Œä¸ºæˆ–äº‹ä»¶
2. å­é—®é¢˜åº”è¯¥è¦†ç›–åŽŸé—®é¢˜çš„ä¸åŒç»´åº¦ï¼ˆå¦‚ï¼šè°ã€ä»€ä¹ˆã€ä¸ºä»€ä¹ˆã€æ€Žä¹ˆæ ·ã€ä½•æ—¶ã€ä½•åœ°ï¼‰
3. å­é—®é¢˜åº”è¯¥ä¸Žæ¨¡æ‹Ÿåœºæ™¯ç›¸å…³
4. è¿”å›žJSONæ ¼å¼ï¼š{"sub_queries": ["å­é—®é¢˜1", "å­é—®é¢˜2", ...]}"""

        user_prompt = f"""æ¨¡æ‹Ÿéœ€æ±‚èƒŒæ™¯ï¼š
{simulation_requirement}

{f"æŠ¥å‘Šä¸Šä¸‹æ–‡ï¼š{report_context[:500]}" if report_context else ""}

è¯·å°†ä»¥ä¸‹é—®é¢˜åˆ†è§£ä¸º{max_queries}ä¸ªå­é—®é¢˜ï¼š
{query}

è¿”å›žJSONæ ¼å¼çš„å­é—®é¢˜åˆ—è¡¨ã€‚"""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            sub_queries = response.get("sub_queries", [])
            # ç¡®ä¿æ˜¯å­—ç¬¦ä¸²åˆ—è¡¨
            return [str(sq) for sq in sub_queries[:max_queries]]
            
        except Exception as e:
            logger.warning(t("console.generateSubQueriesFailed", error=str(e)))
            # é™çº§ï¼šè¿”å›žåŸºäºŽåŽŸé—®é¢˜çš„å˜ä½“
            return [
                query,
                f"{query} çš„ä¸»è¦å‚ä¸Žè€…",
                f"{query} çš„åŽŸå› å’Œå½±å“",
                f"{query} çš„å‘å±•è¿‡ç¨‹"
            ][:max_queries]
    
    def panorama_search(
        self,
        graph_id: str,
        query: str,
        include_expired: bool = True,
        limit: int = 50
    ) -> PanoramaResult:
        """
        ã€PanoramaSearch - å¹¿åº¦æœç´¢ã€‘
        
        èŽ·å–å…¨è²Œè§†å›¾ï¼ŒåŒ…æ‹¬æ‰€æœ‰ç›¸å…³å†…å®¹å’ŒåŽ†å²/è¿‡æœŸä¿¡æ¯ï¼š
        1. èŽ·å–æ‰€æœ‰ç›¸å…³èŠ‚ç‚¹
        2. èŽ·å–æ‰€æœ‰è¾¹ï¼ˆåŒ…æ‹¬å·²è¿‡æœŸ/å¤±æ•ˆçš„ï¼‰
        3. åˆ†ç±»æ•´ç†å½“å‰æœ‰æ•ˆå’ŒåŽ†å²ä¿¡æ¯
        
        è¿™ä¸ªå·¥å…·é€‚ç”¨äºŽéœ€è¦äº†è§£äº‹ä»¶å…¨è²Œã€è¿½è¸ªæ¼”å˜è¿‡ç¨‹çš„åœºæ™¯ã€‚
        
        Args:
            graph_id: å›¾è°±ID
            query: æœç´¢æŸ¥è¯¢ï¼ˆç”¨äºŽç›¸å…³æ€§æŽ’åºï¼‰
            include_expired: æ˜¯å¦åŒ…å«è¿‡æœŸå†…å®¹ï¼ˆé»˜è®¤Trueï¼‰
            limit: è¿”å›žç»“æžœæ•°é‡é™åˆ¶
            
        Returns:
            PanoramaResult: å¹¿åº¦æœç´¢ç»“æžœ
        """
        logger.info(t("console.panoramaSearchStart", query=query[:50]))
        
        result = PanoramaResult(query=query)
        
        # èŽ·å–æ‰€æœ‰èŠ‚ç‚¹
        all_nodes = self.get_all_nodes(graph_id)
        node_map = {n.uuid: n for n in all_nodes}
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)
        
        # èŽ·å–æ‰€æœ‰è¾¹ï¼ˆåŒ…å«æ—¶é—´ä¿¡æ¯ï¼‰
        all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.all_edges = all_edges
        result.total_edges = len(all_edges)
        
        # åˆ†ç±»äº‹å®ž
        active_facts = []
        historical_facts = []
        
        for edge in all_edges:
            if not edge.fact:
                continue
            
            # ä¸ºäº‹å®žæ·»åŠ å®žä½“åç§°
            source_name = node_map.get(edge.source_node_uuid, NodeInfo('', '', [], '', {})).name or edge.source_node_uuid[:8]
            target_name = node_map.get(edge.target_node_uuid, NodeInfo('', '', [], '', {})).name or edge.target_node_uuid[:8]
            
            # åˆ¤æ–­æ˜¯å¦è¿‡æœŸ/å¤±æ•ˆ
            is_historical = edge.is_expired or edge.is_invalid
            
            if is_historical:
                # åŽ†å²/è¿‡æœŸäº‹å®žï¼Œæ·»åŠ æ—¶é—´æ ‡è®°
                valid_at = edge.valid_at or "æœªçŸ¥"
                invalid_at = edge.invalid_at or edge.expired_at or "æœªçŸ¥"
                fact_with_time = f"[{valid_at} - {invalid_at}] {edge.fact}"
                historical_facts.append(fact_with_time)
            else:
                # å½“å‰æœ‰æ•ˆäº‹å®ž
                active_facts.append(edge.fact)
        
        # åŸºäºŽæŸ¥è¯¢è¿›è¡Œç›¸å…³æ€§æŽ’åº
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('ï¼Œ', ' ').split() if len(w.strip()) > 1]
        
        def relevance_score(fact: str) -> int:
            fact_lower = fact.lower()
            score = 0
            if query_lower in fact_lower:
                score += 100
            for kw in keywords:
                if kw in fact_lower:
                    score += 10
            return score
        
        # æŽ’åºå¹¶é™åˆ¶æ•°é‡
        active_facts.sort(key=relevance_score, reverse=True)
        historical_facts.sort(key=relevance_score, reverse=True)
        
        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)
        
        logger.info(t("console.panoramaSearchComplete", active=result.active_count, historical=result.historical_count))
        return result
    
    def quick_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10
    ) -> SearchResult:
        """
        ã€QuickSearch - ç®€å•æœç´¢ã€‘
        
        å¿«é€Ÿã€è½»é‡çº§çš„æ£€ç´¢å·¥å…·ï¼š
        1. ç›´æŽ¥è°ƒç”¨Zepè¯­ä¹‰æœç´¢
        2. è¿”å›žæœ€ç›¸å…³çš„ç»“æžœ
        3. é€‚ç”¨äºŽç®€å•ã€ç›´æŽ¥çš„æ£€ç´¢éœ€æ±‚
        
        Args:
            graph_id: å›¾è°±ID
            query: æœç´¢æŸ¥è¯¢
            limit: è¿”å›žç»“æžœæ•°é‡
            
        Returns:
            SearchResult: æœç´¢ç»“æžœ
        """
        logger.info(t("console.quickSearchStart", query=query[:50]))
        
        # ç›´æŽ¥è°ƒç”¨çŽ°æœ‰çš„search_graphæ–¹æ³•
        result = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit,
            scope="edges"
        )
        
        logger.info(t("console.quickSearchComplete", count=result.total_count))
        return result
    
    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: List[str] = None
    ) -> InterviewResult:
        """
        ã€InterviewAgents - æ·±åº¦é‡‡è®¿ã€‘
        
        è°ƒç”¨çœŸå®žçš„OASISé‡‡è®¿APIï¼Œé‡‡è®¿æ¨¡æ‹Ÿä¸­æ­£åœ¨è¿è¡Œçš„Agentï¼š
        1. è‡ªåŠ¨è¯»å–äººè®¾æ–‡ä»¶ï¼Œäº†è§£æ‰€æœ‰æ¨¡æ‹ŸAgent
        2. ä½¿ç”¨LLMåˆ†æžé‡‡è®¿éœ€æ±‚ï¼Œæ™ºèƒ½é€‰æ‹©æœ€ç›¸å…³çš„Agent
        3. ä½¿ç”¨LLMç”Ÿæˆé‡‡è®¿é—®é¢˜
        4. è°ƒç”¨ /api/simulation/interview/batch æŽ¥å£è¿›è¡ŒçœŸå®žé‡‡è®¿ï¼ˆåŒå¹³å°åŒæ—¶é‡‡è®¿ï¼‰
        5. æ•´åˆæ‰€æœ‰é‡‡è®¿ç»“æžœï¼Œç”Ÿæˆé‡‡è®¿æŠ¥å‘Š
        
        ã€é‡è¦ã€‘æ­¤åŠŸèƒ½éœ€è¦æ¨¡æ‹ŸçŽ¯å¢ƒå¤„äºŽè¿è¡ŒçŠ¶æ€ï¼ˆOASISçŽ¯å¢ƒæœªå…³é—­ï¼‰
        
        ã€ä½¿ç”¨åœºæ™¯ã€‘
        - éœ€è¦ä»Žä¸åŒè§’è‰²è§†è§’äº†è§£äº‹ä»¶çœ‹æ³•
        - éœ€è¦æ”¶é›†å¤šæ–¹æ„è§å’Œè§‚ç‚¹
        - éœ€è¦èŽ·å–æ¨¡æ‹ŸAgentçš„çœŸå®žå›žç­”ï¼ˆéžLLMæ¨¡æ‹Ÿï¼‰
        
        Args:
            simulation_id: æ¨¡æ‹ŸIDï¼ˆç”¨äºŽå®šä½äººè®¾æ–‡ä»¶å’Œè°ƒç”¨é‡‡è®¿APIï¼‰
            interview_requirement: é‡‡è®¿éœ€æ±‚æè¿°ï¼ˆéžç»“æž„åŒ–ï¼Œå¦‚"äº†è§£å­¦ç”Ÿå¯¹äº‹ä»¶çš„çœ‹æ³•"ï¼‰
            simulation_requirement: æ¨¡æ‹Ÿéœ€æ±‚èƒŒæ™¯ï¼ˆå¯é€‰ï¼‰
            max_agents: æœ€å¤šé‡‡è®¿çš„Agentæ•°é‡
            custom_questions: è‡ªå®šä¹‰é‡‡è®¿é—®é¢˜ï¼ˆå¯é€‰ï¼Œè‹¥ä¸æä¾›åˆ™è‡ªåŠ¨ç”Ÿæˆï¼‰
            
        Returns:
            InterviewResult: é‡‡è®¿ç»“æžœ
        """
        from .simulation_runner import SimulationRunner
        
        logger.info(t("console.interviewAgentsStart", requirement=interview_requirement[:50]))
        
        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or []
        )
        
        # Step 1: è¯»å–äººè®¾æ–‡ä»¶
        profiles = self._load_agent_profiles(simulation_id)
        
        if not profiles:
            logger.warning(t("console.profilesNotFound", simId=simulation_id))
            result.summary = "æœªæ‰¾åˆ°å¯é‡‡è®¿çš„Agentäººè®¾æ–‡ä»¶"
            return result
        
        result.total_agents = len(profiles)
        logger.info(t("console.loadedProfiles", count=len(profiles)))
        
        # Step 2: ä½¿ç”¨LLMé€‰æ‹©è¦é‡‡è®¿çš„Agentï¼ˆè¿”å›žagent_idåˆ—è¡¨ï¼‰
        selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents
        )
        
        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(t("console.selectedAgentsForInterview", count=len(selected_agents), indices=selected_indices))
        
        # Step 3: ç”Ÿæˆé‡‡è®¿é—®é¢˜ï¼ˆå¦‚æžœæ²¡æœ‰æä¾›ï¼‰
        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents
            )
            logger.info(t("console.generatedInterviewQuestions", count=len(result.interview_questions)))
        
        # å°†é—®é¢˜åˆå¹¶ä¸ºä¸€ä¸ªé‡‡è®¿prompt
        combined_prompt = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)])
        
        # æ·»åŠ ä¼˜åŒ–å‰ç¼€ï¼Œçº¦æŸAgentå›žå¤æ ¼å¼
        INTERVIEW_PROMPT_PREFIX = (
            "ä½ æ­£åœ¨æŽ¥å—ä¸€æ¬¡é‡‡è®¿ã€‚è¯·ç»“åˆä½ çš„äººè®¾ã€æ‰€æœ‰çš„è¿‡å¾€è®°å¿†ä¸Žè¡ŒåŠ¨ï¼Œ"
            "ä»¥çº¯æ–‡æœ¬æ–¹å¼ç›´æŽ¥å›žç­”ä»¥ä¸‹é—®é¢˜ã€‚\n"
            "å›žå¤è¦æ±‚ï¼š\n"
            "1. ç›´æŽ¥ç”¨è‡ªç„¶è¯­è¨€å›žç­”ï¼Œä¸è¦è°ƒç”¨ä»»ä½•å·¥å…·\n"
            "2. ä¸è¦è¿”å›žJSONæ ¼å¼æˆ–å·¥å…·è°ƒç”¨æ ¼å¼\n"
            "3. ä¸è¦ä½¿ç”¨Markdownæ ‡é¢˜ï¼ˆå¦‚#ã€##ã€###ï¼‰\n"
            "4. æŒ‰é—®é¢˜ç¼–å·é€ä¸€å›žç­”ï¼Œæ¯ä¸ªå›žç­”ä»¥ã€Œé—®é¢˜Xï¼šã€å¼€å¤´ï¼ˆXä¸ºé—®é¢˜ç¼–å·ï¼‰\n"
            "5. æ¯ä¸ªé—®é¢˜çš„å›žç­”ä¹‹é—´ç”¨ç©ºè¡Œåˆ†éš”\n"
            "6. å›žç­”è¦æœ‰å®žè´¨å†…å®¹ï¼Œæ¯ä¸ªé—®é¢˜è‡³å°‘å›žç­”2-3å¥è¯\n\n"
        )
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"
        
        # Step 4: è°ƒç”¨çœŸå®žçš„é‡‡è®¿APIï¼ˆä¸æŒ‡å®šplatformï¼Œé»˜è®¤åŒå¹³å°åŒæ—¶é‡‡è®¿ï¼‰
        try:
            # æž„å»ºæ‰¹é‡é‡‡è®¿åˆ—è¡¨ï¼ˆä¸æŒ‡å®šplatformï¼ŒåŒå¹³å°é‡‡è®¿ï¼‰
            interviews_request = []
            for agent_idx in selected_indices:
                interviews_request.append({
                    "agent_id": agent_idx,
                    "prompt": optimized_prompt  # ä½¿ç”¨ä¼˜åŒ–åŽçš„prompt
                    # ä¸æŒ‡å®šplatformï¼ŒAPIä¼šåœ¨twitterå’Œredditä¸¤ä¸ªå¹³å°éƒ½é‡‡è®¿
                })
            
            logger.info(t("console.callingBatchInterviewApi", count=len(interviews_request)))
            
            # è°ƒç”¨ SimulationRunner çš„æ‰¹é‡é‡‡è®¿æ–¹æ³•ï¼ˆä¸ä¼ platformï¼ŒåŒå¹³å°é‡‡è®¿ï¼‰
            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None,  # ä¸æŒ‡å®šplatformï¼ŒåŒå¹³å°é‡‡è®¿
                timeout=180.0   # åŒå¹³å°éœ€è¦æ›´é•¿è¶…æ—¶
            )
            
            logger.info(t("console.interviewApiReturned", count=api_result.get('interviews_count', 0), success=api_result.get('success')))
            
            # æ£€æŸ¥APIè°ƒç”¨æ˜¯å¦æˆåŠŸ
            if not api_result.get("success", False):
                error_msg = api_result.get("error", "æœªçŸ¥é”™è¯¯")
                logger.warning(t("console.interviewApiReturnedFailure", error=error_msg))
                result.summary = f"é‡‡è®¿APIè°ƒç”¨å¤±è´¥ï¼š{error_msg}ã€‚è¯·æ£€æŸ¥OASISæ¨¡æ‹ŸçŽ¯å¢ƒçŠ¶æ€ã€‚"
                return result
            
            # Step 5: è§£æžAPIè¿”å›žç»“æžœï¼Œæž„å»ºAgentInterviewå¯¹è±¡
            # åŒå¹³å°æ¨¡å¼è¿”å›žæ ¼å¼: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}
            
            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", "æœªçŸ¥")
                agent_bio = agent.get("bio", "")
                
                # èŽ·å–è¯¥Agentåœ¨ä¸¤ä¸ªå¹³å°çš„é‡‡è®¿ç»“æžœ
                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})
                
                twitter_response = twitter_result.get("response", "")
                reddit_response = reddit_result.get("response", "")

                # æ¸…ç†å¯èƒ½çš„å·¥å…·è°ƒç”¨ JSON åŒ…è£¹
                twitter_response = self._clean_tool_call_response(twitter_response)
                reddit_response = self._clean_tool_call_response(reddit_response)

                # å§‹ç»ˆè¾“å‡ºåŒå¹³å°æ ‡è®°
                twitter_text = twitter_response if twitter_response else "ï¼ˆè¯¥å¹³å°æœªèŽ·å¾—å›žå¤ï¼‰"
                reddit_text = reddit_response if reddit_response else "ï¼ˆè¯¥å¹³å°æœªèŽ·å¾—å›žå¤ï¼‰"
                response_text = f"ã€Twitterå¹³å°å›žç­”ã€‘\n{twitter_text}\n\nã€Redditå¹³å°å›žç­”ã€‘\n{reddit_text}"

                # æå–å…³é”®å¼•è¨€ï¼ˆä»Žä¸¤ä¸ªå¹³å°çš„å›žç­”ä¸­ï¼‰
                import re
                combined_responses = f"{twitter_response} {reddit_response}"

                # æ¸…ç†å“åº”æ–‡æœ¬ï¼šåŽ»æŽ‰æ ‡è®°ã€ç¼–å·ã€Markdown ç­‰å¹²æ‰°
                clean_text = re.sub(r'#{1,6}\s+', '', combined_responses)
                clean_text = re.sub(r'\{[^}]*tool_name[^}]*\}', '', clean_text)
                clean_text = re.sub(r'[*_`|>~\-]{2,}', '', clean_text)
                clean_text = re.sub(r'é—®é¢˜\d+[ï¼š:]\s*', '', clean_text)
                clean_text = re.sub(r'ã€[^ã€‘]+ã€‘', '', clean_text)

                # ç­–ç•¥1ï¼ˆä¸»ï¼‰: æå–å®Œæ•´çš„æœ‰å®žè´¨å†…å®¹çš„å¥å­
                sentences = re.split(r'[ã€‚ï¼ï¼Ÿ]', clean_text)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r'^[\s\Wï¼Œ,ï¼›;ï¼š:ã€]+', s.strip())
                    and not s.strip().startswith(('{', 'é—®é¢˜'))
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "ã€‚" for s in meaningful[:3]]

                # ç­–ç•¥2ï¼ˆè¡¥å……ï¼‰: æ­£ç¡®é…å¯¹çš„ä¸­æ–‡å¼•å·ã€Œã€å†…é•¿æ–‡æœ¬
                if not key_quotes:
                    paired = re.findall(r'\u201c([^\u201c\u201d]{15,100})\u201d', clean_text)
                    paired += re.findall(r'\u300c([^\u300c\u300d]{15,100})\u300d', clean_text)
                    key_quotes = [q for q in paired if not re.match(r'^[ï¼Œ,ï¼›;ï¼š:ã€]', q)][:3]
                
                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],  # æ‰©å¤§bioé•¿åº¦é™åˆ¶
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5]
                )
                result.interviews.append(interview)
            
            result.interviewed_count = len(result.interviews)
            
        except ValueError as e:
            # æ¨¡æ‹ŸçŽ¯å¢ƒæœªè¿è¡Œ
            logger.warning(t("console.interviewApiCallFailed", error=e))
            result.summary = f"é‡‡è®¿å¤±è´¥ï¼š{str(e)}ã€‚æ¨¡æ‹ŸçŽ¯å¢ƒå¯èƒ½å·²å…³é—­ï¼Œè¯·ç¡®ä¿OASISçŽ¯å¢ƒæ­£åœ¨è¿è¡Œã€‚"
            return result
        except Exception as e:
            logger.error(t("console.interviewApiCallException", error=e))
            import traceback
            logger.error(traceback.format_exc())
            result.summary = f"é‡‡è®¿è¿‡ç¨‹å‘ç”Ÿé”™è¯¯ï¼š{str(e)}"
            return result
        
        # Step 6: ç”Ÿæˆé‡‡è®¿æ‘˜è¦
        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )
        
        logger.info(t("console.interviewAgentsComplete", count=result.interviewed_count))
        return result
    
    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """æ¸…ç† Agent å›žå¤ä¸­çš„ JSON å·¥å…·è°ƒç”¨åŒ…è£¹ï¼Œæå–å®žé™…å†…å®¹"""
        if not response or not response.strip().startswith('{'):
            return response
        text = response.strip()
        if 'tool_name' not in text[:80]:
            return response
        import re as _re
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'arguments' in data:
                for key in ('content', 'text', 'body', 'message', 'reply'):
                    if key in data['arguments']:
                        return str(data['arguments'][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = _re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """åŠ è½½æ¨¡æ‹Ÿçš„Agentäººè®¾æ–‡ä»¶"""
        import os
        import csv
        
        # æž„å»ºäººè®¾æ–‡ä»¶è·¯å¾„
        sim_dir = os.path.join(
            os.path.dirname(__file__), 
            f'../../uploads/simulations/{simulation_id}'
        )
        
        profiles = []
        
        # ä¼˜å…ˆå°è¯•è¯»å–Reddit JSONæ ¼å¼
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                logger.info(t("console.loadedRedditProfiles", count=len(profiles)))
                return profiles
            except Exception as e:
                logger.warning(t("console.readRedditProfilesFailed", error=e))
        
        # å°è¯•è¯»å–Twitter CSVæ ¼å¼
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # CSVæ ¼å¼è½¬æ¢ä¸ºç»Ÿä¸€æ ¼å¼
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "æœªçŸ¥"
                        })
                logger.info(t("console.loadedTwitterProfiles", count=len(profiles)))
                return profiles
            except Exception as e:
                logger.warning(t("console.readTwitterProfilesFailed", error=e))
        
        return profiles
    
    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int
    ) -> tuple:
        """
        ä½¿ç”¨LLMé€‰æ‹©è¦é‡‡è®¿çš„Agent
        
        Returns:
            tuple: (selected_agents, selected_indices, reasoning)
                - selected_agents: é€‰ä¸­Agentçš„å®Œæ•´ä¿¡æ¯åˆ—è¡¨
                - selected_indices: é€‰ä¸­Agentçš„ç´¢å¼•åˆ—è¡¨ï¼ˆç”¨äºŽAPIè°ƒç”¨ï¼‰
                - reasoning: é€‰æ‹©ç†ç”±
        """
        
        # æž„å»ºAgentæ‘˜è¦åˆ—è¡¨
        agent_summaries = []
        for i, profile in enumerate(profiles):
            summary = {
                "index": i,
                "name": profile.get("realname", profile.get("username", f"Agent_{i}")),
                "profession": profile.get("profession", "æœªçŸ¥"),
                "bio": profile.get("bio", "")[:200],
                "interested_topics": profile.get("interested_topics", [])
            }
            agent_summaries.append(summary)
        
        system_prompt = """ä½ æ˜¯ä¸€ä¸ªä¸“ä¸šçš„é‡‡è®¿ç­–åˆ’ä¸“å®¶ã€‚ä½ çš„ä»»åŠ¡æ˜¯æ ¹æ®é‡‡è®¿éœ€æ±‚ï¼Œä»Žæ¨¡æ‹ŸAgentåˆ—è¡¨ä¸­é€‰æ‹©æœ€é€‚åˆé‡‡è®¿çš„å¯¹è±¡ã€‚

é€‰æ‹©æ ‡å‡†ï¼š
1. Agentçš„èº«ä»½/èŒä¸šä¸Žé‡‡è®¿ä¸»é¢˜ç›¸å…³
2. Agentå¯èƒ½æŒæœ‰ç‹¬ç‰¹æˆ–æœ‰ä»·å€¼çš„è§‚ç‚¹
3. é€‰æ‹©å¤šæ ·åŒ–çš„è§†è§’ï¼ˆå¦‚ï¼šæ”¯æŒæ–¹ã€åå¯¹æ–¹ã€ä¸­ç«‹æ–¹ã€ä¸“ä¸šäººå£«ç­‰ï¼‰
4. ä¼˜å…ˆé€‰æ‹©ä¸Žäº‹ä»¶ç›´æŽ¥ç›¸å…³çš„è§’è‰²

è¿”å›žJSONæ ¼å¼ï¼š
{
    "selected_indices": [é€‰ä¸­Agentçš„ç´¢å¼•åˆ—è¡¨],
    "reasoning": "é€‰æ‹©ç†ç”±è¯´æ˜Ž"
}"""

        user_prompt = f"""é‡‡è®¿éœ€æ±‚ï¼š
{interview_requirement}

æ¨¡æ‹ŸèƒŒæ™¯ï¼š
{simulation_requirement if simulation_requirement else "æœªæä¾›"}

å¯é€‰æ‹©çš„Agentåˆ—è¡¨ï¼ˆå…±{len(agent_summaries)}ä¸ªï¼‰ï¼š
{json.dumps(agent_summaries, ensure_ascii=False, indent=2)}

è¯·é€‰æ‹©æœ€å¤š{max_agents}ä¸ªæœ€é€‚åˆé‡‡è®¿çš„Agentï¼Œå¹¶è¯´æ˜Žé€‰æ‹©ç†ç”±ã€‚"""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            selected_indices = response.get("selected_indices", [])[:max_agents]
            reasoning = response.get("reasoning", "åŸºäºŽç›¸å…³æ€§è‡ªåŠ¨é€‰æ‹©")
            
            # èŽ·å–é€‰ä¸­çš„Agentå®Œæ•´ä¿¡æ¯
            selected_agents = []
            valid_indices = []
            for idx in selected_indices:
                if 0 <= idx < len(profiles):
                    selected_agents.append(profiles[idx])
                    valid_indices.append(idx)
            
            return selected_agents, valid_indices, reasoning
            
        except Exception as e:
            logger.warning(t("console.llmSelectAgentFailed", error=e))
            # é™çº§ï¼šé€‰æ‹©å‰Nä¸ª
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, "ä½¿ç”¨é»˜è®¤é€‰æ‹©ç­–ç•¥"
    
    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[str]:
        """ä½¿ç”¨LLMç”Ÿæˆé‡‡è®¿é—®é¢˜"""
        
        agent_roles = [a.get("profession", "æœªçŸ¥") for a in selected_agents]
        
        system_prompt = """ä½ æ˜¯ä¸€ä¸ªä¸“ä¸šçš„è®°è€…/é‡‡è®¿è€…ã€‚æ ¹æ®é‡‡è®¿éœ€æ±‚ï¼Œç”Ÿæˆ3-5ä¸ªæ·±åº¦é‡‡è®¿é—®é¢˜ã€‚

é—®é¢˜è¦æ±‚ï¼š
1. å¼€æ”¾æ€§é—®é¢˜ï¼Œé¼“åŠ±è¯¦ç»†å›žç­”
2. é’ˆå¯¹ä¸åŒè§’è‰²å¯èƒ½æœ‰ä¸åŒç­”æ¡ˆ
3. æ¶µç›–äº‹å®žã€è§‚ç‚¹ã€æ„Ÿå—ç­‰å¤šä¸ªç»´åº¦
4. è¯­è¨€è‡ªç„¶ï¼ŒåƒçœŸå®žé‡‡è®¿ä¸€æ ·
5. æ¯ä¸ªé—®é¢˜æŽ§åˆ¶åœ¨50å­—ä»¥å†…ï¼Œç®€æ´æ˜Žäº†
6. ç›´æŽ¥æé—®ï¼Œä¸è¦åŒ…å«èƒŒæ™¯è¯´æ˜Žæˆ–å‰ç¼€

è¿”å›žJSONæ ¼å¼ï¼š{"questions": ["é—®é¢˜1", "é—®é¢˜2", ...]}"""

        user_prompt = f"""é‡‡è®¿éœ€æ±‚ï¼š{interview_requirement}

æ¨¡æ‹ŸèƒŒæ™¯ï¼š{simulation_requirement if simulation_requirement else "æœªæä¾›"}

é‡‡è®¿å¯¹è±¡è§’è‰²ï¼š{', '.join(agent_roles)}

è¯·ç”Ÿæˆ3-5ä¸ªé‡‡è®¿é—®é¢˜ã€‚"""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5
            )
            
            return response.get("questions", [f"å…³äºŽ{interview_requirement}ï¼Œæ‚¨æœ‰ä»€ä¹ˆçœ‹æ³•ï¼Ÿ"])
            
        except Exception as e:
            logger.warning(t("console.generateInterviewQuestionsFailed", error=e))
            return [
                f"å…³äºŽ{interview_requirement}ï¼Œæ‚¨çš„è§‚ç‚¹æ˜¯ä»€ä¹ˆï¼Ÿ",
                "è¿™ä»¶äº‹å¯¹æ‚¨æˆ–æ‚¨æ‰€ä»£è¡¨çš„ç¾¤ä½“æœ‰ä»€ä¹ˆå½±å“ï¼Ÿ",
                "æ‚¨è®¤ä¸ºåº”è¯¥å¦‚ä½•è§£å†³æˆ–æ”¹è¿›è¿™ä¸ªé—®é¢˜ï¼Ÿ"
            ]
    
    def _generate_interview_summary(
        self,
        interviews: List[AgentInterview],
        interview_requirement: str
    ) -> str:
        """ç”Ÿæˆé‡‡è®¿æ‘˜è¦"""
        
        if not interviews:
            return "æœªå®Œæˆä»»ä½•é‡‡è®¿"
        
        # æ”¶é›†æ‰€æœ‰é‡‡è®¿å†…å®¹
        interview_texts = []
        for interview in interviews:
            interview_texts.append(f"ã€{interview.agent_name}ï¼ˆ{interview.agent_role}ï¼‰ã€‘\n{interview.response[:500]}")
        
        quote_instruction = "å¼•ç”¨å—è®¿è€…åŽŸè¯æ—¶ä½¿ç”¨ä¸­æ–‡å¼•å·ã€Œã€" if get_locale() == 'zh' else 'Use quotation marks "" when quoting interviewees'
        system_prompt = f"""ä½ æ˜¯ä¸€ä¸ªä¸“ä¸šçš„æ–°é—»ç¼–è¾‘ã€‚è¯·æ ¹æ®å¤šä½å—è®¿è€…çš„å›žç­”ï¼Œç”Ÿæˆä¸€ä»½é‡‡è®¿æ‘˜è¦ã€‚

æ‘˜è¦è¦æ±‚ï¼š
1. æç‚¼å„æ–¹ä¸»è¦è§‚ç‚¹
2. æŒ‡å‡ºè§‚ç‚¹çš„å…±è¯†å’Œåˆ†æ­§
3. çªå‡ºæœ‰ä»·å€¼çš„å¼•è¨€
4. å®¢è§‚ä¸­ç«‹ï¼Œä¸åè¢’ä»»ä½•ä¸€æ–¹
5. æŽ§åˆ¶åœ¨1000å­—å†…

æ ¼å¼çº¦æŸï¼ˆå¿…é¡»éµå®ˆï¼‰ï¼š
- ä½¿ç”¨çº¯æ–‡æœ¬æ®µè½ï¼Œç”¨ç©ºè¡Œåˆ†éš”ä¸åŒéƒ¨åˆ†
- ä¸è¦ä½¿ç”¨Markdownæ ‡é¢˜ï¼ˆå¦‚#ã€##ã€###ï¼‰
- ä¸è¦ä½¿ç”¨åˆ†å‰²çº¿ï¼ˆå¦‚---ã€***ï¼‰
- {quote_instruction}
- å¯ä»¥ä½¿ç”¨**åŠ ç²—**æ ‡è®°å…³é”®è¯ï¼Œä½†ä¸è¦ä½¿ç”¨å…¶ä»–Markdownè¯­æ³•"""

        user_prompt = f"""é‡‡è®¿ä¸»é¢˜ï¼š{interview_requirement}

é‡‡è®¿å†…å®¹ï¼š
{"".join(interview_texts)}

è¯·ç”Ÿæˆé‡‡è®¿æ‘˜è¦ã€‚"""

        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return summary
            
        except Exception as e:
            logger.warning(t("console.generateInterviewSummaryFailed", error=e))
            # é™çº§ï¼šç®€å•æ‹¼æŽ¥
            return f"å…±é‡‡è®¿äº†{len(interviews)}ä½å—è®¿è€…ï¼ŒåŒ…æ‹¬ï¼š" + "ã€".join([i.agent_name for i in interviews])

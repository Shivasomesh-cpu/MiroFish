"""

"""

import json
import math
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_language_instruction, t
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('posiedon.simulation_config')

CHINA_TIMEZONE_CONFIG = {
    "dead_hours": [0, 1, 2, 3, 4, 5],
    "morning_hours": [6, 7, 8],
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    "peak_hours": [19, 20, 21, 22],
    "night_hours": [23],
    "activity_multipliers": {
        "dead": 0.05,      # å‡Œæ™¨å‡ ä¹Žæ— äºº
        "morning": 0.4,    # æ—©é—´é€æ¸æ´»è·ƒ
        "work": 0.7,       # å·¥ä½œæ—¶æ®µä¸­ç­‰
        "peak": 1.5,       # æ™šé—´é«˜å³°
        "night": 0.5       # æ·±å¤œä¸‹é™
    }
}


@dataclass
class AgentActivityConfig:
    """å•ä¸ªAgentçš„æ´»åŠ¨é…ç½®"""
    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str
    
    activity_level: float = 0.5  # æ•´ä½“æ´»è·ƒåº¦
    
    posts_per_hour: float = 1.0
    comments_per_hour: float = 2.0
    
    active_hours: List[int] = field(default_factory=lambda: list(range(8, 23)))
    
    response_delay_min: int = 5
    response_delay_max: int = 60
    
    sentiment_bias: float = 0.0
    
    stance: str = "neutral"  # supportive, opposing, neutral, observer
    
    influence_weight: float = 1.0


@dataclass  
class TimeSimulationConfig:
    """æ—¶é—´æ¨¡æ‹Ÿé…ç½®ï¼ˆåŸºäºŽä¸­å›½äººä½œæ¯ä¹ æƒ¯ï¼‰"""
    total_simulation_hours: int = 72  # é»˜è®¤æ¨¡æ‹Ÿ72å°æ—¶ï¼ˆ3å¤©ï¼‰
    
    minutes_per_round: int = 60
    
    agents_per_hour_min: int = 5
    agents_per_hour_max: int = 20
    
    peak_hours: List[int] = field(default_factory=lambda: [19, 20, 21, 22])
    peak_activity_multiplier: float = 1.5
    
    off_peak_hours: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    off_peak_activity_multiplier: float = 0.05  # å‡Œæ™¨æ´»è·ƒåº¦æžä½Ž
    
    morning_hours: List[int] = field(default_factory=lambda: [6, 7, 8])
    morning_activity_multiplier: float = 0.4
    
    work_hours: List[int] = field(default_factory=lambda: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18])
    work_activity_multiplier: float = 0.7


@dataclass
class EventConfig:
    """äº‹ä»¶é…ç½®"""
    initial_posts: List[Dict[str, Any]] = field(default_factory=list)
    
    scheduled_events: List[Dict[str, Any]] = field(default_factory=list)
    
    hot_topics: List[str] = field(default_factory=list)
    
    narrative_direction: str = ""


@dataclass
class PlatformConfig:
    """å¹³å°ç‰¹å®šé…ç½®"""
    platform: str  # twitter or reddit
    
    recency_weight: float = 0.4  # æ—¶é—´æ–°é²œåº¦
    popularity_weight: float = 0.3  # çƒ­åº¦
    relevance_weight: float = 0.3  # ç›¸å…³æ€§
    
    viral_threshold: int = 10
    
    echo_chamber_strength: float = 0.5


@dataclass
class SimulationParameters:
    """å®Œæ•´çš„æ¨¡æ‹Ÿå‚æ•°é…ç½®"""
    simulation_id: str
    project_id: str
    graph_id: str
    simulation_requirement: str
    
    time_config: TimeSimulationConfig = field(default_factory=TimeSimulationConfig)
    
    agent_configs: List[AgentActivityConfig] = field(default_factory=list)
    
    event_config: EventConfig = field(default_factory=EventConfig)
    
    twitter_config: Optional[PlatformConfig] = None
    reddit_config: Optional[PlatformConfig] = None
    
    llm_model: str = ""
    llm_base_url: str = ""
    
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generation_reasoning: str = ""  # LLMçš„æŽ¨ç†è¯´æ˜Ž
    
    def to_dict(self) -> Dict[str, Any]:
        """è½¬æ¢ä¸ºå­—å…¸"""
        time_dict = asdict(self.time_config)
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "time_config": time_dict,
            "agent_configs": [asdict(a) for a in self.agent_configs],
            "event_config": asdict(self.event_config),
            "twitter_config": asdict(self.twitter_config) if self.twitter_config else None,
            "reddit_config": asdict(self.reddit_config) if self.reddit_config else None,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "generated_at": self.generated_at,
            "generation_reasoning": self.generation_reasoning,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """è½¬æ¢ä¸ºJSONå­—ç¬¦ä¸²"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class SimulationConfigGenerator:
    """
    
    
    """
    
    MAX_CONTEXT_LENGTH = 50000
    AGENTS_PER_BATCH = 15
    
    TIME_CONFIG_CONTEXT_LENGTH = 10000   # æ—¶é—´é…ç½®
    EVENT_CONFIG_CONTEXT_LENGTH = 8000   # äº‹ä»¶é…ç½®
    ENTITY_SUMMARY_LENGTH = 300          # å®žä½“æ‘˜è¦
    AGENT_SUMMARY_LENGTH = 300           # Agenté…ç½®ä¸­çš„å®žä½“æ‘˜è¦
    ENTITIES_PER_TYPE_DISPLAY = 20       # æ¯ç±»å®žä½“æ˜¾ç¤ºæ•°é‡
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY æœªé…ç½®")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> SimulationParameters:
        """
        
        Args:
            
        Returns:
        """
        logger.info(f"å¼€å§‹æ™ºèƒ½ç”Ÿæˆæ¨¡æ‹Ÿé…ç½®: simulation_id={simulation_id}, å®žä½“æ•°={len(entities)}")
        
        num_batches = math.ceil(len(entities) / self.AGENTS_PER_BATCH)
        total_steps = 3 + num_batches  # æ—¶é—´é…ç½® + äº‹ä»¶é…ç½® + Næ‰¹Agent + å¹³å°é…ç½®
        current_step = 0
        
        def report_progress(step: int, message: str):
            nonlocal current_step
            current_step = step
            if progress_callback:
                progress_callback(step, total_steps, message)
            logger.info(f"[{step}/{total_steps}] {message}")
        
        context = self._build_context(
            simulation_requirement=simulation_requirement,
            document_text=document_text,
            entities=entities
        )
        
        reasoning_parts = []
        
        report_progress(1, t('progress.generatingTimeConfig'))
        num_entities = len(entities)
        time_config_result = self._generate_time_config(context, num_entities)
        time_config = self._parse_time_config(time_config_result, num_entities)
        reasoning_parts.append(f"{t('progress.timeConfigLabel')}: {time_config_result.get('reasoning', t('common.success'))}")
        
        report_progress(2, t('progress.generatingEventConfig'))
        event_config_result = self._generate_event_config(context, simulation_requirement, entities)
        event_config = self._parse_event_config(event_config_result)
        reasoning_parts.append(f"{t('progress.eventConfigLabel')}: {event_config_result.get('reasoning', t('common.success'))}")
        
        all_agent_configs = []
        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.AGENTS_PER_BATCH
            end_idx = min(start_idx + self.AGENTS_PER_BATCH, len(entities))
            batch_entities = entities[start_idx:end_idx]
            
            report_progress(
                3 + batch_idx,
                t('progress.generatingAgentConfig', start=start_idx + 1, end=end_idx, total=len(entities))
            )
            
            batch_configs = self._generate_agent_configs_batch(
                context=context,
                entities=batch_entities,
                start_idx=start_idx,
                simulation_requirement=simulation_requirement
            )
            all_agent_configs.extend(batch_configs)
        
        reasoning_parts.append(t('progress.agentConfigResult', count=len(all_agent_configs)))
        
        logger.info("ä¸ºåˆå§‹å¸–å­åˆ†é…åˆé€‚çš„å‘å¸ƒè€… Agent...")
        event_config = self._assign_initial_post_agents(event_config, all_agent_configs)
        assigned_count = len([p for p in event_config.initial_posts if p.get("poster_agent_id") is not None])
        reasoning_parts.append(t('progress.postAssignResult', count=assigned_count))
        
        report_progress(total_steps, t('progress.generatingPlatformConfig'))
        twitter_config = None
        reddit_config = None
        
        if enable_twitter:
            twitter_config = PlatformConfig(
                platform="twitter",
                recency_weight=0.4,
                popularity_weight=0.3,
                relevance_weight=0.3,
                viral_threshold=10,
                echo_chamber_strength=0.5
            )
        
        if enable_reddit:
            reddit_config = PlatformConfig(
                platform="reddit",
                recency_weight=0.3,
                popularity_weight=0.4,
                relevance_weight=0.3,
                viral_threshold=15,
                echo_chamber_strength=0.6
            )
        
        params = SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            time_config=time_config,
            agent_configs=all_agent_configs,
            event_config=event_config,
            twitter_config=twitter_config,
            reddit_config=reddit_config,
            llm_model=self.model_name,
            llm_base_url=self.base_url,
            generation_reasoning=" | ".join(reasoning_parts)
        )
        
        logger.info(f"æ¨¡æ‹Ÿé…ç½®ç”Ÿæˆå®Œæˆ: {len(params.agent_configs)} ä¸ªAgenté…ç½®")
        
        return params
    
    def _build_context(
        self,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode]
    ) -> str:
        """æž„å»ºLLMä¸Šä¸‹æ–‡ï¼Œæˆªæ–­åˆ°æœ€å¤§é•¿åº¦"""
        
        entity_summary = self._summarize_entities(entities)
        
        context_parts = [
            f"## æ¨¡æ‹Ÿéœ€æ±‚\n{simulation_requirement}",
            f"\n## å®žä½“ä¿¡æ¯ ({len(entities)}ä¸ª)\n{entity_summary}",
        ]
        
        current_length = sum(len(p) for p in context_parts)
        remaining_length = self.MAX_CONTEXT_LENGTH - current_length - 500  # ç•™500å­—ç¬¦ä½™é‡
        
        if remaining_length > 0 and document_text:
            doc_text = document_text[:remaining_length]
            if len(document_text) > remaining_length:
                doc_text += "\n...(æ–‡æ¡£å·²æˆªæ–­)"
            context_parts.append(f"\n## åŽŸå§‹æ–‡æ¡£å†…å®¹\n{doc_text}")
        
        return "\n".join(context_parts)
    
    def _summarize_entities(self, entities: List[EntityNode]) -> str:
        """ç”Ÿæˆå®žä½“æ‘˜è¦"""
        lines = []
        
        by_type: Dict[str, List[EntityNode]] = {}
        for e in entities:
            t = e.get_entity_type() or "Unknown"
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e)
        
        for entity_type, type_entities in by_type.items():
            lines.append(f"\n### {entity_type} ({len(type_entities)}ä¸ª)")
            display_count = self.ENTITIES_PER_TYPE_DISPLAY
            summary_len = self.ENTITY_SUMMARY_LENGTH
            for e in type_entities[:display_count]:
                summary_preview = (e.summary[:summary_len] + "...") if len(e.summary) > summary_len else e.summary
                lines.append(f"- {e.name}: {summary_preview}")
            if len(type_entities) > display_count:
                lines.append(f"  ... è¿˜æœ‰ {len(type_entities) - display_count} ä¸ª")
        
        return "\n".join(lines)
    
    def _call_llm_with_retry(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """å¸¦é‡è¯•çš„LLMè°ƒç”¨ï¼ŒåŒ…å«JSONä¿®å¤é€»è¾‘"""
        import re
        
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1)  # æ¯æ¬¡é‡è¯•é™ä½Žæ¸©åº¦
                )
                
                content = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason
                
                if finish_reason == 'length':
                    logger.warning(f"LLMè¾“å‡ºè¢«æˆªæ–­ (attempt {attempt+1})")
                    content = self._fix_truncated_json(content)
                
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSONè§£æžå¤±è´¥ (attempt {attempt+1}): {str(e)[:80]}")
                    
                    fixed = self._try_fix_config_json(content)
                    if fixed:
                        return fixed
                    
                    last_error = e
                    
            except Exception as e:
                logger.warning(f"LLMè°ƒç”¨å¤±è´¥ (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(2 * (attempt + 1))
        
        raise last_error or Exception("LLMè°ƒç”¨å¤±è´¥")
    
    def _fix_truncated_json(self, content: str) -> str:
        """ä¿®å¤è¢«æˆªæ–­çš„JSON"""
        content = content.strip()
        
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        if content and content[-1] not in '",}]':
            content += '"'
        
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_config_json(self, content: str) -> Optional[Dict[str, Any]]:
        """å°è¯•ä¿®å¤é…ç½®JSON"""
        import re
        
        content = self._fix_truncated_json(content)
        
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            def fix_string(match):
                s = match.group(0)
                s = s.replace('\n', ' ').replace('\r', ' ')
                s = re.sub(r'\s+', ' ', s)
                return s
            
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string, json_str)
            
            try:
                return json.loads(json_str)
            except:
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                json_str = re.sub(r'\s+', ' ', json_str)
                try:
                    return json.loads(json_str)
                except:
                    pass
        
        return None
    
    def _generate_time_config(self, context: str, num_entities: int) -> Dict[str, Any]:
        """ç”Ÿæˆæ—¶é—´é…ç½®"""
        context_truncated = context[:self.TIME_CONFIG_CONTEXT_LENGTH]
        
        max_agents_allowed = max(1, int(num_entities * 0.9))
        
        prompt = f"""åŸºäºŽä»¥ä¸‹æ¨¡æ‹Ÿéœ€æ±‚ï¼Œç”Ÿæˆæ—¶é—´æ¨¡æ‹Ÿé…ç½®ã€‚

{context_truncated}

è¯·ç”Ÿæˆæ—¶é—´é…ç½®JSONã€‚

- è¯·æ ¹æ®æ¨¡æ‹Ÿåœºæ™¯æŽ¨æ–­ç›®æ ‡ç”¨æˆ·ç¾¤ä½“æ‰€åœ¨æ—¶åŒºå’Œä½œæ¯ä¹ æƒ¯ï¼Œä»¥ä¸‹ä¸ºä¸œå…«åŒº(UTC+8)çš„å‚è€ƒç¤ºä¾‹
- å‡Œæ™¨0-5ç‚¹å‡ ä¹Žæ— äººæ´»åŠ¨ï¼ˆæ´»è·ƒåº¦ç³»æ•°0.05ï¼‰
- æ—©ä¸Š6-8ç‚¹é€æ¸æ´»è·ƒï¼ˆæ´»è·ƒåº¦ç³»æ•°0.4ï¼‰
- å·¥ä½œæ—¶é—´9-18ç‚¹ä¸­ç­‰æ´»è·ƒï¼ˆæ´»è·ƒåº¦ç³»æ•°0.7ï¼‰
- æ™šé—´19-22ç‚¹æ˜¯é«˜å³°æœŸï¼ˆæ´»è·ƒåº¦ç³»æ•°1.5ï¼‰
- 23ç‚¹åŽæ´»è·ƒåº¦ä¸‹é™ï¼ˆæ´»è·ƒåº¦ç³»æ•°0.5ï¼‰
- ä¸€èˆ¬è§„å¾‹ï¼šå‡Œæ™¨ä½Žæ´»è·ƒã€æ—©é—´æ¸å¢žã€å·¥ä½œæ—¶æ®µä¸­ç­‰ã€æ™šé—´é«˜å³°
- **é‡è¦**ï¼šä»¥ä¸‹ç¤ºä¾‹å€¼ä»…ä¾›å‚è€ƒï¼Œä½ éœ€è¦æ ¹æ®äº‹ä»¶æ€§è´¨ã€å‚ä¸Žç¾¤ä½“ç‰¹ç‚¹æ¥è°ƒæ•´å…·ä½“æ—¶æ®µ
  - ä¾‹å¦‚ï¼šå­¦ç”Ÿç¾¤ä½“é«˜å³°å¯èƒ½æ˜¯21-23ç‚¹ï¼›åª’ä½“å…¨å¤©æ´»è·ƒï¼›å®˜æ–¹æœºæž„åªåœ¨å·¥ä½œæ—¶é—´
  - ä¾‹å¦‚ï¼šçªå‘çƒ­ç‚¹å¯èƒ½å¯¼è‡´æ·±å¤œä¹Ÿæœ‰è®¨è®ºï¼Œoff_peak_hours å¯é€‚å½“ç¼©çŸ­


ç¤ºä¾‹ï¼š
{{
    "total_simulation_hours": 72,
    "minutes_per_round": 60,
    "agents_per_hour_min": 5,
    "agents_per_hour_max": 50,
    "peak_hours": [19, 20, 21, 22],
    "off_peak_hours": [0, 1, 2, 3, 4, 5],
    "morning_hours": [6, 7, 8],
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    "reasoning": "é’ˆå¯¹è¯¥äº‹ä»¶çš„æ—¶é—´é…ç½®è¯´æ˜Ž"
}}

å­—æ®µè¯´æ˜Žï¼š
- total_simulation_hours (int): æ¨¡æ‹Ÿæ€»æ—¶é•¿ï¼Œ24-168å°æ—¶ï¼Œçªå‘äº‹ä»¶çŸ­ã€æŒç»­è¯é¢˜é•¿
- minutes_per_round (int): æ¯è½®æ—¶é•¿ï¼Œ30-120åˆ†é’Ÿï¼Œå»ºè®®60åˆ†é’Ÿ
- agents_per_hour_min (int): æ¯å°æ—¶æœ€å°‘æ¿€æ´»Agentæ•°ï¼ˆå–å€¼èŒƒå›´: 1-{max_agents_allowed}ï¼‰
- agents_per_hour_max (int): æ¯å°æ—¶æœ€å¤šæ¿€æ´»Agentæ•°ï¼ˆå–å€¼èŒƒå›´: 1-{max_agents_allowed}ï¼‰
- peak_hours (intæ•°ç»„): é«˜å³°æ—¶æ®µï¼Œæ ¹æ®äº‹ä»¶å‚ä¸Žç¾¤ä½“è°ƒæ•´
- off_peak_hours (intæ•°ç»„): ä½Žè°·æ—¶æ®µï¼Œé€šå¸¸æ·±å¤œå‡Œæ™¨
- morning_hours (intæ•°ç»„): æ—©é—´æ—¶æ®µ
- work_hours (intæ•°ç»„): å·¥ä½œæ—¶æ®µ
- reasoning (string): ç®€è¦è¯´æ˜Žä¸ºä»€ä¹ˆè¿™æ ·é…ç½®"""

        system_prompt = "ä½ æ˜¯ç¤¾äº¤åª’ä½“æ¨¡æ‹Ÿä¸“å®¶ã€‚è¿”å›žçº¯JSONæ ¼å¼ï¼Œæ—¶é—´é…ç½®éœ€ç¬¦åˆæ¨¡æ‹Ÿåœºæ™¯ä¸­ç›®æ ‡ç”¨æˆ·ç¾¤ä½“çš„ä½œæ¯ä¹ æƒ¯ã€‚"
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}"

        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"æ—¶é—´é…ç½®LLMç”Ÿæˆå¤±è´¥: {e}, ä½¿ç”¨é»˜è®¤é…ç½®")
            return self._get_default_time_config(num_entities)
    
    def _get_default_time_config(self, num_entities: int) -> Dict[str, Any]:
        """èŽ·å–é»˜è®¤æ—¶é—´é…ç½®ï¼ˆä¸­å›½äººä½œæ¯ï¼‰"""
        return {
            "total_simulation_hours": 72,
            "minutes_per_round": 60,  # æ¯è½®1å°æ—¶ï¼ŒåŠ å¿«æ—¶é—´æµé€Ÿ
            "agents_per_hour_min": max(1, num_entities // 15),
            "agents_per_hour_max": max(5, num_entities // 5),
            "peak_hours": [19, 20, 21, 22],
            "off_peak_hours": [0, 1, 2, 3, 4, 5],
            "morning_hours": [6, 7, 8],
            "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            "reasoning": "ä½¿ç”¨é»˜è®¤ä¸­å›½äººä½œæ¯é…ç½®ï¼ˆæ¯è½®1å°æ—¶ï¼‰"
        }
    
    def _parse_time_config(self, result: Dict[str, Any], num_entities: int) -> TimeSimulationConfig:
        """è§£æžæ—¶é—´é…ç½®ç»“æžœï¼Œå¹¶éªŒè¯agents_per_hourå€¼ä¸è¶…è¿‡æ€»agentæ•°"""
        agents_per_hour_min = result.get("agents_per_hour_min", max(1, num_entities // 15))
        agents_per_hour_max = result.get("agents_per_hour_max", max(5, num_entities // 5))
        
        if agents_per_hour_min > num_entities:
            logger.warning(f"agents_per_hour_min ({agents_per_hour_min}) è¶…è¿‡æ€»Agentæ•° ({num_entities})ï¼Œå·²ä¿®æ­£")
            agents_per_hour_min = max(1, num_entities // 10)
        
        if agents_per_hour_max > num_entities:
            logger.warning(f"agents_per_hour_max ({agents_per_hour_max}) è¶…è¿‡æ€»Agentæ•° ({num_entities})ï¼Œå·²ä¿®æ­£")
            agents_per_hour_max = max(agents_per_hour_min + 1, num_entities // 2)
        
        if agents_per_hour_min >= agents_per_hour_max:
            agents_per_hour_min = max(1, agents_per_hour_max // 2)
            logger.warning(f"agents_per_hour_min >= maxï¼Œå·²ä¿®æ­£ä¸º {agents_per_hour_min}")
        
        return TimeSimulationConfig(
            total_simulation_hours=result.get("total_simulation_hours", 72),
            minutes_per_round=result.get("minutes_per_round", 60),  # é»˜è®¤æ¯è½®1å°æ—¶
            agents_per_hour_min=agents_per_hour_min,
            agents_per_hour_max=agents_per_hour_max,
            peak_hours=result.get("peak_hours", [19, 20, 21, 22]),
            off_peak_hours=result.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
            off_peak_activity_multiplier=0.05,  # å‡Œæ™¨å‡ ä¹Žæ— äºº
            morning_hours=result.get("morning_hours", [6, 7, 8]),
            morning_activity_multiplier=0.4,
            work_hours=result.get("work_hours", list(range(9, 19))),
            work_activity_multiplier=0.7,
            peak_activity_multiplier=1.5
        )
    
    def _generate_event_config(
        self, 
        context: str, 
        simulation_requirement: str,
        entities: List[EntityNode]
    ) -> Dict[str, Any]:
        """ç”Ÿæˆäº‹ä»¶é…ç½®"""
        
        entity_types_available = list(set(
            e.get_entity_type() or "Unknown" for e in entities
        ))
        
        type_examples = {}
        for e in entities:
            etype = e.get_entity_type() or "Unknown"
            if etype not in type_examples:
                type_examples[etype] = []
            if len(type_examples[etype]) < 3:
                type_examples[etype].append(e.name)
        
        type_info = "\n".join([
            f"- {t}: {', '.join(examples)}" 
            for t, examples in type_examples.items()
        ])
        
        context_truncated = context[:self.EVENT_CONFIG_CONTEXT_LENGTH]
        
        prompt = f"""åŸºäºŽä»¥ä¸‹æ¨¡æ‹Ÿéœ€æ±‚ï¼Œç”Ÿæˆäº‹ä»¶é…ç½®ã€‚

æ¨¡æ‹Ÿéœ€æ±‚: {simulation_requirement}

{context_truncated}

{type_info}

è¯·ç”Ÿæˆäº‹ä»¶é…ç½®JSONï¼š
- æå–çƒ­ç‚¹è¯é¢˜å…³é”®è¯
- æè¿°èˆ†è®ºå‘å±•æ–¹å‘
- è®¾è®¡åˆå§‹å¸–å­å†…å®¹ï¼Œ**æ¯ä¸ªå¸–å­å¿…é¡»æŒ‡å®š poster_typeï¼ˆå‘å¸ƒè€…ç±»åž‹ï¼‰**

**é‡è¦**: poster_type å¿…é¡»ä»Žä¸Šé¢çš„"å¯ç”¨å®žä½“ç±»åž‹"ä¸­é€‰æ‹©ï¼Œè¿™æ ·åˆå§‹å¸–å­æ‰èƒ½åˆ†é…ç»™åˆé€‚çš„ Agent å‘å¸ƒã€‚
ä¾‹å¦‚ï¼šå®˜æ–¹å£°æ˜Žåº”ç”± Official/University ç±»åž‹å‘å¸ƒï¼Œæ–°é—»ç”± MediaOutlet å‘å¸ƒï¼Œå­¦ç”Ÿè§‚ç‚¹ç”± Student å‘å¸ƒã€‚

è¿”å›žJSONæ ¼å¼ï¼ˆä¸è¦markdownï¼‰ï¼š
{{
    "hot_topics": ["å…³é”®è¯1", "å…³é”®è¯2", ...],
    "narrative_direction": "<èˆ†è®ºå‘å±•æ–¹å‘æè¿°>",
    "initial_posts": [
        {{"content": "å¸–å­å†…å®¹", "poster_type": "å®žä½“ç±»åž‹ï¼ˆå¿…é¡»ä»Žå¯ç”¨ç±»åž‹ä¸­é€‰æ‹©ï¼‰"}},
        ...
    ],
    "reasoning": "<ç®€è¦è¯´æ˜Ž>"
}}"""

        system_prompt = "ä½ æ˜¯èˆ†è®ºåˆ†æžä¸“å®¶ã€‚è¿”å›žçº¯JSONæ ¼å¼ã€‚æ³¨æ„ poster_type å¿…é¡»ç²¾ç¡®åŒ¹é…å¯ç”¨å®žä½“ç±»åž‹ã€‚"
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}\nIMPORTANT: The 'poster_type' field value MUST be in English PascalCase exactly matching the available entity types. Only 'content', 'narrative_direction', 'hot_topics' and 'reasoning' fields should use the specified language."

        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"äº‹ä»¶é…ç½®LLMç”Ÿæˆå¤±è´¥: {e}, ä½¿ç”¨é»˜è®¤é…ç½®")
            return {
                "hot_topics": [],
                "narrative_direction": "",
                "initial_posts": [],
                "reasoning": "ä½¿ç”¨é»˜è®¤é…ç½®"
            }
    
    def _parse_event_config(self, result: Dict[str, Any]) -> EventConfig:
        """è§£æžäº‹ä»¶é…ç½®ç»“æžœ"""
        return EventConfig(
            initial_posts=result.get("initial_posts", []),
            scheduled_events=[],
            hot_topics=result.get("hot_topics", []),
            narrative_direction=result.get("narrative_direction", "")
        )
    
    def _assign_initial_post_agents(
        self,
        event_config: EventConfig,
        agent_configs: List[AgentActivityConfig]
    ) -> EventConfig:
        """
        
        """
        if not event_config.initial_posts:
            return event_config
        
        agents_by_type: Dict[str, List[AgentActivityConfig]] = {}
        for agent in agent_configs:
            etype = agent.entity_type.lower()
            if etype not in agents_by_type:
                agents_by_type[etype] = []
            agents_by_type[etype].append(agent)
        
        type_aliases = {
            "official": ["official", "university", "governmentagency", "government"],
            "university": ["university", "official"],
            "mediaoutlet": ["mediaoutlet", "media"],
            "student": ["student", "person"],
            "professor": ["professor", "expert", "teacher"],
            "alumni": ["alumni", "person"],
            "organization": ["organization", "ngo", "company", "group"],
            "person": ["person", "student", "alumni"],
        }
        
        used_indices: Dict[str, int] = {}
        
        updated_posts = []
        for post in event_config.initial_posts:
            poster_type = post.get("poster_type", "").lower()
            content = post.get("content", "")
            
            matched_agent_id = None
            
            if poster_type in agents_by_type:
                agents = agents_by_type[poster_type]
                idx = used_indices.get(poster_type, 0) % len(agents)
                matched_agent_id = agents[idx].agent_id
                used_indices[poster_type] = idx + 1
            else:
                for alias_key, aliases in type_aliases.items():
                    if poster_type in aliases or alias_key == poster_type:
                        for alias in aliases:
                            if alias in agents_by_type:
                                agents = agents_by_type[alias]
                                idx = used_indices.get(alias, 0) % len(agents)
                                matched_agent_id = agents[idx].agent_id
                                used_indices[alias] = idx + 1
                                break
                    if matched_agent_id is not None:
                        break
            
            if matched_agent_id is None:
                logger.warning(f"æœªæ‰¾åˆ°ç±»åž‹ '{poster_type}' çš„åŒ¹é… Agentï¼Œä½¿ç”¨å½±å“åŠ›æœ€é«˜çš„ Agent")
                if agent_configs:
                    sorted_agents = sorted(agent_configs, key=lambda a: a.influence_weight, reverse=True)
                    matched_agent_id = sorted_agents[0].agent_id
                else:
                    matched_agent_id = 0
            
            updated_posts.append({
                "content": content,
                "poster_type": post.get("poster_type", "Unknown"),
                "poster_agent_id": matched_agent_id
            })
            
            logger.info(f"åˆå§‹å¸–å­åˆ†é…: poster_type='{poster_type}' -> agent_id={matched_agent_id}")
        
        event_config.initial_posts = updated_posts
        return event_config
    
    def _generate_agent_configs_batch(
        self,
        context: str,
        entities: List[EntityNode],
        start_idx: int,
        simulation_requirement: str
    ) -> List[AgentActivityConfig]:
        """åˆ†æ‰¹ç”ŸæˆAgenté…ç½®"""
        
        entity_list = []
        summary_len = self.AGENT_SUMMARY_LENGTH
        for i, e in enumerate(entities):
            entity_list.append({
                "agent_id": start_idx + i,
                "entity_name": e.name,
                "entity_type": e.get_entity_type() or "Unknown",
                "summary": e.summary[:summary_len] if e.summary else ""
            })
        
        prompt = f"""åŸºäºŽä»¥ä¸‹ä¿¡æ¯ï¼Œä¸ºæ¯ä¸ªå®žä½“ç”Ÿæˆç¤¾äº¤åª’ä½“æ´»åŠ¨é…ç½®ã€‚

æ¨¡æ‹Ÿéœ€æ±‚: {simulation_requirement}

```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

ä¸ºæ¯ä¸ªå®žä½“ç”Ÿæˆæ´»åŠ¨é…ç½®ï¼Œæ³¨æ„ï¼š
- **æ—¶é—´ç¬¦åˆç›®æ ‡ç”¨æˆ·ç¾¤ä½“ä½œæ¯**ï¼šä»¥ä¸‹ä¸ºå‚è€ƒï¼ˆä¸œå…«åŒºï¼‰ï¼Œè¯·æ ¹æ®æ¨¡æ‹Ÿåœºæ™¯è°ƒæ•´
- **å®˜æ–¹æœºæž„**ï¼ˆUniversity/GovernmentAgencyï¼‰ï¼šæ´»è·ƒåº¦ä½Ž(0.1-0.3)ï¼Œå·¥ä½œæ—¶é—´(9-17)æ´»åŠ¨ï¼Œå“åº”æ…¢(60-240åˆ†é’Ÿ)ï¼Œå½±å“åŠ›é«˜(2.5-3.0)
- **åª’ä½“**ï¼ˆMediaOutletï¼‰ï¼šæ´»è·ƒåº¦ä¸­(0.4-0.6)ï¼Œå…¨å¤©æ´»åŠ¨(8-23)ï¼Œå“åº”å¿«(5-30åˆ†é’Ÿ)ï¼Œå½±å“åŠ›é«˜(2.0-2.5)
- **ä¸ªäºº**ï¼ˆStudent/Person/Alumniï¼‰ï¼šæ´»è·ƒåº¦é«˜(0.6-0.9)ï¼Œä¸»è¦æ™šé—´æ´»åŠ¨(18-23)ï¼Œå“åº”å¿«(1-15åˆ†é’Ÿ)ï¼Œå½±å“åŠ›ä½Ž(0.8-1.2)
- **å…¬ä¼—äººç‰©/ä¸“å®¶**ï¼šæ´»è·ƒåº¦ä¸­(0.4-0.6)ï¼Œå½±å“åŠ›ä¸­é«˜(1.5-2.0)

è¿”å›žJSONæ ¼å¼ï¼ˆä¸è¦markdownï¼‰ï¼š
{{
    "agent_configs": [
        {{
            "agent_id": <å¿…é¡»ä¸Žè¾“å…¥ä¸€è‡´>,
            "activity_level": <0.0-1.0>,
            "posts_per_hour": <å‘å¸–é¢‘çŽ‡>,
            "comments_per_hour": <è¯„è®ºé¢‘çŽ‡>,
            "active_hours": [<æ´»è·ƒå°æ—¶åˆ—è¡¨ï¼Œè€ƒè™‘ä¸­å›½äººä½œæ¯>],
            "response_delay_min": <æœ€å°å“åº”å»¶è¿Ÿåˆ†é’Ÿ>,
            "response_delay_max": <æœ€å¤§å“åº”å»¶è¿Ÿåˆ†é’Ÿ>,
            "sentiment_bias": <-1.0åˆ°1.0>,
            "stance": "<supportive/opposing/neutral/observer>",
            "influence_weight": <å½±å“åŠ›æƒé‡>
        }},
        ...
    ]
}}"""

        system_prompt = "ä½ æ˜¯ç¤¾äº¤åª’ä½“è¡Œä¸ºåˆ†æžä¸“å®¶ã€‚è¿”å›žçº¯JSONï¼Œé…ç½®éœ€ç¬¦åˆæ¨¡æ‹Ÿåœºæ™¯ä¸­ç›®æ ‡ç”¨æˆ·ç¾¤ä½“çš„ä½œæ¯ä¹ æƒ¯ã€‚"
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}\nIMPORTANT: The 'stance' field value MUST be one of the English strings: 'supportive', 'opposing', 'neutral', 'observer'. All JSON field names and numeric values must remain unchanged. Only natural language text fields should use the specified language."

        try:
            result = self._call_llm_with_retry(prompt, system_prompt)
            llm_configs = {cfg["agent_id"]: cfg for cfg in result.get("agent_configs", [])}
        except Exception as e:
            logger.warning(f"Agenté…ç½®æ‰¹æ¬¡LLMç”Ÿæˆå¤±è´¥: {e}, ä½¿ç”¨è§„åˆ™ç”Ÿæˆ")
            llm_configs = {}
        
        configs = []
        for i, entity in enumerate(entities):
            agent_id = start_idx + i
            cfg = llm_configs.get(agent_id, {})
            
            if not cfg:
                cfg = self._generate_agent_config_by_rule(entity)
            
            config = AgentActivityConfig(
                agent_id=agent_id,
                entity_uuid=entity.uuid,
                entity_name=entity.name,
                entity_type=entity.get_entity_type() or "Unknown",
                activity_level=cfg.get("activity_level", 0.5),
                posts_per_hour=cfg.get("posts_per_hour", 0.5),
                comments_per_hour=cfg.get("comments_per_hour", 1.0),
                active_hours=cfg.get("active_hours", list(range(9, 23))),
                response_delay_min=cfg.get("response_delay_min", 5),
                response_delay_max=cfg.get("response_delay_max", 60),
                sentiment_bias=cfg.get("sentiment_bias", 0.0),
                stance=cfg.get("stance", "neutral"),
                influence_weight=cfg.get("influence_weight", 1.0)
            )
            configs.append(config)
        
        return configs
    
    def _generate_agent_config_by_rule(self, entity: EntityNode) -> Dict[str, Any]:
        """åŸºäºŽè§„åˆ™ç”Ÿæˆå•ä¸ªAgenté…ç½®ï¼ˆä¸­å›½äººä½œæ¯ï¼‰"""
        entity_type = (entity.get_entity_type() or "Unknown").lower()
        
        if entity_type in ["university", "governmentagency", "ngo"]:
            return {
                "activity_level": 0.2,
                "posts_per_hour": 0.1,
                "comments_per_hour": 0.05,
                "active_hours": list(range(9, 18)),  # 9:00-17:59
                "response_delay_min": 60,
                "response_delay_max": 240,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 3.0
            }
        elif entity_type in ["mediaoutlet"]:
            return {
                "activity_level": 0.5,
                "posts_per_hour": 0.8,
                "comments_per_hour": 0.3,
                "active_hours": list(range(7, 24)),  # 7:00-23:59
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "observer",
                "influence_weight": 2.5
            }
        elif entity_type in ["professor", "expert", "official"]:
            return {
                "activity_level": 0.4,
                "posts_per_hour": 0.3,
                "comments_per_hour": 0.5,
                "active_hours": list(range(8, 22)),  # 8:00-21:59
                "response_delay_min": 15,
                "response_delay_max": 90,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 2.0
            }
        elif entity_type in ["student"]:
            return {
                "activity_level": 0.8,
                "posts_per_hour": 0.6,
                "comments_per_hour": 1.5,
                "active_hours": [8, 9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # ä¸Šåˆ+æ™šé—´
                "response_delay_min": 1,
                "response_delay_max": 15,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 0.8
            }
        elif entity_type in ["alumni"]:
            return {
                "activity_level": 0.6,
                "posts_per_hour": 0.4,
                "comments_per_hour": 0.8,
                "active_hours": [12, 13, 19, 20, 21, 22, 23],  # åˆä¼‘+æ™šé—´
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
        else:
            return {
                "activity_level": 0.7,
                "posts_per_hour": 0.5,
                "comments_per_hour": 1.2,
                "active_hours": [9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # ç™½å¤©+æ™šé—´
                "response_delay_min": 2,
                "response_delay_max": 20,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
    


"""

"""

import json
import random
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from openai import OpenAI
from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_language_instruction, get_locale, set_locale, t
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('posiedon.oasis_profile')


@dataclass
class OasisAgentProfile:
    """OASIS Agent Profileæ•°æ®ç»“æž„"""
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str
    
    karma: int = 1000
    
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500
    
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)
    
    # Opinion drift fields
    # opinion_state: Maps topic -> opinion value [-1.0 to 1.0]
    # -1.0 = strongly against, 0 = neutral, 1.0 = strongly for
    opinion_state: Dict[str, float] = field(default_factory=dict)
    
    # susceptibility: How easily opinions change (0.0 = unchangeable, 1.0 = highly malleable)
    # Correlates with openness trait if MBTI is available
    susceptibility: float = 0.5
    
    # opinion_history: List of {round, topic, value} tuples tracking opinion changes
    opinion_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Big Five openness trait (derived from MBTI or set directly)
    openness: Optional[float] = None
    
    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None
    
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    def to_reddit_format(self) -> Dict[str, Any]:
        """è½¬æ¢ä¸ºRedditå¹³å°æ ¼å¼"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS åº“è¦æ±‚å­—æ®µåä¸º usernameï¼ˆæ— ä¸‹åˆ’çº¿ï¼‰
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }
        
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        # Opinion drift fields
        profile["opinion_state"] = self.opinion_state
        profile["susceptibility"] = self.susceptibility
        profile["opinion_history"] = self.opinion_history
        if self.openness is not None:
            profile["openness"] = self.openness
        
        return profile
    
    def to_twitter_format(self) -> Dict[str, Any]:
        """è½¬æ¢ä¸ºTwitterå¹³å°æ ¼å¼"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS åº“è¦æ±‚å­—æ®µåä¸º usernameï¼ˆæ— ä¸‹åˆ’çº¿ï¼‰
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }
        
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        # Opinion drift fields
        profile["opinion_state"] = self.opinion_state
        profile["susceptibility"] = self.susceptibility
        profile["opinion_history"] = self.opinion_history
        if self.openness is not None:
            profile["openness"] = self.openness
        
        return profile
    
    def to_dict(self) -> Dict[str, Any]:
        """è½¬æ¢ä¸ºå®Œæ•´å­—å…¸æ ¼å¼"""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
            # Opinion drift fields
            "opinion_state": self.opinion_state,
            "susceptibility": self.susceptibility,
            "opinion_history": self.opinion_history,
            "openness": self.openness,
        }
    
    def update_opinion(self, topic: str, new_value: float, round_number: int) -> None:
        """
        Update opinion on a topic and record in history.
        
        Args:
            topic: The topic/issue to update opinion on
            new_value: New opinion value (-1.0 to 1.0)
            round_number: Current simulation round
        """
        # Clamp value to valid range
        new_value = max(-1.0, min(1.0, new_value))
        
        # Update current state
        self.opinion_state[topic] = new_value
        
        # Record in history
        self.opinion_history.append({
            "round": round_number,
            "topic": topic,
            "value": new_value
        })
    
    def get_opinion(self, topic: str) -> float:
        """Get current opinion on a topic (0.0 if not set)."""
        return self.opinion_state.get(topic, 0.0)
    
    @staticmethod
    def calculate_susceptibility_from_mbti(mbti: str) -> float:
        """
        Calculate susceptibility based on MBTI type.
        
        Higher openness (N types, especially NP) = higher susceptibility.
        """
        if not mbti or len(mbti) != 4:
            return 0.5  # Default
        
        susceptibility = 0.5
        
        # Intuitive (N) types are more open to new ideas
        if mbti[1] == 'N':
            susceptibility += 0.15
        else:  # Sensing (S) types are more traditional
            susceptibility -= 0.1
        
        # Perceiving (P) types are more flexible
        if mbti[3] == 'P':
            susceptibility += 0.1
        else:  # Judging (J) types are more set in their ways
            susceptibility -= 0.05
        
        # Feeling (F) types may be more influenced by others
        if mbti[2] == 'F':
            susceptibility += 0.05
        
        # Clamp to valid range
        return max(0.0, min(1.0, susceptibility))


class OasisProfileGenerator:
    """
    
    
    """
    
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]
    
    COUNTRIES = [
        "China", "US", "UK", "Japan", "Germany", "France", 
        "Canada", "Australia", "Brazil", "India", "South Korea"
    ]
    
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure", 
        "expert", "faculty", "official", "journalist", "activist"
    ]
    
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo", 
        "mediaoutlet", "company", "institution", "group", "community"
    ]
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        zep_api_key: Optional[str] = None,
        graph_id: Optional[str] = None
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
        
        self.zep_api_key = zep_api_key or Config.ZEP_API_KEY
        self.zep_client = None
        self.graph_id = graph_id
        
        if self.zep_api_key:
            try:
                self.zep_client = Zep(api_key=self.zep_api_key)
            except Exception as e:
                logger.warning(f"Zepå®¢æˆ·ç«¯åˆå§‹åŒ–å¤±è´¥: {e}")
    
    def generate_profile_from_entity(
        self, 
        entity: EntityNode, 
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
        
        Args:
            
        Returns:
            OasisAgentProfile
        """
        entity_type = entity.get_entity_type() or "Entity"
        
        name = entity.name
        user_name = self._generate_username(name)
        
        context = self._build_entity_context(entity)
        
        if use_llm:
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )
        
        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )
    
    def _generate_username(self, name: str) -> str:
        """ç”Ÿæˆç”¨æˆ·å"""
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')
        
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"
    
    def _search_zep_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
        
        
        Args:
            
        Returns:
        """
        import concurrent.futures
        
        if not self.zep_client:
            return {"facts": [], "node_summaries": [], "context": ""}
        
        entity_name = entity.name
        
        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }
        
        if not self.graph_id:
            logger.debug(f"è·³è¿‡Zepæ£€ç´¢ï¼šæœªè®¾ç½®graph_id")
            return results
        
        comprehensive_query = t('progress.zepSearchQuery', name=entity_name)
        
        def search_edges():
            """æœç´¢è¾¹ï¼ˆäº‹å®ž/å…³ç³»ï¼‰- å¸¦é‡è¯•æœºåˆ¶"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=30,
                        scope="edges",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zepè¾¹æœç´¢ç¬¬ {attempt + 1} æ¬¡å¤±è´¥: {str(e)[:80]}, é‡è¯•ä¸­...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zepè¾¹æœç´¢åœ¨ {max_retries} æ¬¡å°è¯•åŽä»å¤±è´¥: {e}")
            return None
        
        def search_nodes():
            """æœç´¢èŠ‚ç‚¹ï¼ˆå®žä½“æ‘˜è¦ï¼‰- å¸¦é‡è¯•æœºåˆ¶"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=20,
                        scope="nodes",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"ZepèŠ‚ç‚¹æœç´¢ç¬¬ {attempt + 1} æ¬¡å¤±è´¥: {str(e)[:80]}, é‡è¯•ä¸­...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"ZepèŠ‚ç‚¹æœç´¢åœ¨ {max_retries} æ¬¡å°è¯•åŽä»å¤±è´¥: {e}")
            return None
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                edge_future = executor.submit(search_edges)
                node_future = executor.submit(search_nodes)
                
                edge_result = edge_future.result(timeout=30)
                node_result = node_future.result(timeout=30)
            
            all_facts = set()
            if edge_result and hasattr(edge_result, 'edges') and edge_result.edges:
                for edge in edge_result.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        all_facts.add(edge.fact)
            results["facts"] = list(all_facts)
            
            all_summaries = set()
            if node_result and hasattr(node_result, 'nodes') and node_result.nodes:
                for node in node_result.nodes:
                    if hasattr(node, 'summary') and node.summary:
                        all_summaries.add(node.summary)
                    if hasattr(node, 'name') and node.name and node.name != entity_name:
                        all_summaries.add(f"ç›¸å…³å®žä½“: {node.name}")
            results["node_summaries"] = list(all_summaries)
            
            context_parts = []
            if results["facts"]:
                context_parts.append("äº‹å®žä¿¡æ¯:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("ç›¸å…³å®žä½“:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)
            
            logger.info(f"Zepæ··åˆæ£€ç´¢å®Œæˆ: {entity_name}, èŽ·å– {len(results['facts'])} æ¡äº‹å®ž, {len(results['node_summaries'])} ä¸ªç›¸å…³èŠ‚ç‚¹")
            
        except concurrent.futures.TimeoutError:
            logger.warning(f"Zepæ£€ç´¢è¶…æ—¶ ({entity_name})")
        except Exception as e:
            logger.warning(f"Zepæ£€ç´¢å¤±è´¥ ({entity_name}): {e}")
        
        return results
    
    def _build_entity_context(self, entity: EntityNode) -> str:
        """
        
        """
        context_parts = []
        
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### å®žä½“å±žæ€§\n" + "\n".join(attrs))
        
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:  # ä¸é™åˆ¶æ•°é‡
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")
                
                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (ç›¸å…³å®žä½“)")
                    else:
                        relationships.append(f"- (ç›¸å…³å®žä½“) --[{edge_name}]--> {entity.name}")
            
            if relationships:
                context_parts.append("### ç›¸å…³äº‹å®žå’Œå…³ç³»\n" + "\n".join(relationships))
        
        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes:  # ä¸é™åˆ¶æ•°é‡
                node_name = node.get("name", "")
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")
                
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""
                
                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")
            
            if related_info:
                context_parts.append("### å…³è”å®žä½“ä¿¡æ¯\n" + "\n".join(related_info))
        
        zep_results = self._search_zep_for_entity(entity)
        
        if zep_results.get("facts"):
            new_facts = [f for f in zep_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### Zepæ£€ç´¢åˆ°çš„äº‹å®žä¿¡æ¯\n" + "\n".join(f"- {f}" for f in new_facts[:15]))
        
        if zep_results.get("node_summaries"):
            context_parts.append("### Zepæ£€ç´¢åˆ°çš„ç›¸å…³èŠ‚ç‚¹\n" + "\n".join(f"- {s}" for s in zep_results["node_summaries"][:10]))
        
        return "\n\n".join(context_parts)
    
    def _is_individual_entity(self, entity_type: str) -> bool:
        """åˆ¤æ–­æ˜¯å¦æ˜¯ä¸ªäººç±»åž‹å®žä½“"""
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES
    
    def _is_group_entity(self, entity_type: str) -> bool:
        """åˆ¤æ–­æ˜¯å¦æ˜¯ç¾¤ä½“/æœºæž„ç±»åž‹å®žä½“"""
        return entity_type.lower() in self.GROUP_ENTITY_TYPES
    
    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        
        """
        
        is_individual = self._is_individual_entity(entity_type)
        
        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt(is_individual)},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1)  # æ¯æ¬¡é‡è¯•é™ä½Žæ¸©åº¦
                )
                
                content = response.choices[0].message.content
                
                finish_reason = response.choices[0].finish_reason
                if finish_reason == 'length':
                    logger.warning(f"LLMè¾“å‡ºè¢«æˆªæ–­ (attempt {attempt+1}), å°è¯•ä¿®å¤...")
                    content = self._fix_truncated_json(content)
                
                try:
                    result = json.loads(content)
                    
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name}æ˜¯ä¸€ä¸ª{entity_type}ã€‚"
                    
                    return result
                    
                except json.JSONDecodeError as je:
                    logger.warning(f"JSONè§£æžå¤±è´¥ (attempt {attempt+1}): {str(je)[:80]}")
                    
                    result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result
                    
                    last_error = je
                    
            except Exception as e:
                logger.warning(f"LLMè°ƒç”¨å¤±è´¥ (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(1 * (attempt + 1))  # æŒ‡æ•°é€€é¿
        
        logger.warning(f"LLMç”Ÿæˆäººè®¾å¤±è´¥ï¼ˆ{max_attempts}æ¬¡å°è¯•ï¼‰: {last_error}, ä½¿ç”¨è§„åˆ™ç”Ÿæˆ")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )
    
    def _fix_truncated_json(self, content: str) -> str:
        """ä¿®å¤è¢«æˆªæ–­çš„JSONï¼ˆè¾“å‡ºè¢«max_tokensé™åˆ¶æˆªæ–­ï¼‰"""
        import re
        
        content = content.strip()
        
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        if content and content[-1] not in '",}]':
            content += '"'
        
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        """å°è¯•ä¿®å¤æŸåçš„JSON"""
        import re
        
        content = self._fix_truncated_json(content)
        
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            def fix_string_newlines(match):
                s = match.group(0)
                s = s.replace('\n', ' ').replace('\r', ' ')
                s = re.sub(r'\s+', ' ', s)
                return s
            
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)
            
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError as e:
                try:
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except:
                    pass
        
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # å¯èƒ½è¢«æˆªæ–­
        
        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name}æ˜¯ä¸€ä¸ª{entity_type}ã€‚")
        
        if bio_match or persona_match:
            logger.info(f"ä»ŽæŸåçš„JSONä¸­æå–äº†éƒ¨åˆ†ä¿¡æ¯")
            return {
                "bio": bio,
                "persona": persona,
                "_fixed": True
            }
        
        logger.warning(f"JSONä¿®å¤å¤±è´¥ï¼Œè¿”å›žåŸºç¡€ç»“æž„")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name}æ˜¯ä¸€ä¸ª{entity_type}ã€‚"
        }
    
    def _get_system_prompt(self, is_individual: bool) -> str:
        """èŽ·å–ç³»ç»Ÿæç¤ºè¯"""
        base_prompt = "ä½ æ˜¯ç¤¾äº¤åª’ä½“ç”¨æˆ·ç”»åƒç”Ÿæˆä¸“å®¶ã€‚ç”Ÿæˆè¯¦ç»†ã€çœŸå®žçš„äººè®¾ç”¨äºŽèˆ†è®ºæ¨¡æ‹Ÿ,æœ€å¤§ç¨‹åº¦è¿˜åŽŸå·²æœ‰çŽ°å®žæƒ…å†µã€‚å¿…é¡»è¿”å›žæœ‰æ•ˆçš„JSONæ ¼å¼ï¼Œæ‰€æœ‰å­—ç¬¦ä¸²å€¼ä¸èƒ½åŒ…å«æœªè½¬ä¹‰çš„æ¢è¡Œç¬¦ã€‚"
        return f"{base_prompt}\n\n{get_language_instruction()}"
    
    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """æž„å»ºä¸ªäººå®žä½“çš„è¯¦ç»†äººè®¾æç¤ºè¯"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "æ— "
        context_str = context[:3000] if context else "æ— é¢å¤–ä¸Šä¸‹æ–‡"
        
        return f"""ä¸ºå®žä½“ç”Ÿæˆè¯¦ç»†çš„ç¤¾äº¤åª’ä½“ç”¨æˆ·äººè®¾,æœ€å¤§ç¨‹åº¦è¿˜åŽŸå·²æœ‰çŽ°å®žæƒ…å†µã€‚

å®žä½“åç§°: {entity_name}
å®žä½“ç±»åž‹: {entity_type}
å®žä½“æ‘˜è¦: {entity_summary}
å®žä½“å±žæ€§: {attrs_str}

ä¸Šä¸‹æ–‡ä¿¡æ¯:
{context_str}

è¯·ç”ŸæˆJSONï¼ŒåŒ…å«ä»¥ä¸‹å­—æ®µ:

1. bio: ç¤¾äº¤åª’ä½“ç®€ä»‹ï¼Œ200å­—
2. persona: è¯¦ç»†äººè®¾æè¿°ï¼ˆ2000å­—çš„çº¯æ–‡æœ¬ï¼‰ï¼Œéœ€åŒ…å«:
   - åŸºæœ¬ä¿¡æ¯ï¼ˆå¹´é¾„ã€èŒä¸šã€æ•™è‚²èƒŒæ™¯ã€æ‰€åœ¨åœ°ï¼‰
   - äººç‰©èƒŒæ™¯ï¼ˆé‡è¦ç»åŽ†ã€ä¸Žäº‹ä»¶çš„å…³è”ã€ç¤¾ä¼šå…³ç³»ï¼‰
   - æ€§æ ¼ç‰¹å¾ï¼ˆMBTIç±»åž‹ã€æ ¸å¿ƒæ€§æ ¼ã€æƒ…ç»ªè¡¨è¾¾æ–¹å¼ï¼‰
   - ç¤¾äº¤åª’ä½“è¡Œä¸ºï¼ˆå‘å¸–é¢‘çŽ‡ã€å†…å®¹åå¥½ã€äº’åŠ¨é£Žæ ¼ã€è¯­è¨€ç‰¹ç‚¹ï¼‰
   - ç«‹åœºè§‚ç‚¹ï¼ˆå¯¹è¯é¢˜çš„æ€åº¦ã€å¯èƒ½è¢«æ¿€æ€’/æ„ŸåŠ¨çš„å†…å®¹ï¼‰
   - ç‹¬ç‰¹ç‰¹å¾ï¼ˆå£å¤´ç¦…ã€ç‰¹æ®Šç»åŽ†ã€ä¸ªäººçˆ±å¥½ï¼‰
   - ä¸ªäººè®°å¿†ï¼ˆäººè®¾çš„é‡è¦éƒ¨åˆ†ï¼Œè¦ä»‹ç»è¿™ä¸ªä¸ªä½“ä¸Žäº‹ä»¶çš„å…³è”ï¼Œä»¥åŠè¿™ä¸ªä¸ªä½“åœ¨äº‹ä»¶ä¸­çš„å·²æœ‰åŠ¨ä½œä¸Žååº”ï¼‰
3. age: å¹´é¾„æ•°å­—ï¼ˆå¿…é¡»æ˜¯æ•´æ•°ï¼‰
4. gender: æ€§åˆ«ï¼Œå¿…é¡»æ˜¯è‹±æ–‡: "male" æˆ– "female"
5. mbti: MBTIç±»åž‹ï¼ˆå¦‚INTJã€ENFPç­‰ï¼‰
6. country: å›½å®¶ï¼ˆä½¿ç”¨ä¸­æ–‡ï¼Œå¦‚"ä¸­å›½"ï¼‰
7. profession: èŒä¸š
8. interested_topics: æ„Ÿå…´è¶£è¯é¢˜æ•°ç»„

é‡è¦:
- æ‰€æœ‰å­—æ®µå€¼å¿…é¡»æ˜¯å­—ç¬¦ä¸²æˆ–æ•°å­—ï¼Œä¸è¦ä½¿ç”¨æ¢è¡Œç¬¦
- personaå¿…é¡»æ˜¯ä¸€æ®µè¿žè´¯çš„æ–‡å­—æè¿°
- {get_language_instruction()} (genderå­—æ®µå¿…é¡»ç”¨è‹±æ–‡male/female)
- å†…å®¹è¦ä¸Žå®žä½“ä¿¡æ¯ä¿æŒä¸€è‡´
- ageå¿…é¡»æ˜¯æœ‰æ•ˆçš„æ•´æ•°ï¼Œgenderå¿…é¡»æ˜¯"male"æˆ–"female"
"""

    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """æž„å»ºç¾¤ä½“/æœºæž„å®žä½“çš„è¯¦ç»†äººè®¾æç¤ºè¯"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "æ— "
        context_str = context[:3000] if context else "æ— é¢å¤–ä¸Šä¸‹æ–‡"
        
        return f"""ä¸ºæœºæž„/ç¾¤ä½“å®žä½“ç”Ÿæˆè¯¦ç»†çš„ç¤¾äº¤åª’ä½“è´¦å·è®¾å®š,æœ€å¤§ç¨‹åº¦è¿˜åŽŸå·²æœ‰çŽ°å®žæƒ…å†µã€‚

å®žä½“åç§°: {entity_name}
å®žä½“ç±»åž‹: {entity_type}
å®žä½“æ‘˜è¦: {entity_summary}
å®žä½“å±žæ€§: {attrs_str}

ä¸Šä¸‹æ–‡ä¿¡æ¯:
{context_str}

è¯·ç”ŸæˆJSONï¼ŒåŒ…å«ä»¥ä¸‹å­—æ®µ:

1. bio: å®˜æ–¹è´¦å·ç®€ä»‹ï¼Œ200å­—ï¼Œä¸“ä¸šå¾—ä½“
2. persona: è¯¦ç»†è´¦å·è®¾å®šæè¿°ï¼ˆ2000å­—çš„çº¯æ–‡æœ¬ï¼‰ï¼Œéœ€åŒ…å«:
   - æœºæž„åŸºæœ¬ä¿¡æ¯ï¼ˆæ­£å¼åç§°ã€æœºæž„æ€§è´¨ã€æˆç«‹èƒŒæ™¯ã€ä¸»è¦èŒèƒ½ï¼‰
   - è´¦å·å®šä½ï¼ˆè´¦å·ç±»åž‹ã€ç›®æ ‡å—ä¼—ã€æ ¸å¿ƒåŠŸèƒ½ï¼‰
   - å‘è¨€é£Žæ ¼ï¼ˆè¯­è¨€ç‰¹ç‚¹ã€å¸¸ç”¨è¡¨è¾¾ã€ç¦å¿Œè¯é¢˜ï¼‰
   - å‘å¸ƒå†…å®¹ç‰¹ç‚¹ï¼ˆå†…å®¹ç±»åž‹ã€å‘å¸ƒé¢‘çŽ‡ã€æ´»è·ƒæ—¶é—´æ®µï¼‰
   - ç«‹åœºæ€åº¦ï¼ˆå¯¹æ ¸å¿ƒè¯é¢˜çš„å®˜æ–¹ç«‹åœºã€é¢å¯¹äº‰è®®çš„å¤„ç†æ–¹å¼ï¼‰
   - ç‰¹æ®Šè¯´æ˜Žï¼ˆä»£è¡¨çš„ç¾¤ä½“ç”»åƒã€è¿è¥ä¹ æƒ¯ï¼‰
   - æœºæž„è®°å¿†ï¼ˆæœºæž„äººè®¾çš„é‡è¦éƒ¨åˆ†ï¼Œè¦ä»‹ç»è¿™ä¸ªæœºæž„ä¸Žäº‹ä»¶çš„å…³è”ï¼Œä»¥åŠè¿™ä¸ªæœºæž„åœ¨äº‹ä»¶ä¸­çš„å·²æœ‰åŠ¨ä½œä¸Žååº”ï¼‰
3. age: å›ºå®šå¡«30ï¼ˆæœºæž„è´¦å·çš„è™šæ‹Ÿå¹´é¾„ï¼‰
4. gender: å›ºå®šå¡«"other"ï¼ˆæœºæž„è´¦å·ä½¿ç”¨otherè¡¨ç¤ºéžä¸ªäººï¼‰
5. mbti: MBTIç±»åž‹ï¼Œç”¨äºŽæè¿°è´¦å·é£Žæ ¼ï¼Œå¦‚ISTJä»£è¡¨ä¸¥è°¨ä¿å®ˆ
6. country: å›½å®¶ï¼ˆä½¿ç”¨ä¸­æ–‡ï¼Œå¦‚"ä¸­å›½"ï¼‰
7. profession: æœºæž„èŒèƒ½æè¿°
8. interested_topics: å…³æ³¨é¢†åŸŸæ•°ç»„

é‡è¦:
- æ‰€æœ‰å­—æ®µå€¼å¿…é¡»æ˜¯å­—ç¬¦ä¸²æˆ–æ•°å­—ï¼Œä¸å…è®¸nullå€¼
- personaå¿…é¡»æ˜¯ä¸€æ®µè¿žè´¯çš„æ–‡å­—æè¿°ï¼Œä¸è¦ä½¿ç”¨æ¢è¡Œç¬¦
- {get_language_instruction()} (genderå­—æ®µå¿…é¡»ç”¨è‹±æ–‡"other")
- ageå¿…é¡»æ˜¯æ•´æ•°30ï¼Œgenderå¿…é¡»æ˜¯å­—ç¬¦ä¸²"other"
- æœºæž„è´¦å·å‘è¨€è¦ç¬¦åˆå…¶èº«ä»½å®šä½"""
    
    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """ä½¿ç”¨è§„åˆ™ç”ŸæˆåŸºç¡€äººè®¾"""
        
        entity_type_lower = entity_type.lower()
        
        if entity_type_lower in ["student", "alumni"]:
            return {
                "bio": f"{entity_type} with interests in academics and social issues.",
                "persona": f"{entity_name} is a {entity_type.lower()} who is actively engaged in academic and social discussions. They enjoy sharing perspectives and connecting with peers.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "Student",
                "interested_topics": ["Education", "Social Issues", "Technology"],
            }
        
        elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
            return {
                "bio": f"Expert and thought leader in their field.",
                "persona": f"{entity_name} is a recognized {entity_type.lower()} who shares insights and opinions on important matters. They are known for their expertise and influence in public discourse.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "Expert"),
                "interested_topics": ["Politics", "Economics", "Culture & Society"],
            }
        
        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
            return {
                "bio": f"Official account for {entity_name}. News and updates.",
                "persona": f"{entity_name} is a media entity that reports news and facilitates public discourse. The account shares timely updates and engages with the audience on current events.",
                "age": 30,  # æœºæž„è™šæ‹Ÿå¹´é¾„
                "gender": "other",  # æœºæž„ä½¿ç”¨other
                "mbti": "ISTJ",  # æœºæž„é£Žæ ¼ï¼šä¸¥è°¨ä¿å®ˆ
                "country": "ä¸­å›½",
                "profession": "Media",
                "interested_topics": ["General News", "Current Events", "Public Affairs"],
            }
        
        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
            return {
                "bio": f"Official account of {entity_name}.",
                "persona": f"{entity_name} is an institutional entity that communicates official positions, announcements, and engages with stakeholders on relevant matters.",
                "age": 30,  # æœºæž„è™šæ‹Ÿå¹´é¾„
                "gender": "other",  # æœºæž„ä½¿ç”¨other
                "mbti": "ISTJ",  # æœºæž„é£Žæ ¼ï¼šä¸¥è°¨ä¿å®ˆ
                "country": "ä¸­å›½",
                "profession": entity_type,
                "interested_topics": ["Public Policy", "Community", "Official Announcements"],
            }
        
        else:
            return {
                "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
                "persona": entity_summary or f"{entity_name} is a {entity_type.lower()} participating in social discussions.",
                "age": random.randint(25, 50),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_type,
                "interested_topics": ["General", "Social Issues"],
            }
    
    def set_graph_id(self, graph_id: str):
        """è®¾ç½®å›¾è°±IDç”¨äºŽZepæ£€ç´¢"""
        self.graph_id = graph_id
    
    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[callable] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 5,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit"
    ) -> List[OasisAgentProfile]:
        """
        
        Args:
            
        Returns:
        """
        import concurrent.futures
        from threading import Lock
        
        if graph_id:
            self.graph_id = graph_id
        
        total = len(entities)
        profiles = [None] * total  # é¢„åˆ†é…åˆ—è¡¨ä¿æŒé¡ºåº
        completed_count = [0]  # ä½¿ç”¨åˆ—è¡¨ä»¥ä¾¿åœ¨é—­åŒ…ä¸­ä¿®æ”¹
        lock = Lock()
        
        def save_profiles_realtime():
            """å®žæ—¶ä¿å­˜å·²ç”Ÿæˆçš„ profiles åˆ°æ–‡ä»¶"""
            if not realtime_output_path:
                return
            
            with lock:
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return
                
                try:
                    if output_platform == "reddit":
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f"å®žæ—¶ä¿å­˜ profiles å¤±è´¥: {e}")
        
        # Capture locale before spawning thread pool workers
        current_locale = get_locale()

        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            """ç”Ÿæˆå•ä¸ªprofileçš„å·¥ä½œå‡½æ•°"""
            set_locale(current_locale)
            entity_type = entity.get_entity_type() or "Entity"
            
            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )
                
                self._print_generated_profile(entity.name, entity_type, profile)
                
                return idx, profile, None
                
            except Exception as e:
                logger.error(f"ç”Ÿæˆå®žä½“ {entity.name} çš„äººè®¾å¤±è´¥: {str(e)}")
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or f"A participant in social discussions.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)
        
        logger.info(f"å¼€å§‹å¹¶è¡Œç”Ÿæˆ {total} ä¸ªAgentäººè®¾ï¼ˆå¹¶è¡Œæ•°: {parallel_count}ï¼‰...")
        print(f"\n{'='*60}")
        print(f"å¼€å§‹ç”ŸæˆAgentäººè®¾ - å…± {total} ä¸ªå®žä½“ï¼Œå¹¶è¡Œæ•°: {parallel_count}")
        print(f"{'='*60}\n")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }
            
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"
                
                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile
                    
                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]
                    
                    save_profiles_realtime()
                    
                    if progress_callback:
                        progress_callback(
                            current, 
                            total, 
                            f"å·²å®Œæˆ {current}/{total}: {entity.name}ï¼ˆ{entity_type}ï¼‰"
                        )
                    
                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} ä½¿ç”¨å¤‡ç”¨äººè®¾: {error}")
                    else:
                        logger.info(f"[{current}/{total}] æˆåŠŸç”Ÿæˆäººè®¾: {entity.name} ({entity_type})")
                        
                except Exception as e:
                    logger.error(f"å¤„ç†å®žä½“ {entity.name} æ—¶å‘ç”Ÿå¼‚å¸¸: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=self._generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "A participant in social discussions.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    save_profiles_realtime()
        
        print(f"\n{'='*60}")
        print(f"äººè®¾ç”Ÿæˆå®Œæˆï¼å…±ç”Ÿæˆ {len([p for p in profiles if p])} ä¸ªAgent")
        print(f"{'='*60}\n")
        
        return profiles
    
    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """å®žæ—¶è¾“å‡ºç”Ÿæˆçš„äººè®¾åˆ°æŽ§åˆ¶å°ï¼ˆå®Œæ•´å†…å®¹ï¼Œä¸æˆªæ–­ï¼‰"""
        separator = "-" * 70
        
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else 'æ— '
        
        output_lines = [
            f"\n{separator}",
            t('progress.profileGenerated', name=entity_name, type=entity_type),
            f"{separator}",
            f"ç”¨æˆ·å: {profile.user_name}",
            f"",
            f"ã€ç®€ä»‹ã€‘",
            f"{profile.bio}",
            f"",
            f"ã€è¯¦ç»†äººè®¾ã€‘",
            f"{profile.persona}",
            f"",
            f"ã€åŸºæœ¬å±žæ€§ã€‘",
            f"å¹´é¾„: {profile.age} | æ€§åˆ«: {profile.gender} | MBTI: {profile.mbti}",
            f"èŒä¸š: {profile.profession} | å›½å®¶: {profile.country}",
            f"å…´è¶£è¯é¢˜: {topics_str}",
            separator
        ]
        
        output = "\n".join(output_lines)
        
        print(output)
    
    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """
        
        
        Args:
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)
    
    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        
        
        """
        import csv
        
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            headers = ['user_id', 'name', 'username', 'user_char', 'description']
            writer.writerow(headers)
            
            for idx, profile in enumerate(profiles):
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')
                
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')
                
                row = [
                    idx,                    # user_id: ä»Ž0å¼€å§‹çš„é¡ºåºID
                    profile.name,           # name: çœŸå®žå§“å
                    profile.user_name,      # username: ç”¨æˆ·å
                    user_char,              # user_char: å®Œæ•´äººè®¾ï¼ˆå†…éƒ¨LLMä½¿ç”¨ï¼‰
                    description             # description: ç®€çŸ­ç®€ä»‹ï¼ˆå¤–éƒ¨æ˜¾ç¤ºï¼‰
                ]
                writer.writerow(row)
        
        logger.info(f"å·²ä¿å­˜ {len(profiles)} ä¸ªTwitter Profileåˆ° {file_path} (OASIS CSVæ ¼å¼)")
    
    def _normalize_gender(self, gender: Optional[str]) -> str:
        """
        
        """
        if not gender:
            return "other"
        
        gender_lower = gender.lower().strip()
        
        gender_map = {
            "ç”·": "male",
            "å¥³": "female",
            "æœºæž„": "other",
            "å…¶ä»–": "other",
            "male": "male",
            "female": "female",
            "other": "other",
        }
        
        return gender_map.get(gender_lower, "other")
    
    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        
        
        """
        data = []
        for idx, profile in enumerate(profiles):
            item = {
                "user_id": profile.user_id if profile.user_id is not None else idx,  # å…³é”®ï¼šå¿…é¡»åŒ…å« user_id
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:150] if profile.bio else f"{profile.name}",
                "persona": profile.persona or f"{profile.name} is a participant in social discussions.",
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                "age": profile.age if profile.age else 30,
                "gender": self._normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else "ISTJ",
                "country": profile.country if profile.country else "ä¸­å›½",
            }
            
            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics
            
            data.append(item)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"å·²ä¿å­˜ {len(profiles)} ä¸ªReddit Profileåˆ° {file_path} (JSONæ ¼å¼ï¼ŒåŒ…å«user_idå­—æ®µ)")
    
    def save_profiles_to_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """[å·²åºŸå¼ƒ] è¯·ä½¿ç”¨ save_profiles() æ–¹æ³•"""
        logger.warning("save_profiles_to_jsonå·²åºŸå¼ƒï¼Œè¯·ä½¿ç”¨save_profilesæ–¹æ³•")
        self.save_profiles(profiles, file_path, platform)


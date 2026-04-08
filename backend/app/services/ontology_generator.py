"""
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient
from ..utils.locale import get_language_instruction

logger = logging.getLogger(__name__)


def _to_pascal_case(name: str) -> str:
    """å°†ä»»æ„æ ¼å¼çš„åç§°è½¬æ¢ä¸º PascalCaseï¼ˆå¦‚ 'works_for' -> 'WorksFor', 'person' -> 'Person'ï¼‰"""
    parts = re.split(r'[^a-zA-Z0-9]+', name)
    words = []
    for part in parts:
        words.extend(re.sub(r'([a-z])([A-Z])', r'\1_\2', part).split('_'))
    result = ''.join(word.capitalize() for word in words if word)
    return result if result else 'Unknown'


ONTOLOGY_SYSTEM_PROMPT = """ä½ æ˜¯ä¸€ä¸ªä¸“ä¸šçš„çŸ¥è¯†å›¾è°±æœ¬ä½“è®¾è®¡ä¸“å®¶ã€‚ä½ çš„ä»»åŠ¡æ˜¯åˆ†æžç»™å®šçš„æ–‡æœ¬å†…å®¹å’Œæ¨¡æ‹Ÿéœ€æ±‚ï¼Œè®¾è®¡é€‚åˆ**ç¤¾äº¤åª’ä½“èˆ†è®ºæ¨¡æ‹Ÿ**çš„å®žä½“ç±»åž‹å’Œå…³ç³»ç±»åž‹ã€‚

**é‡è¦ï¼šä½ å¿…é¡»è¾“å‡ºæœ‰æ•ˆçš„JSONæ ¼å¼æ•°æ®ï¼Œä¸è¦è¾“å‡ºä»»ä½•å…¶ä»–å†…å®¹ã€‚**


æˆ‘ä»¬æ­£åœ¨æž„å»ºä¸€ä¸ª**ç¤¾äº¤åª’ä½“èˆ†è®ºæ¨¡æ‹Ÿç³»ç»Ÿ**ã€‚åœ¨è¿™ä¸ªç³»ç»Ÿä¸­ï¼š
- æ¯ä¸ªå®žä½“éƒ½æ˜¯ä¸€ä¸ªå¯ä»¥åœ¨ç¤¾äº¤åª’ä½“ä¸Šå‘å£°ã€äº’åŠ¨ã€ä¼ æ’­ä¿¡æ¯çš„"è´¦å·"æˆ–"ä¸»ä½“"
- å®žä½“ä¹‹é—´ä¼šç›¸äº’å½±å“ã€è½¬å‘ã€è¯„è®ºã€å›žåº”
- æˆ‘ä»¬éœ€è¦æ¨¡æ‹Ÿèˆ†è®ºäº‹ä»¶ä¸­å„æ–¹çš„ååº”å’Œä¿¡æ¯ä¼ æ’­è·¯å¾„

å› æ­¤ï¼Œ**å®žä½“å¿…é¡»æ˜¯çŽ°å®žä¸­çœŸå®žå­˜åœ¨çš„ã€å¯ä»¥åœ¨ç¤¾åª’ä¸Šå‘å£°å’Œäº’åŠ¨çš„ä¸»ä½“**ï¼š

**å¯ä»¥æ˜¯**ï¼š
- å…·ä½“çš„ä¸ªäººï¼ˆå…¬ä¼—äººç‰©ã€å½“äº‹äººã€æ„è§é¢†è¢–ã€ä¸“å®¶å­¦è€…ã€æ™®é€šäººï¼‰
- å…¬å¸ã€ä¼ä¸šï¼ˆåŒ…æ‹¬å…¶å®˜æ–¹è´¦å·ï¼‰
- ç»„ç»‡æœºæž„ï¼ˆå¤§å­¦ã€åä¼šã€NGOã€å·¥ä¼šç­‰ï¼‰
- æ”¿åºœéƒ¨é—¨ã€ç›‘ç®¡æœºæž„
- åª’ä½“æœºæž„ï¼ˆæŠ¥çº¸ã€ç”µè§†å°ã€è‡ªåª’ä½“ã€ç½‘ç«™ï¼‰
- ç¤¾äº¤åª’ä½“å¹³å°æœ¬èº«
- ç‰¹å®šç¾¤ä½“ä»£è¡¨ï¼ˆå¦‚æ ¡å‹ä¼šã€ç²‰ä¸å›¢ã€ç»´æƒç¾¤ä½“ç­‰ï¼‰

**ä¸å¯ä»¥æ˜¯**ï¼š
- æŠ½è±¡æ¦‚å¿µï¼ˆå¦‚"èˆ†è®º"ã€"æƒ…ç»ª"ã€"è¶‹åŠ¿"ï¼‰
- ä¸»é¢˜/è¯é¢˜ï¼ˆå¦‚"å­¦æœ¯è¯šä¿¡"ã€"æ•™è‚²æ”¹é©"ï¼‰
- è§‚ç‚¹/æ€åº¦ï¼ˆå¦‚"æ”¯æŒæ–¹"ã€"åå¯¹æ–¹"ï¼‰


è¯·è¾“å‡ºJSONæ ¼å¼ï¼ŒåŒ…å«ä»¥ä¸‹ç»“æž„ï¼š

```json
{
    "entity_types": [
        {
            "name": "å®žä½“ç±»åž‹åç§°ï¼ˆè‹±æ–‡ï¼ŒPascalCaseï¼‰",
            "description": "ç®€çŸ­æè¿°ï¼ˆè‹±æ–‡ï¼Œä¸è¶…è¿‡100å­—ç¬¦ï¼‰",
            "attributes": [
                {
                    "name": "å±žæ€§åï¼ˆè‹±æ–‡ï¼Œsnake_caseï¼‰",
                    "type": "text",
                    "description": "å±žæ€§æè¿°"
                }
            ],
            "examples": ["ç¤ºä¾‹å®žä½“1", "ç¤ºä¾‹å®žä½“2"]
        }
    ],
    "edge_types": [
        {
            "name": "å…³ç³»ç±»åž‹åç§°ï¼ˆè‹±æ–‡ï¼ŒUPPER_SNAKE_CASEï¼‰",
            "description": "ç®€çŸ­æè¿°ï¼ˆè‹±æ–‡ï¼Œä¸è¶…è¿‡100å­—ç¬¦ï¼‰",
            "source_targets": [
                {"source": "æºå®žä½“ç±»åž‹", "target": "ç›®æ ‡å®žä½“ç±»åž‹"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "å¯¹æ–‡æœ¬å†…å®¹çš„ç®€è¦åˆ†æžè¯´æ˜Ž"
}
```



**æ•°é‡è¦æ±‚ï¼šå¿…é¡»æ­£å¥½10ä¸ªå®žä½“ç±»åž‹**

**å±‚æ¬¡ç»“æž„è¦æ±‚ï¼ˆå¿…é¡»åŒæ—¶åŒ…å«å…·ä½“ç±»åž‹å’Œå…œåº•ç±»åž‹ï¼‰**ï¼š

ä½ çš„10ä¸ªå®žä½“ç±»åž‹å¿…é¡»åŒ…å«ä»¥ä¸‹å±‚æ¬¡ï¼š

A. **å…œåº•ç±»åž‹ï¼ˆå¿…é¡»åŒ…å«ï¼Œæ”¾åœ¨åˆ—è¡¨æœ€åŽ2ä¸ªï¼‰**ï¼š
   - `Person`: ä»»ä½•è‡ªç„¶äººä¸ªä½“çš„å…œåº•ç±»åž‹ã€‚å½“ä¸€ä¸ªäººä¸å±žäºŽå…¶ä»–æ›´å…·ä½“çš„äººç‰©ç±»åž‹æ—¶ï¼Œå½’å…¥æ­¤ç±»ã€‚
   - `Organization`: ä»»ä½•ç»„ç»‡æœºæž„çš„å…œåº•ç±»åž‹ã€‚å½“ä¸€ä¸ªç»„ç»‡ä¸å±žäºŽå…¶ä»–æ›´å…·ä½“çš„ç»„ç»‡ç±»åž‹æ—¶ï¼Œå½’å…¥æ­¤ç±»ã€‚

B. **å…·ä½“ç±»åž‹ï¼ˆ8ä¸ªï¼Œæ ¹æ®æ–‡æœ¬å†…å®¹è®¾è®¡ï¼‰**ï¼š
   - é’ˆå¯¹æ–‡æœ¬ä¸­å‡ºçŽ°çš„ä¸»è¦è§’è‰²ï¼Œè®¾è®¡æ›´å…·ä½“çš„ç±»åž‹
   - ä¾‹å¦‚ï¼šå¦‚æžœæ–‡æœ¬æ¶‰åŠå­¦æœ¯äº‹ä»¶ï¼Œå¯ä»¥æœ‰ `Student`, `Professor`, `University`
   - ä¾‹å¦‚ï¼šå¦‚æžœæ–‡æœ¬æ¶‰åŠå•†ä¸šäº‹ä»¶ï¼Œå¯ä»¥æœ‰ `Company`, `CEO`, `Employee`

**ä¸ºä»€ä¹ˆéœ€è¦å…œåº•ç±»åž‹**ï¼š
- æ–‡æœ¬ä¸­ä¼šå‡ºçŽ°å„ç§äººç‰©ï¼Œå¦‚"ä¸­å°å­¦æ•™å¸ˆ"ã€"è·¯äººç”²"ã€"æŸä½ç½‘å‹"
- å¦‚æžœæ²¡æœ‰ä¸“é—¨çš„ç±»åž‹åŒ¹é…ï¼Œä»–ä»¬åº”è¯¥è¢«å½’å…¥ `Person`
- åŒç†ï¼Œå°åž‹ç»„ç»‡ã€ä¸´æ—¶å›¢ä½“ç­‰åº”è¯¥å½’å…¥ `Organization`

**å…·ä½“ç±»åž‹çš„è®¾è®¡åŽŸåˆ™**ï¼š
- ä»Žæ–‡æœ¬ä¸­è¯†åˆ«å‡ºé«˜é¢‘å‡ºçŽ°æˆ–å…³é”®çš„è§’è‰²ç±»åž‹
- æ¯ä¸ªå…·ä½“ç±»åž‹åº”è¯¥æœ‰æ˜Žç¡®çš„è¾¹ç•Œï¼Œé¿å…é‡å 
- description å¿…é¡»æ¸…æ™°è¯´æ˜Žè¿™ä¸ªç±»åž‹å’Œå…œåº•ç±»åž‹çš„åŒºåˆ«


- æ•°é‡ï¼š6-10ä¸ª
- å…³ç³»åº”è¯¥åæ˜ ç¤¾åª’äº’åŠ¨ä¸­çš„çœŸå®žè”ç³»
- ç¡®ä¿å…³ç³»çš„ source_targets æ¶µç›–ä½ å®šä¹‰çš„å®žä½“ç±»åž‹


- æ¯ä¸ªå®žä½“ç±»åž‹1-3ä¸ªå…³é”®å±žæ€§
- **æ³¨æ„**ï¼šå±žæ€§åä¸èƒ½ä½¿ç”¨ `name`ã€`uuid`ã€`group_id`ã€`created_at`ã€`summary`ï¼ˆè¿™äº›æ˜¯ç³»ç»Ÿä¿ç•™å­—ï¼‰
- æŽ¨èä½¿ç”¨ï¼š`full_name`, `title`, `role`, `position`, `location`, `description` ç­‰


**ä¸ªäººç±»ï¼ˆå…·ä½“ï¼‰**ï¼š
- Student: å­¦ç”Ÿ
- Professor: æ•™æŽˆ/å­¦è€…
- Journalist: è®°è€…
- Celebrity: æ˜Žæ˜Ÿ/ç½‘çº¢
- Executive: é«˜ç®¡
- Official: æ”¿åºœå®˜å‘˜
- Lawyer: å¾‹å¸ˆ
- Doctor: åŒ»ç”Ÿ

**ä¸ªäººç±»ï¼ˆå…œåº•ï¼‰**ï¼š
- Person: ä»»ä½•è‡ªç„¶äººï¼ˆä¸å±žäºŽä¸Šè¿°å…·ä½“ç±»åž‹æ—¶ä½¿ç”¨ï¼‰

**ç»„ç»‡ç±»ï¼ˆå…·ä½“ï¼‰**ï¼š
- University: é«˜æ ¡
- Company: å…¬å¸ä¼ä¸š
- GovernmentAgency: æ”¿åºœæœºæž„
- MediaOutlet: åª’ä½“æœºæž„
- Hospital: åŒ»é™¢
- School: ä¸­å°å­¦
- NGO: éžæ”¿åºœç»„ç»‡

**ç»„ç»‡ç±»ï¼ˆå…œåº•ï¼‰**ï¼š
- Organization: ä»»ä½•ç»„ç»‡æœºæž„ï¼ˆä¸å±žäºŽä¸Šè¿°å…·ä½“ç±»åž‹æ—¶ä½¿ç”¨ï¼‰


- WORKS_FOR: å·¥ä½œäºŽ
- STUDIES_AT: å°±è¯»äºŽ
- AFFILIATED_WITH: éš¶å±žäºŽ
- REPRESENTS: ä»£è¡¨
- REGULATES: ç›‘ç®¡
- REPORTS_ON: æŠ¥é“
- COMMENTS_ON: è¯„è®º
- RESPONDS_TO: å›žåº”
- SUPPORTS: æ”¯æŒ
- OPPOSES: åå¯¹
- COLLABORATES_WITH: åˆä½œ
- COMPETES_WITH: ç«žäº‰
"""


class OntologyGenerator:
    """
    æœ¬ä½“ç”Ÿæˆå™¨
    åˆ†æžæ–‡æœ¬å†…å®¹ï¼Œç”Ÿæˆå®žä½“å’Œå…³ç³»ç±»åž‹å®šä¹‰
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ç”Ÿæˆæœ¬ä½“å®šä¹‰
        
        Args:
            document_texts: æ–‡æ¡£æ–‡æœ¬åˆ—è¡¨
            simulation_requirement: æ¨¡æ‹Ÿéœ€æ±‚æè¿°
            additional_context: é¢å¤–ä¸Šä¸‹æ–‡
            
        Returns:
            æœ¬ä½“å®šä¹‰ï¼ˆentity_types, edge_typesç­‰ï¼‰
        """
        user_message = self._build_user_message(
            document_texts, 
            simulation_requirement,
            additional_context
        )
        
        lang_instruction = get_language_instruction()
        system_prompt = f"{ONTOLOGY_SYSTEM_PROMPT}\n\n{lang_instruction}\nIMPORTANT: Entity type names MUST be in English PascalCase (e.g., 'PersonEntity', 'MediaOrganization'). Relationship type names MUST be in English UPPER_SNAKE_CASE (e.g., 'WORKS_FOR'). Attribute names MUST be in English snake_case. Only description fields and analysis_summary should use the specified language above."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )
        
        result = self._validate_and_process(result)
        
        return result
    
    MAX_TEXT_LENGTH_FOR_LLM = 50000
    
    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """æž„å»ºç”¨æˆ·æ¶ˆæ¯"""
        
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)
        
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(åŽŸæ–‡å…±{original_length}å­—ï¼Œå·²æˆªå–å‰{self.MAX_TEXT_LENGTH_FOR_LLM}å­—ç”¨äºŽæœ¬ä½“åˆ†æž)..."
        
        message = f"""## æ¨¡æ‹Ÿéœ€æ±‚

{simulation_requirement}


{combined_text}
"""
        
        if additional_context:
            message += f"""

{additional_context}
"""
        
        message += """
è¯·æ ¹æ®ä»¥ä¸Šå†…å®¹ï¼Œè®¾è®¡é€‚åˆç¤¾ä¼šèˆ†è®ºæ¨¡æ‹Ÿçš„å®žä½“ç±»åž‹å’Œå…³ç³»ç±»åž‹ã€‚

**å¿…é¡»éµå®ˆçš„è§„åˆ™**ï¼š
1. å¿…é¡»æ­£å¥½è¾“å‡º10ä¸ªå®žä½“ç±»åž‹
2. æœ€åŽ2ä¸ªå¿…é¡»æ˜¯å…œåº•ç±»åž‹ï¼šPersonï¼ˆä¸ªäººå…œåº•ï¼‰å’Œ Organizationï¼ˆç»„ç»‡å…œåº•ï¼‰
3. å‰8ä¸ªæ˜¯æ ¹æ®æ–‡æœ¬å†…å®¹è®¾è®¡çš„å…·ä½“ç±»åž‹
4. æ‰€æœ‰å®žä½“ç±»åž‹å¿…é¡»æ˜¯çŽ°å®žä¸­å¯ä»¥å‘å£°çš„ä¸»ä½“ï¼Œä¸èƒ½æ˜¯æŠ½è±¡æ¦‚å¿µ
5. å±žæ€§åä¸èƒ½ä½¿ç”¨ nameã€uuidã€group_id ç­‰ä¿ç•™å­—ï¼Œç”¨ full_nameã€org_name ç­‰æ›¿ä»£
"""
        
        return message
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """éªŒè¯å’ŒåŽå¤„ç†ç»“æžœ"""
        
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""
        
        entity_name_map = {}
        for entity in result["entity_types"]:
            if "name" in entity:
                original_name = entity["name"]
                entity["name"] = _to_pascal_case(original_name)
                if entity["name"] != original_name:
                    logger.warning(f"Entity type name '{original_name}' auto-converted to '{entity['name']}'")
                entity_name_map[original_name] = entity["name"]
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."
        
        for edge in result["edge_types"]:
            if "name" in edge:
                original_name = edge["name"]
                edge["name"] = original_name.upper()
                if edge["name"] != original_name:
                    logger.warning(f"Edge type name '{original_name}' auto-converted to '{edge['name']}'")
            for st in edge.get("source_targets", []):
                if st.get("source") in entity_name_map:
                    st["source"] = entity_name_map[st["source"]]
                if st.get("target") in entity_name_map:
                    st["target"] = entity_name_map[st["target"]]
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
        
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10

        seen_names = set()
        deduped = []
        for entity in result["entity_types"]:
            name = entity.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                deduped.append(entity)
            elif name in seen_names:
                logger.warning(f"Duplicate entity type '{name}' removed during validation")
        result["entity_types"] = deduped

        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }
        
        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }
        
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names
        
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)
        
        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)
            
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                result["entity_types"] = result["entity_types"][:-to_remove]
            
            result["entity_types"].extend(fallbacks_to_add)
        
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]
        
        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]
        
        return result
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        
        Args:
            
        Returns:
        """
        code_lines = [
            '"""',
            'è‡ªå®šä¹‰å®žä½“ç±»åž‹å®šä¹‰',
            'ç”±Posiedonè‡ªåŠ¨ç”Ÿæˆï¼Œç”¨äºŽç¤¾ä¼šèˆ†è®ºæ¨¡æ‹Ÿ',
            '"""',
            '',
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
            '',
            '# ============== å®žä½“ç±»åž‹å®šä¹‰ ==============',
            '',
        ]
        
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")
            
            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== å…³ç³»ç±»åž‹å®šä¹‰ ==============')
        code_lines.append('')
        
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")
            
            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== ç±»åž‹é…ç½® ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')
        
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)


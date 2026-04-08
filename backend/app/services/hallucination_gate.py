"""
Hallucination Gate Service

This module provides a validation layer that checks agent outputs against
the knowledge graph before committing them. It extracts entities and claims
from agent responses and validates them against known graph nodes.

Features:
- Entity extraction from agent outputs
- Cross-reference validation against knowledge graph
- Retry mechanism with grounded fallback
- Hallucination scoring for quality tracking
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import IntEnum

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient

logger = get_logger('posiedon.hallucination_gate')


class HallucinationScore(IntEnum):
    """Hallucination validation scores for action records"""
    CLEAN = 0           # No hallucination detected - passed first validation
    CORRECTED = 1       # Hallucination detected and corrected via retry
    FORCED_FALLBACK = 2 # Max retries exceeded, forced to grounded fallback


@dataclass
class EntityReference:
    """An entity mentioned in agent output"""
    name: str
    context: str  # The surrounding text where entity was mentioned
    entity_type: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of hallucination validation"""
    is_valid: bool
    score: HallucinationScore
    original_output: str
    validated_output: str
    ungrounded_entities: List[str] = field(default_factory=list)
    retry_count: int = 0
    fallback_used: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "hallucination_score": self.score.value,
            "ungrounded_entities": self.ungrounded_entities,
            "retry_count": self.retry_count,
            "fallback_used": self.fallback_used,
        }


class HallucinationGate:
    """
    Validates agent outputs against the knowledge graph to prevent hallucinations.
    
    The gate extracts named entities from agent outputs and cross-references them
    against nodes in the knowledge graph. If any entity is not found, the output
    is rejected and the agent is re-prompted.
    
    Usage:
        gate = HallucinationGate(graph_nodes, graph_edges)
        result = gate.validate_and_correct(agent_output, agent_reprompt_func)
    """
    
    MAX_RETRIES = 2
    
    ENTITY_EXTRACTION_PROMPT = """You are an entity extraction system. Extract all named entities (people, places, organizations, events, concepts) from the following text.

Text: {text}

Return a JSON object with this structure:
{{
    "entities": [
        {{"name": "Entity Name", "type": "PERSON/PLACE/ORG/EVENT/CONCEPT", "context": "brief surrounding text"}}
    ]
}}

Only include specific named entities, not generic nouns. Be precise with names."""

    GROUNDED_FALLBACK_PROMPT = """You made a claim about entities that don't exist in the knowledge base.

Your original response: {original_output}

Ungrounded entities (not in knowledge base): {ungrounded_entities}

Available entities in the knowledge base:
{available_entities}

Please revise your response using ONLY information about entities that exist in the knowledge base above. 
Do not reference {ungrounded_entities}.

Revised response:"""

    def __init__(
        self,
        graph_nodes: List[Dict[str, Any]],
        graph_edges: List[Dict[str, Any]],
        llm_client: Optional[LLMClient] = None,
        fuzzy_match_threshold: float = 0.85
    ):
        """
        Initialize the hallucination gate.
        
        Args:
            graph_nodes: List of node dictionaries from the knowledge graph
            graph_edges: List of edge dictionaries from the knowledge graph
            llm_client: LLM client for entity extraction (optional, uses default if not provided)
            fuzzy_match_threshold: Similarity threshold for fuzzy entity matching
        """
        self.graph_nodes = graph_nodes
        self.graph_edges = graph_edges
        self.llm_client = llm_client or LLMClient()
        self.fuzzy_match_threshold = fuzzy_match_threshold
        
        # Build entity name index for fast lookup
        self._entity_names: Set[str] = set()
        self._entity_name_lower: Dict[str, str] = {}  # lowercase -> original
        self._build_entity_index()
        
        logger.info(f"HallucinationGate initialized with {len(self._entity_names)} known entities")
    
    def _build_entity_index(self):
        """Build an index of known entity names from the graph."""
        for node in self.graph_nodes:
            name = node.get("name", "")
            if name:
                self._entity_names.add(name)
                self._entity_name_lower[name.lower()] = name
                
            # Also index attribute values that might be names
            attributes = node.get("attributes", {})
            for attr_value in attributes.values():
                if isinstance(attr_value, str) and len(attr_value) > 2:
                    self._entity_names.add(attr_value)
                    self._entity_name_lower[attr_value.lower()] = attr_value
    
    def _extract_entities(self, text: str) -> List[EntityReference]:
        """
        Extract named entities from text using LLM.
        
        Args:
            text: The text to extract entities from
            
        Returns:
            List of EntityReference objects
        """
        if not text or len(text.strip()) < 10:
            return []
        
        try:
            prompt = self.ENTITY_EXTRACTION_PROMPT.format(text=text[:2000])  # Limit length
            
            response = self.llm_client.chat_json([
                {"role": "system", "content": "You extract named entities from text and return JSON."},
                {"role": "user", "content": prompt}
            ], temperature=0.1)
            
            entities = []
            for entity_data in response.get("entities", []):
                entities.append(EntityReference(
                    name=entity_data.get("name", ""),
                    context=entity_data.get("context", ""),
                    entity_type=entity_data.get("type")
                ))
            
            return entities
            
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            # Fallback: simple regex-based extraction
            return self._extract_entities_regex(text)
    
    def _extract_entities_regex(self, text: str) -> List[EntityReference]:
        """
        Fallback entity extraction using regex patterns.
        
        Looks for capitalized words that might be names.
        """
        entities = []
        
        # Match sequences of capitalized words (potential names)
        pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        matches = re.findall(pattern, text)
        
        for match in matches:
            if len(match) > 2 and match.lower() not in {'the', 'this', 'that', 'these', 'those'}:
                entities.append(EntityReference(name=match, context=""))
        
        return entities
    
    def _normalize_name(self, name: str) -> str:
        """Normalize an entity name for comparison."""
        return name.lower().strip()
    
    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate string similarity between two names.
        
        Uses a simple Jaccard similarity on character n-grams.
        """
        def get_ngrams(s: str, n: int = 2) -> Set[str]:
            s = s.lower()
            return set(s[i:i+n] for i in range(len(s) - n + 1))
        
        ngrams1 = get_ngrams(name1)
        ngrams2 = get_ngrams(name2)
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)
        
        return intersection / union if union > 0 else 0.0
    
    def _is_entity_grounded(self, entity_name: str) -> Tuple[bool, Optional[str]]:
        """
        Check if an entity name exists in the knowledge graph.
        
        Args:
            entity_name: The entity name to check
            
        Returns:
            Tuple of (is_grounded, matched_entity_name or None)
        """
        normalized = self._normalize_name(entity_name)
        
        # Exact match (case-insensitive)
        if normalized in self._entity_name_lower:
            return True, self._entity_name_lower[normalized]
        
        # Fuzzy match
        best_match = None
        best_score = 0.0
        
        for known_name in self._entity_names:
            score = self._calculate_similarity(entity_name, known_name)
            if score > best_score and score >= self.fuzzy_match_threshold:
                best_score = score
                best_match = known_name
        
        if best_match:
            return True, best_match
        
        return False, None
    
    def validate_output(self, agent_output: str) -> Tuple[bool, List[str]]:
        """
        Validate that all entities in agent output are grounded in the knowledge graph.
        
        Args:
            agent_output: The agent's response text
            
        Returns:
            Tuple of (is_valid, list of ungrounded entity names)
        """
        entities = self._extract_entities(agent_output)
        
        ungrounded = []
        for entity in entities:
            is_grounded, _ = self._is_entity_grounded(entity.name)
            if not is_grounded:
                ungrounded.append(entity.name)
        
        return len(ungrounded) == 0, ungrounded
    
    def _get_available_entities_sample(self, limit: int = 20) -> str:
        """Get a sample of available entity names for the fallback prompt."""
        sample = list(self._entity_names)[:limit]
        return ", ".join(sample)
    
    def _generate_grounded_fallback(
        self,
        original_output: str,
        ungrounded_entities: List[str]
    ) -> str:
        """
        Generate a grounded fallback response that doesn't reference ungrounded entities.
        
        Args:
            original_output: The original agent output
            ungrounded_entities: List of entity names not in the knowledge graph
            
        Returns:
            A revised, grounded response
        """
        try:
            prompt = self.GROUNDED_FALLBACK_PROMPT.format(
                original_output=original_output[:1000],
                ungrounded_entities=", ".join(ungrounded_entities),
                available_entities=self._get_available_entities_sample(30)
            )
            
            response = self.llm_client.chat([
                {"role": "system", "content": "You are a helpful assistant that only references known entities."},
                {"role": "user", "content": prompt}
            ], temperature=0.3)
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to generate grounded fallback: {e}")
            # Ultimate fallback: return a generic safe response
            return "I can only discuss entities that exist in the knowledge base."
    
    def validate_and_correct(
        self,
        agent_output: str,
        reprompt_func: Optional[callable] = None,
        agent_context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate agent output and correct if needed.
        
        This is the main entry point for the hallucination gate. It:
        1. Extracts entities from the output
        2. Validates them against the knowledge graph
        3. If invalid, retries with a correction prompt (up to MAX_RETRIES)
        4. If still invalid, generates a grounded fallback
        
        Args:
            agent_output: The agent's response to validate
            reprompt_func: Optional function to re-prompt the agent with a correction message.
                          Signature: reprompt_func(correction_message: str) -> str
            agent_context: Optional context about the agent (for logging)
            
        Returns:
            ValidationResult with the validated/corrected output
        """
        original_output = agent_output
        current_output = agent_output
        retry_count = 0
        
        # First validation
        is_valid, ungrounded = self.validate_output(current_output)
        
        if is_valid:
            logger.debug("Output passed hallucination check on first try")
            return ValidationResult(
                is_valid=True,
                score=HallucinationScore.CLEAN,
                original_output=original_output,
                validated_output=current_output,
                ungrounded_entities=[],
                retry_count=0,
                fallback_used=False
            )
        
        # Try to correct via reprompting
        while not is_valid and retry_count < self.MAX_RETRIES and reprompt_func:
            retry_count += 1
            
            correction_message = (
                f"Your response references entities that are not in the knowledge base: "
                f"{', '.join(ungrounded)}. "
                f"Please revise using only information from the graph."
            )
            
            logger.info(f"Hallucination detected, retry {retry_count}/{self.MAX_RETRIES}: "
                       f"ungrounded entities: {ungrounded}")
            
            try:
                current_output = reprompt_func(correction_message)
                is_valid, ungrounded = self.validate_output(current_output)
            except Exception as e:
                logger.warning(f"Reprompt failed: {e}")
                break
        
        if is_valid:
            logger.info(f"Output corrected after {retry_count} retries")
            return ValidationResult(
                is_valid=True,
                score=HallucinationScore.CORRECTED,
                original_output=original_output,
                validated_output=current_output,
                ungrounded_entities=[],
                retry_count=retry_count,
                fallback_used=False
            )
        
        # Max retries exceeded, use grounded fallback
        logger.warning(f"Max retries exceeded, generating grounded fallback. "
                      f"Ungrounded entities: {ungrounded}")
        
        fallback_output = self._generate_grounded_fallback(original_output, ungrounded)
        
        return ValidationResult(
            is_valid=True,  # Fallback is always "valid" (grounded)
            score=HallucinationScore.FORCED_FALLBACK,
            original_output=original_output,
            validated_output=fallback_output,
            ungrounded_entities=ungrounded,
            retry_count=retry_count,
            fallback_used=True
        )
    
    def add_hallucination_score_to_action(
        self,
        action_dict: Dict[str, Any],
        validation_result: ValidationResult
    ) -> Dict[str, Any]:
        """
        Add hallucination score field to an action dictionary.
        
        This is used to annotate action records in actions.jsonl.
        
        Args:
            action_dict: The action record dictionary
            validation_result: The validation result
            
        Returns:
            The action dict with hallucination_score added
        """
        action_dict["hallucination_score"] = validation_result.score.value
        
        if validation_result.fallback_used:
            action_dict["hallucination_fallback"] = True
            action_dict["original_content"] = validation_result.original_output
        
        return action_dict


def create_hallucination_gate_from_zep(
    graph_id: str,
    zep_api_key: Optional[str] = None
) -> HallucinationGate:
    """
    Factory function to create a HallucinationGate from a Zep graph.
    
    Args:
        graph_id: The Zep graph ID
        zep_api_key: Optional Zep API key (uses config if not provided)
        
    Returns:
        Configured HallucinationGate instance
    """
    from .zep_entity_reader import ZepEntityReader
    
    reader = ZepEntityReader(api_key=zep_api_key)
    nodes = reader.get_all_nodes(graph_id)
    edges = reader.get_all_edges(graph_id)
    
    return HallucinationGate(graph_nodes=nodes, graph_edges=edges)

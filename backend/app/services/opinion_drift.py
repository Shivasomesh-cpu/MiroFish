"""
Opinion Drift Service

Implements dynamic opinion evolution for Posiedon agents.
After each simulation round, agents' opinions update based on their social exposure.

Key concepts:
- opinion_state: Maps topics to opinion values [-1.0 to 1.0]
- susceptibility: How easily an agent's opinions change (0.0-1.0)
- exposure: Content the agent was exposed to (posts seen, replies received)
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('posiedon.opinion_drift')


@dataclass
class ExposureItem:
    """A piece of content an agent was exposed to."""
    content: str
    source_agent_id: str
    action_type: str  # CREATE_POST, REPLY, QUOTE, etc.
    timestamp: str
    platform: str


@dataclass
class StanceAnalysis:
    """Analysis of stance/sentiment on a topic."""
    topic: str
    stance: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0


class OpinionDriftProcessor:
    """
    Processes opinion drift for agents after each simulation round.
    
    Algorithm:
    1. Collect all content the agent was exposed to during the round
    2. Extract sentiment/stance on each topic from the exposure
    3. Compute weighted average: 
       new_opinion = (1 - susceptibility) * current_opinion + susceptibility * exposure_average
    4. Update agent's opinion_state and record in opinion_history
    """
    
    # Default topics to track if none specified
    DEFAULT_TOPICS = [
        "general_sentiment",  # Overall positive/negative sentiment
    ]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        topics: Optional[List[str]] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        # Use a faster/cheaper model for stance analysis
        self.model_name = model_name or Config.LLM_MODEL_NAME
        
        self.topics = topics or self.DEFAULT_TOPICS
        
        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        else:
            self.client = None
            logger.warning("No LLM API key configured - using heuristic stance analysis")
    
    def collect_agent_exposure(
        self,
        agent_id: str,
        actions: List[Dict[str, Any]],
        round_number: int
    ) -> List[ExposureItem]:
        """
        Collect all content an agent was exposed to during a round.
        
        Exposure includes:
        - Posts the agent saw (in their feed)
        - Replies they received
        - Content they interacted with (liked, reposted, quoted)
        """
        exposure = []
        
        for action in actions:
            if action.get('round', action.get('round_num', 0)) != round_number:
                continue
            
            action_type = action.get('action_type', '')
            action_args = action.get('action_args', {})
            acting_agent = action.get('agent_id', '')
            
            # Exposure from seeing others' posts (simplified - in reality would track feed)
            if acting_agent != agent_id:
                # If someone created a post, the agent may have seen it
                if action_type == 'CREATE_POST' and action_args.get('content'):
                    exposure.append(ExposureItem(
                        content=action_args['content'],
                        source_agent_id=acting_agent,
                        action_type=action_type,
                        timestamp=action.get('timestamp', ''),
                        platform=action.get('platform', 'unknown')
                    ))
                
                # If someone replied to this agent's content
                if action_type in ['CREATE_COMMENT', 'REPLY']:
                    target_author = action_args.get('post_author_id') or action_args.get('parent_author_id')
                    if target_author == agent_id and action_args.get('content'):
                        exposure.append(ExposureItem(
                            content=action_args['content'],
                            source_agent_id=acting_agent,
                            action_type=action_type,
                            timestamp=action.get('timestamp', ''),
                            platform=action.get('platform', 'unknown')
                        ))
                
                # Quotes of this agent's posts
                if action_type == 'QUOTE_POST':
                    original_author = action_args.get('original_author_id')
                    if original_author == agent_id:
                        quote_content = action_args.get('quote_content', '')
                        if quote_content:
                            exposure.append(ExposureItem(
                                content=quote_content,
                                source_agent_id=acting_agent,
                                action_type=action_type,
                                timestamp=action.get('timestamp', ''),
                                platform=action.get('platform', 'unknown')
                            ))
            
            # Content the agent actively engaged with
            if acting_agent == agent_id:
                # Posts they liked - they were exposed to the content
                if action_type == 'LIKE_POST' and action_args.get('post_content'):
                    exposure.append(ExposureItem(
                        content=action_args['post_content'],
                        source_agent_id=action_args.get('post_author_id', 'unknown'),
                        action_type='VIEWED',  # Mark as viewed
                        timestamp=action.get('timestamp', ''),
                        platform=action.get('platform', 'unknown')
                    ))
                
                # Posts they reposted
                if action_type == 'REPOST' and action_args.get('original_content'):
                    exposure.append(ExposureItem(
                        content=action_args['original_content'],
                        source_agent_id=action_args.get('original_author_id', 'unknown'),
                        action_type='VIEWED',
                        timestamp=action.get('timestamp', ''),
                        platform=action.get('platform', 'unknown')
                    ))
        
        return exposure
    
    def analyze_stance_llm(
        self,
        content: str,
        topics: List[str]
    ) -> List[StanceAnalysis]:
        """
        Use LLM to analyze stance on topics from content.
        """
        if not self.client:
            return self._analyze_stance_heuristic(content, topics)
        
        try:
            prompt = f"""Analyze the following social media content and determine the stance on each topic.

Content: "{content}"

Topics to analyze:
{chr(10).join(f'- {topic}' for topic in topics)}

For each topic, provide:
- stance: a value from -1.0 (strongly against/negative) to 1.0 (strongly for/positive), 0 = neutral
- confidence: how confident you are in this assessment (0.0 to 1.0)

If the content doesn't relate to a topic, use stance=0 and confidence=0.1

Respond in JSON format:
{{"analyses": [{{"topic": "topic_name", "stance": 0.5, "confidence": 0.8}}, ...]}}
"""
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing sentiment and stance in social media content. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                analyses = []
                for item in result.get('analyses', []):
                    analyses.append(StanceAnalysis(
                        topic=item['topic'],
                        stance=max(-1.0, min(1.0, float(item['stance']))),
                        confidence=max(0.0, min(1.0, float(item['confidence'])))
                    ))
                return analyses
            
        except Exception as e:
            logger.warning(f"LLM stance analysis failed: {e}, falling back to heuristic")
        
        return self._analyze_stance_heuristic(content, topics)
    
    def _analyze_stance_heuristic(
        self,
        content: str,
        topics: List[str]
    ) -> List[StanceAnalysis]:
        """
        Simple heuristic stance analysis using keyword matching.
        """
        analyses = []
        content_lower = content.lower()
        
        # Simple sentiment keywords
        positive_words = {'good', 'great', 'excellent', 'love', 'support', 'agree', 'yes', 'right', 'true', 'best', 'amazing', 'wonderful', 'positive', 'helpful', 'beneficial'}
        negative_words = {'bad', 'terrible', 'hate', 'oppose', 'disagree', 'no', 'wrong', 'false', 'worst', 'awful', 'negative', 'harmful', 'dangerous'}
        
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)
        
        total = positive_count + negative_count
        if total > 0:
            base_stance = (positive_count - negative_count) / total
            confidence = min(0.7, total * 0.1)  # More words = more confidence, cap at 0.7
        else:
            base_stance = 0.0
            confidence = 0.1
        
        for topic in topics:
            # Check if topic is mentioned
            topic_lower = topic.lower().replace('_', ' ')
            topic_mentioned = topic_lower in content_lower or any(word in content_lower for word in topic_lower.split())
            
            if topic == 'general_sentiment':
                analyses.append(StanceAnalysis(
                    topic=topic,
                    stance=base_stance,
                    confidence=confidence
                ))
            elif topic_mentioned:
                analyses.append(StanceAnalysis(
                    topic=topic,
                    stance=base_stance,
                    confidence=confidence * 1.2  # Boost confidence if topic mentioned
                ))
            else:
                analyses.append(StanceAnalysis(
                    topic=topic,
                    stance=0.0,
                    confidence=0.1
                ))
        
        return analyses
    
    def compute_exposure_average(
        self,
        exposure_items: List[ExposureItem],
        topics: List[str]
    ) -> Dict[str, Tuple[float, float]]:
        """
        Compute weighted average stance across all exposure items.
        
        Returns: Dict mapping topic -> (average_stance, total_weight)
        """
        topic_stances: Dict[str, List[Tuple[float, float]]] = {t: [] for t in topics}
        
        for item in exposure_items:
            analyses = self.analyze_stance_llm(item.content, topics)
            
            for analysis in analyses:
                if analysis.topic in topic_stances:
                    topic_stances[analysis.topic].append((analysis.stance, analysis.confidence))
        
        result = {}
        for topic, stance_list in topic_stances.items():
            if not stance_list:
                result[topic] = (0.0, 0.0)
                continue
            
            total_weight = sum(conf for _, conf in stance_list)
            if total_weight > 0:
                weighted_sum = sum(stance * conf for stance, conf in stance_list)
                avg_stance = weighted_sum / total_weight
            else:
                avg_stance = 0.0
            
            result[topic] = (avg_stance, total_weight)
        
        return result
    
    def update_agent_opinions(
        self,
        agent_profile: Dict[str, Any],
        exposure_items: List[ExposureItem],
        round_number: int,
        topics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Update an agent's opinions based on their exposure.
        
        Algorithm:
        new_opinion = (1 - susceptibility) * current_opinion + susceptibility * exposure_average
        
        Returns: Updated agent profile dict
        """
        topics = topics or self.topics
        susceptibility = agent_profile.get('susceptibility', 0.5)
        current_opinions = agent_profile.get('opinion_state', {})
        opinion_history = agent_profile.get('opinion_history', [])
        
        if not exposure_items:
            logger.debug(f"No exposure for agent, skipping opinion update")
            return agent_profile
        
        # Compute exposure average
        exposure_averages = self.compute_exposure_average(exposure_items, topics)
        
        # Update opinions
        new_opinions = dict(current_opinions)
        for topic in topics:
            current_value = current_opinions.get(topic, 0.0)
            exposure_avg, exposure_weight = exposure_averages.get(topic, (0.0, 0.0))
            
            if exposure_weight > 0:
                # Weighted update based on susceptibility
                new_value = (1 - susceptibility) * current_value + susceptibility * exposure_avg
                new_value = max(-1.0, min(1.0, new_value))
                
                new_opinions[topic] = new_value
                
                # Record in history
                opinion_history.append({
                    "round": round_number,
                    "topic": topic,
                    "value": new_value,
                    "previous_value": current_value,
                    "exposure_avg": exposure_avg,
                    "exposure_weight": exposure_weight
                })
                
                logger.debug(f"Agent opinion updated: {topic} {current_value:.3f} -> {new_value:.3f} (exposure: {exposure_avg:.3f}, weight: {exposure_weight:.2f})")
        
        # Update profile
        agent_profile['opinion_state'] = new_opinions
        agent_profile['opinion_history'] = opinion_history
        
        return agent_profile
    
    def process_round(
        self,
        agent_profiles: List[Dict[str, Any]],
        actions: List[Dict[str, Any]],
        round_number: int,
        topics: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Process opinion drift for all agents after a round.
        
        Args:
            agent_profiles: List of agent profile dicts
            actions: List of all actions from the round
            round_number: Current round number
            topics: Topics to track (uses default if not specified)
        
        Returns: Updated list of agent profiles
        """
        topics = topics or self.topics
        updated_profiles = []
        
        for profile in agent_profiles:
            agent_id = profile.get('user_id') or profile.get('agent_id')
            if not agent_id:
                updated_profiles.append(profile)
                continue
            
            # Collect exposure
            exposure = self.collect_agent_exposure(str(agent_id), actions, round_number)
            
            # Update opinions
            updated_profile = self.update_agent_opinions(
                profile, 
                exposure, 
                round_number,
                topics
            )
            
            updated_profiles.append(updated_profile)
        
        logger.info(f"Processed opinion drift for {len(updated_profiles)} agents in round {round_number}")
        return updated_profiles


def extract_topics_from_seed(seed_content: str, max_topics: int = 5) -> List[str]:
    """
    Extract key topics from seed document for opinion tracking.
    
    Uses simple keyword extraction if no LLM available.
    """
    # Simple extraction: look for capitalized phrases and common topic patterns
    topics = ['general_sentiment']
    
    # Extract capitalized words/phrases (likely proper nouns/topics)
    words = seed_content.split()
    for word in words:
        clean_word = word.strip('.,!?()[]{}":;')
        if clean_word and clean_word[0].isupper() and len(clean_word) > 3:
            topic = clean_word.lower().replace(' ', '_')
            if topic not in topics:
                topics.append(topic)
                if len(topics) >= max_topics:
                    break
    
    return topics[:max_topics]

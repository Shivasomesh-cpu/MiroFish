"""
OASISæ¨¡æ‹Ÿç®¡ç†å™¨
ç®¡ç†Twitterå’ŒRedditåŒå¹³å°å¹¶è¡Œæ¨¡æ‹Ÿ
ä½¿ç”¨é¢„è®¾è„šæœ¬ + LLMæ™ºèƒ½ç”Ÿæˆé…ç½®å‚æ•°
"""

import os
import json
import shutil
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.logger import get_logger
from .zep_entity_reader import ZepEntityReader, FilteredEntities
from .oasis_profile_generator import OasisProfileGenerator, OasisAgentProfile
from .simulation_config_generator import SimulationConfigGenerator, SimulationParameters
from ..utils.locale import t

logger = get_logger('posiedon.simulation')


class SimulationStatus(str, Enum):
    """æ¨¡æ‹ŸçŠ¶æ€"""
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"      # æ¨¡æ‹Ÿè¢«æ‰‹åŠ¨åœæ­¢
    COMPLETED = "completed"  # æ¨¡æ‹Ÿè‡ªç„¶å®Œæˆ
    FAILED = "failed"


class PlatformType(str, Enum):
    """å¹³å°ç±»åž‹"""
    TWITTER = "twitter"
    REDDIT = "reddit"


@dataclass
class SimulationState:
    """æ¨¡æ‹ŸçŠ¶æ€"""
    simulation_id: str
    project_id: str
    graph_id: str
    
    # å¹³å°å¯ç”¨çŠ¶æ€
    enable_twitter: bool = True
    enable_reddit: bool = True
    
    # çŠ¶æ€
    status: SimulationStatus = SimulationStatus.CREATED
    
    # å‡†å¤‡é˜¶æ®µæ•°æ®
    entities_count: int = 0
    profiles_count: int = 0
    entity_types: List[str] = field(default_factory=list)
    
    # é…ç½®ç”Ÿæˆä¿¡æ¯
    config_generated: bool = False
    config_reasoning: str = ""
    
    # è¿è¡Œæ—¶æ•°æ®
    current_round: int = 0
    twitter_status: str = "not_started"
    reddit_status: str = "not_started"
    
    # æ—¶é—´æˆ³
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # é”™è¯¯ä¿¡æ¯
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """å®Œæ•´çŠ¶æ€å­—å…¸ï¼ˆå†…éƒ¨ä½¿ç”¨ï¼‰"""
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "enable_twitter": self.enable_twitter,
            "enable_reddit": self.enable_reddit,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "config_generated": self.config_generated,
            "config_reasoning": self.config_reasoning,
            "current_round": self.current_round,
            "twitter_status": self.twitter_status,
            "reddit_status": self.reddit_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }
    
    def to_simple_dict(self) -> Dict[str, Any]:
        """ç®€åŒ–çŠ¶æ€å­—å…¸ï¼ˆAPIè¿”å›žä½¿ç”¨ï¼‰"""
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "config_generated": self.config_generated,
            "error": self.error,
        }


class SimulationManager:
    """
    æ¨¡æ‹Ÿç®¡ç†å™¨
    
    æ ¸å¿ƒåŠŸèƒ½ï¼š
    1. ä»ŽZepå›¾è°±è¯»å–å®žä½“å¹¶è¿‡æ»¤
    2. ç”ŸæˆOASIS Agent Profile
    3. ä½¿ç”¨LLMæ™ºèƒ½ç”Ÿæˆæ¨¡æ‹Ÿé…ç½®å‚æ•°
    4. å‡†å¤‡é¢„è®¾è„šæœ¬æ‰€éœ€çš„æ‰€æœ‰æ–‡ä»¶
    """
    
    # æ¨¡æ‹Ÿæ•°æ®å­˜å‚¨ç›®å½•
    SIMULATION_DATA_DIR = os.path.join(
        os.path.dirname(__file__), 
        '../../uploads/simulations'
    )
    
    def __init__(self):
        # ç¡®ä¿ç›®å½•å­˜åœ¨
        os.makedirs(self.SIMULATION_DATA_DIR, exist_ok=True)
        
        # å†…å­˜ä¸­çš„æ¨¡æ‹ŸçŠ¶æ€ç¼“å­˜
        self._simulations: Dict[str, SimulationState] = {}
    
    def _get_simulation_dir(self, simulation_id: str) -> str:
        """èŽ·å–æ¨¡æ‹Ÿæ•°æ®ç›®å½•"""
        sim_dir = os.path.join(self.SIMULATION_DATA_DIR, simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        return sim_dir
    
    def _save_simulation_state(self, state: SimulationState):
        """ä¿å­˜æ¨¡æ‹ŸçŠ¶æ€åˆ°æ–‡ä»¶"""
        sim_dir = self._get_simulation_dir(state.simulation_id)
        state_file = os.path.join(sim_dir, "state.json")
        
        state.updated_at = datetime.now().isoformat()
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        
        self._simulations[state.simulation_id] = state
    
    def _load_simulation_state(self, simulation_id: str) -> Optional[SimulationState]:
        """ä»Žæ–‡ä»¶åŠ è½½æ¨¡æ‹ŸçŠ¶æ€"""
        if simulation_id in self._simulations:
            return self._simulations[simulation_id]
        
        sim_dir = self._get_simulation_dir(simulation_id)
        state_file = os.path.join(sim_dir, "state.json")
        
        if not os.path.exists(state_file):
            return None
        
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        state = SimulationState(
            simulation_id=simulation_id,
            project_id=data.get("project_id", ""),
            graph_id=data.get("graph_id", ""),
            enable_twitter=data.get("enable_twitter", True),
            enable_reddit=data.get("enable_reddit", True),
            status=SimulationStatus(data.get("status", "created")),
            entities_count=data.get("entities_count", 0),
            profiles_count=data.get("profiles_count", 0),
            entity_types=data.get("entity_types", []),
            config_generated=data.get("config_generated", False),
            config_reasoning=data.get("config_reasoning", ""),
            current_round=data.get("current_round", 0),
            twitter_status=data.get("twitter_status", "not_started"),
            reddit_status=data.get("reddit_status", "not_started"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            error=data.get("error"),
        )
        
        self._simulations[simulation_id] = state
        return state
    
    def create_simulation(
        self,
        project_id: str,
        graph_id: str,
        enable_twitter: bool = True,
        enable_reddit: bool = True,
    ) -> SimulationState:
        """
        åˆ›å»ºæ–°çš„æ¨¡æ‹Ÿ
        
        Args:
            project_id: é¡¹ç›®ID
            graph_id: Zepå›¾è°±ID
            enable_twitter: æ˜¯å¦å¯ç”¨Twitteræ¨¡æ‹Ÿ
            enable_reddit: æ˜¯å¦å¯ç”¨Redditæ¨¡æ‹Ÿ
            
        Returns:
            SimulationState
        """
        import uuid
        simulation_id = f"sim_{uuid.uuid4().hex[:12]}"
        
        state = SimulationState(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=enable_twitter,
            enable_reddit=enable_reddit,
            status=SimulationStatus.CREATED,
        )
        
        self._save_simulation_state(state)
        logger.info(f"åˆ›å»ºæ¨¡æ‹Ÿ: {simulation_id}, project={project_id}, graph={graph_id}")
        
        return state
    
    def prepare_simulation(
        self,
        simulation_id: str,
        simulation_requirement: str,
        document_text: str,
        defined_entity_types: Optional[List[str]] = None,
        use_llm_for_profiles: bool = True,
        progress_callback: Optional[callable] = None,
        parallel_profile_count: int = 3
    ) -> SimulationState:
        """
        å‡†å¤‡æ¨¡æ‹ŸçŽ¯å¢ƒï¼ˆå…¨ç¨‹è‡ªåŠ¨åŒ–ï¼‰
        
        æ­¥éª¤ï¼š
        1. ä»ŽZepå›¾è°±è¯»å–å¹¶è¿‡æ»¤å®žä½“
        2. ä¸ºæ¯ä¸ªå®žä½“ç”ŸæˆOASIS Agent Profileï¼ˆå¯é€‰LLMå¢žå¼ºï¼Œæ”¯æŒå¹¶è¡Œï¼‰
        3. ä½¿ç”¨LLMæ™ºèƒ½ç”Ÿæˆæ¨¡æ‹Ÿé…ç½®å‚æ•°ï¼ˆæ—¶é—´ã€æ´»è·ƒåº¦ã€å‘è¨€é¢‘çŽ‡ç­‰ï¼‰
        4. ä¿å­˜é…ç½®æ–‡ä»¶å’ŒProfileæ–‡ä»¶
        5. å¤åˆ¶é¢„è®¾è„šæœ¬åˆ°æ¨¡æ‹Ÿç›®å½•
        
        Args:
            simulation_id: æ¨¡æ‹ŸID
            simulation_requirement: æ¨¡æ‹Ÿéœ€æ±‚æè¿°ï¼ˆç”¨äºŽLLMç”Ÿæˆé…ç½®ï¼‰
            document_text: åŽŸå§‹æ–‡æ¡£å†…å®¹ï¼ˆç”¨äºŽLLMç†è§£èƒŒæ™¯ï¼‰
            defined_entity_types: é¢„å®šä¹‰çš„å®žä½“ç±»åž‹ï¼ˆå¯é€‰ï¼‰
            use_llm_for_profiles: æ˜¯å¦ä½¿ç”¨LLMç”Ÿæˆè¯¦ç»†äººè®¾
            progress_callback: è¿›åº¦å›žè°ƒå‡½æ•° (stage, progress, message)
            parallel_profile_count: å¹¶è¡Œç”Ÿæˆäººè®¾çš„æ•°é‡ï¼Œé»˜è®¤3
            
        Returns:
            SimulationState
        """
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"æ¨¡æ‹Ÿä¸å­˜åœ¨: {simulation_id}")
        
        try:
            state.status = SimulationStatus.PREPARING
            self._save_simulation_state(state)
            
            sim_dir = self._get_simulation_dir(simulation_id)
            
            # ========== é˜¶æ®µ1: è¯»å–å¹¶è¿‡æ»¤å®žä½“ ==========
            if progress_callback:
                progress_callback("reading", 0, t('progress.connectingZepGraph'))
            
            reader = ZepEntityReader()
            
            if progress_callback:
                progress_callback("reading", 30, t('progress.readingNodeData'))
            
            filtered = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=defined_entity_types,
                enrich_with_edges=True
            )
            
            state.entities_count = filtered.filtered_count
            state.entity_types = list(filtered.entity_types)
            
            if progress_callback:
                progress_callback(
                    "reading", 100,
                    t('progress.readingComplete', count=filtered.filtered_count),
                    current=filtered.filtered_count,
                    total=filtered.filtered_count
                )
            
            if filtered.filtered_count == 0:
                state.status = SimulationStatus.FAILED
                state.error = "æ²¡æœ‰æ‰¾åˆ°ç¬¦åˆæ¡ä»¶çš„å®žä½“ï¼Œè¯·æ£€æŸ¥å›¾è°±æ˜¯å¦æ­£ç¡®æž„å»º"
                self._save_simulation_state(state)
                return state
            
            # ========== é˜¶æ®µ2: ç”ŸæˆAgent Profile ==========
            total_entities = len(filtered.entities)
            
            if progress_callback:
                progress_callback(
                    "generating_profiles", 0,
                    t('progress.startGenerating'),
                    current=0,
                    total=total_entities
                )
            
            # ä¼ å…¥graph_idä»¥å¯ç”¨Zepæ£€ç´¢åŠŸèƒ½ï¼ŒèŽ·å–æ›´ä¸°å¯Œçš„ä¸Šä¸‹æ–‡
            generator = OasisProfileGenerator(graph_id=state.graph_id)
            
            def profile_progress(current, total, msg):
                if progress_callback:
                    progress_callback(
                        "generating_profiles", 
                        int(current / total * 100), 
                        msg,
                        current=current,
                        total=total,
                        item_name=msg
                    )
            
            # è®¾ç½®å®žæ—¶ä¿å­˜çš„æ–‡ä»¶è·¯å¾„ï¼ˆä¼˜å…ˆä½¿ç”¨ Reddit JSON æ ¼å¼ï¼‰
            realtime_output_path = None
            realtime_platform = "reddit"
            if state.enable_reddit:
                realtime_output_path = os.path.join(sim_dir, "reddit_profiles.json")
                realtime_platform = "reddit"
            elif state.enable_twitter:
                realtime_output_path = os.path.join(sim_dir, "twitter_profiles.csv")
                realtime_platform = "twitter"
            
            profiles = generator.generate_profiles_from_entities(
                entities=filtered.entities,
                use_llm=use_llm_for_profiles,
                progress_callback=profile_progress,
                graph_id=state.graph_id,  # ä¼ å…¥graph_idç”¨äºŽZepæ£€ç´¢
                parallel_count=parallel_profile_count,  # å¹¶è¡Œç”Ÿæˆæ•°é‡
                realtime_output_path=realtime_output_path,  # å®žæ—¶ä¿å­˜è·¯å¾„
                output_platform=realtime_platform  # è¾“å‡ºæ ¼å¼
            )
            
            state.profiles_count = len(profiles)
            
            # ä¿å­˜Profileæ–‡ä»¶ï¼ˆæ³¨æ„ï¼šTwitterä½¿ç”¨CSVæ ¼å¼ï¼ŒRedditä½¿ç”¨JSONæ ¼å¼ï¼‰
            # Reddit å·²ç»åœ¨ç”Ÿæˆè¿‡ç¨‹ä¸­å®žæ—¶ä¿å­˜äº†ï¼Œè¿™é‡Œå†ä¿å­˜ä¸€æ¬¡ç¡®ä¿å®Œæ•´æ€§
            if progress_callback:
                progress_callback(
                    "generating_profiles", 95,
                    t('progress.savingProfiles'),
                    current=total_entities,
                    total=total_entities
                )
            
            if state.enable_reddit:
                generator.save_profiles(
                    profiles=profiles,
                    file_path=os.path.join(sim_dir, "reddit_profiles.json"),
                    platform="reddit"
                )
            
            if state.enable_twitter:
                # Twitterä½¿ç”¨CSVæ ¼å¼ï¼è¿™æ˜¯OASISçš„è¦æ±‚
                generator.save_profiles(
                    profiles=profiles,
                    file_path=os.path.join(sim_dir, "twitter_profiles.csv"),
                    platform="twitter"
                )
            
            if progress_callback:
                progress_callback(
                    "generating_profiles", 100,
                    t('progress.profilesComplete', count=len(profiles)),
                    current=len(profiles),
                    total=len(profiles)
                )
            
            # ========== é˜¶æ®µ3: LLMæ™ºèƒ½ç”Ÿæˆæ¨¡æ‹Ÿé…ç½® ==========
            if progress_callback:
                progress_callback(
                    "generating_config", 0,
                    t('progress.analyzingRequirements'),
                    current=0,
                    total=3
                )
            
            config_generator = SimulationConfigGenerator()
            
            if progress_callback:
                progress_callback(
                    "generating_config", 30,
                    t('progress.callingLLMConfig'),
                    current=1,
                    total=3
                )
            
            sim_params = config_generator.generate_config(
                simulation_id=simulation_id,
                project_id=state.project_id,
                graph_id=state.graph_id,
                simulation_requirement=simulation_requirement,
                document_text=document_text,
                entities=filtered.entities,
                enable_twitter=state.enable_twitter,
                enable_reddit=state.enable_reddit
            )
            
            if progress_callback:
                progress_callback(
                    "generating_config", 70,
                    t('progress.savingConfigFiles'),
                    current=2,
                    total=3
                )
            
            # ä¿å­˜é…ç½®æ–‡ä»¶
            config_path = os.path.join(sim_dir, "simulation_config.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(sim_params.to_json())
            
            state.config_generated = True
            state.config_reasoning = sim_params.generation_reasoning
            
            if progress_callback:
                progress_callback(
                    "generating_config", 100,
                    t('progress.configComplete'),
                    current=3,
                    total=3
                )
            
            # æ³¨æ„ï¼šè¿è¡Œè„šæœ¬ä¿ç•™åœ¨ backend/scripts/ ç›®å½•ï¼Œä¸å†å¤åˆ¶åˆ°æ¨¡æ‹Ÿç›®å½•
            # å¯åŠ¨æ¨¡æ‹Ÿæ—¶ï¼Œsimulation_runner ä¼šä»Ž scripts/ ç›®å½•è¿è¡Œè„šæœ¬
            
            # æ›´æ–°çŠ¶æ€
            state.status = SimulationStatus.READY
            self._save_simulation_state(state)
            
            logger.info(f"æ¨¡æ‹Ÿå‡†å¤‡å®Œæˆ: {simulation_id}, "
                       f"entities={state.entities_count}, profiles={state.profiles_count}")
            
            return state
            
        except Exception as e:
            logger.error(f"æ¨¡æ‹Ÿå‡†å¤‡å¤±è´¥: {simulation_id}, error={str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            state.status = SimulationStatus.FAILED
            state.error = str(e)
            self._save_simulation_state(state)
            raise
    
    def get_simulation(self, simulation_id: str) -> Optional[SimulationState]:
        """èŽ·å–æ¨¡æ‹ŸçŠ¶æ€"""
        return self._load_simulation_state(simulation_id)
    
    def list_simulations(self, project_id: Optional[str] = None) -> List[SimulationState]:
        """åˆ—å‡ºæ‰€æœ‰æ¨¡æ‹Ÿ"""
        simulations = []
        
        if os.path.exists(self.SIMULATION_DATA_DIR):
            for sim_id in os.listdir(self.SIMULATION_DATA_DIR):
                # è·³è¿‡éšè—æ–‡ä»¶ï¼ˆå¦‚ .DS_Storeï¼‰å’Œéžç›®å½•æ–‡ä»¶
                sim_path = os.path.join(self.SIMULATION_DATA_DIR, sim_id)
                if sim_id.startswith('.') or not os.path.isdir(sim_path):
                    continue
                
                state = self._load_simulation_state(sim_id)
                if state:
                    if project_id is None or state.project_id == project_id:
                        simulations.append(state)
        
        return simulations
    
    def get_profiles(self, simulation_id: str, platform: str = "reddit") -> List[Dict[str, Any]]:
        """èŽ·å–æ¨¡æ‹Ÿçš„Agent Profile"""
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"æ¨¡æ‹Ÿä¸å­˜åœ¨: {simulation_id}")
        
        sim_dir = self._get_simulation_dir(simulation_id)
        profile_path = os.path.join(sim_dir, f"{platform}_profiles.json")
        
        if not os.path.exists(profile_path):
            return []
        
        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_simulation_config(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """èŽ·å–æ¨¡æ‹Ÿé…ç½®"""
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return None
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_run_instructions(self, simulation_id: str) -> Dict[str, str]:
        """èŽ·å–è¿è¡Œè¯´æ˜Ž"""
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))
        
        return {
            "simulation_dir": sim_dir,
            "scripts_dir": scripts_dir,
            "config_file": config_path,
            "commands": {
                "twitter": f"python {scripts_dir}/run_twitter_simulation.py --config {config_path}",
                "reddit": f"python {scripts_dir}/run_reddit_simulation.py --config {config_path}",
                "parallel": f"python {scripts_dir}/run_parallel_simulation.py --config {config_path}",
            },
            "instructions": (
                f"1. æ¿€æ´»condaçŽ¯å¢ƒ: conda activate Posiedon\n"
                f"2. è¿è¡Œæ¨¡æ‹Ÿ (è„šæœ¬ä½äºŽ {scripts_dir}):\n"
                f"   - å•ç‹¬è¿è¡ŒTwitter: python {scripts_dir}/run_twitter_simulation.py --config {config_path}\n"
                f"   - å•ç‹¬è¿è¡ŒReddit: python {scripts_dir}/run_reddit_simulation.py --config {config_path}\n"
                f"   - å¹¶è¡Œè¿è¡ŒåŒå¹³å°: python {scripts_dir}/run_parallel_simulation.py --config {config_path}"
            )
        }

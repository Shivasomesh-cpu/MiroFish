"""
OASISÃ¦Â¨Â¡Ã¦â€¹Å¸Ã§Â®Â¡Ã§Ââ€ Ã¥â„¢Â¨
Ã§Â®Â¡Ã§Ââ€ TwitterÃ¥â€™Å’RedditÃ¥ÂÅ’Ã¥Â¹Â³Ã¥ÂÂ°Ã¥Â¹Â¶Ã¨Â¡Å’Ã¦Â¨Â¡Ã¦â€¹Å¸
Ã¤Â½Â¿Ã§â€Â¨Ã©Â¢â€žÃ¨Â®Â¾Ã¨â€žÅ¡Ã¦Å“Â¬ + LLMÃ¦â„¢ÂºÃ¨Æ’Â½Ã§â€Å¸Ã¦Ë†ÂÃ©â€¦ÂÃ§Â½Â®Ã¥Ââ€šÃ¦â€¢Â°
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
    """Ã¦Â¨Â¡Ã¦â€¹Å¸Ã§Å Â¶Ã¦â‚¬Â"""
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"      # Ã¦Â¨Â¡Ã¦â€¹Å¸Ã¨Â¢Â«Ã¦â€°â€¹Ã¥Å Â¨Ã¥ÂÅ“Ã¦Â­Â¢
    COMPLETED = "completed"  # Ã¦Â¨Â¡Ã¦â€¹Å¸Ã¨â€¡ÂªÃ§â€žÂ¶Ã¥Â®Å’Ã¦Ë†Â
    FAILED = "failed"


class PlatformType(str, Enum):
    """Ã¥Â¹Â³Ã¥ÂÂ°Ã§Â±Â»Ã¥Å¾â€¹"""
    TWITTER = "twitter"
    REDDIT = "reddit"


@dataclass
class SimulationState:
    """Ã¦Â¨Â¡Ã¦â€¹Å¸Ã§Å Â¶Ã¦â‚¬Â"""
    simulation_id: str
    project_id: str
    graph_id: str
    
    enable_twitter: bool = True
    enable_reddit: bool = True
    
    status: SimulationStatus = SimulationStatus.CREATED
    
    entities_count: int = 0
    profiles_count: int = 0
    entity_types: List[str] = field(default_factory=list)
    
    config_generated: bool = False
    config_reasoning: str = ""
    
    current_round: int = 0
    twitter_status: str = "not_started"
    reddit_status: str = "not_started"
    
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Ã¥Â®Å’Ã¦â€¢Â´Ã§Å Â¶Ã¦â‚¬ÂÃ¥Â­â€”Ã¥â€¦Â¸Ã¯Â¼Ë†Ã¥â€ â€¦Ã©Æ’Â¨Ã¤Â½Â¿Ã§â€Â¨Ã¯Â¼â€°"""
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
        """Ã§Â®â‚¬Ã¥Å’â€“Ã§Å Â¶Ã¦â‚¬ÂÃ¥Â­â€”Ã¥â€¦Â¸Ã¯Â¼Ë†APIÃ¨Â¿â€Ã¥â€ºÅ¾Ã¤Â½Â¿Ã§â€Â¨Ã¯Â¼â€°"""
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
    
    """
    
    SIMULATION_DATA_DIR = os.path.join(
        os.path.dirname(__file__), 
        '../../uploads/simulations'
    )
    
    def __init__(self):
        os.makedirs(self.SIMULATION_DATA_DIR, exist_ok=True)
        
        self._simulations: Dict[str, SimulationState] = {}
    
    def _get_simulation_dir(self, simulation_id: str) -> str:
        """Ã¨Å½Â·Ã¥Ââ€“Ã¦Â¨Â¡Ã¦â€¹Å¸Ã¦â€¢Â°Ã¦ÂÂ®Ã§â€ºÂ®Ã¥Â½â€¢"""
        sim_dir = os.path.join(self.SIMULATION_DATA_DIR, simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        return sim_dir
    
    def _save_simulation_state(self, state: SimulationState):
        """Ã¤Â¿ÂÃ¥Â­ËœÃ¦Â¨Â¡Ã¦â€¹Å¸Ã§Å Â¶Ã¦â‚¬ÂÃ¥Ë†Â°Ã¦â€“â€¡Ã¤Â»Â¶"""
        sim_dir = self._get_simulation_dir(state.simulation_id)
        state_file = os.path.join(sim_dir, "state.json")
        
        state.updated_at = datetime.now().isoformat()
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        
        self._simulations[state.simulation_id] = state
    
    def _load_simulation_state(self, simulation_id: str) -> Optional[SimulationState]:
        """Ã¤Â»Å½Ã¦â€“â€¡Ã¤Â»Â¶Ã¥Å Â Ã¨Â½Â½Ã¦Â¨Â¡Ã¦â€¹Å¸Ã§Å Â¶Ã¦â‚¬Â"""
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
        
        Args:
            
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
        logger.info(f"Ã¥Ë†â€ºÃ¥Â»ÂºÃ¦Â¨Â¡Ã¦â€¹Å¸: {simulation_id}, project={project_id}, graph={graph_id}")
        
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
        
        
        Args:
            
        Returns:
            SimulationState
        """
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"Ã¦Â¨Â¡Ã¦â€¹Å¸Ã¤Â¸ÂÃ¥Â­ËœÃ¥Å“Â¨: {simulation_id}")
        
        try:
            state.status = SimulationStatus.PREPARING
            self._save_simulation_state(state)
            
            sim_dir = self._get_simulation_dir(simulation_id)
            
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
                state.error = "Ã¦Â²Â¡Ã¦Å“â€°Ã¦â€°Â¾Ã¥Ë†Â°Ã§Â¬Â¦Ã¥ÂË†Ã¦ÂÂ¡Ã¤Â»Â¶Ã§Å¡â€žÃ¥Â®Å¾Ã¤Â½â€œÃ¯Â¼Å’Ã¨Â¯Â·Ã¦Â£â‚¬Ã¦Å¸Â¥Ã¥â€ºÂ¾Ã¨Â°Â±Ã¦ËœÂ¯Ã¥ÂÂ¦Ã¦Â­Â£Ã§Â¡Â®Ã¦Å¾â€žÃ¥Â»Âº"
                self._save_simulation_state(state)
                return state
            
            total_entities = len(filtered.entities)
            
            if progress_callback:
                progress_callback(
                    "generating_profiles", 0,
                    t('progress.startGenerating'),
                    current=0,
                    total=total_entities
                )
            
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
                graph_id=state.graph_id,  # Ã¤Â¼Â Ã¥â€¦Â¥graph_idÃ§â€Â¨Ã¤ÂºÅ½ZepÃ¦Â£â‚¬Ã§Â´Â¢
                parallel_count=parallel_profile_count,  # Ã¥Â¹Â¶Ã¨Â¡Å’Ã§â€Å¸Ã¦Ë†ÂÃ¦â€¢Â°Ã©â€¡Â
                realtime_output_path=realtime_output_path,  # Ã¥Â®Å¾Ã¦â€”Â¶Ã¤Â¿ÂÃ¥Â­ËœÃ¨Â·Â¯Ã¥Â¾â€ž
                output_platform=realtime_platform  # Ã¨Â¾â€œÃ¥â€¡ÂºÃ¦Â Â¼Ã¥Â¼Â
            )
            
            state.profiles_count = len(profiles)
            
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
            
            
            state.status = SimulationStatus.READY
            self._save_simulation_state(state)
            
            logger.info(f"Ã¦Â¨Â¡Ã¦â€¹Å¸Ã¥â€¡â€ Ã¥Â¤â€¡Ã¥Â®Å’Ã¦Ë†Â: {simulation_id}, "
                       f"entities={state.entities_count}, profiles={state.profiles_count}")
            
            return state
            
        except Exception as e:
            logger.error(f"Ã¦Â¨Â¡Ã¦â€¹Å¸Ã¥â€¡â€ Ã¥Â¤â€¡Ã¥Â¤Â±Ã¨Â´Â¥: {simulation_id}, error={str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            state.status = SimulationStatus.FAILED
            state.error = str(e)
            self._save_simulation_state(state)
            raise
    
    def get_simulation(self, simulation_id: str) -> Optional[SimulationState]:
        """Ã¨Å½Â·Ã¥Ââ€“Ã¦Â¨Â¡Ã¦â€¹Å¸Ã§Å Â¶Ã¦â‚¬Â"""
        return self._load_simulation_state(simulation_id)
    
    def list_simulations(self, project_id: Optional[str] = None) -> List[SimulationState]:
        """Ã¥Ë†â€”Ã¥â€¡ÂºÃ¦â€°â‚¬Ã¦Å“â€°Ã¦Â¨Â¡Ã¦â€¹Å¸"""
        simulations = []
        
        if os.path.exists(self.SIMULATION_DATA_DIR):
            for sim_id in os.listdir(self.SIMULATION_DATA_DIR):
                sim_path = os.path.join(self.SIMULATION_DATA_DIR, sim_id)
                if sim_id.startswith('.') or not os.path.isdir(sim_path):
                    continue
                
                state = self._load_simulation_state(sim_id)
                if state:
                    if project_id is None or state.project_id == project_id:
                        simulations.append(state)
        
        return simulations
    
    def get_profiles(self, simulation_id: str, platform: str = "reddit") -> List[Dict[str, Any]]:
        """Ã¨Å½Â·Ã¥Ââ€“Ã¦Â¨Â¡Ã¦â€¹Å¸Ã§Å¡â€žAgent Profile"""
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"Ã¦Â¨Â¡Ã¦â€¹Å¸Ã¤Â¸ÂÃ¥Â­ËœÃ¥Å“Â¨: {simulation_id}")
        
        sim_dir = self._get_simulation_dir(simulation_id)
        profile_path = os.path.join(sim_dir, f"{platform}_profiles.json")
        
        if not os.path.exists(profile_path):
            return []
        
        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_simulation_config(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """Ã¨Å½Â·Ã¥Ââ€“Ã¦Â¨Â¡Ã¦â€¹Å¸Ã©â€¦ÂÃ§Â½Â®"""
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return None
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_run_instructions(self, simulation_id: str) -> Dict[str, str]:
        """Ã¨Å½Â·Ã¥Ââ€“Ã¨Â¿ÂÃ¨Â¡Å’Ã¨Â¯Â´Ã¦ËœÅ½"""
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
                f"1. Ã¦Â¿â‚¬Ã¦Â´Â»condaÃ§Å½Â¯Ã¥Â¢Æ’: conda activate Posiedon\n"
                f"2. Ã¨Â¿ÂÃ¨Â¡Å’Ã¦Â¨Â¡Ã¦â€¹Å¸ (Ã¨â€žÅ¡Ã¦Å“Â¬Ã¤Â½ÂÃ¤ÂºÅ½ {scripts_dir}):\n"
                f"   - Ã¥Ââ€¢Ã§â€¹Â¬Ã¨Â¿ÂÃ¨Â¡Å’Twitter: python {scripts_dir}/run_twitter_simulation.py --config {config_path}\n"
                f"   - Ã¥Ââ€¢Ã§â€¹Â¬Ã¨Â¿ÂÃ¨Â¡Å’Reddit: python {scripts_dir}/run_reddit_simulation.py --config {config_path}\n"
                f"   - Ã¥Â¹Â¶Ã¨Â¡Å’Ã¨Â¿ÂÃ¨Â¡Å’Ã¥ÂÅ’Ã¥Â¹Â³Ã¥ÂÂ°: python {scripts_dir}/run_parallel_simulation.py --config {config_path}"
            )
        }




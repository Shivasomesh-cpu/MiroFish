"""
Checkpoint Manager Service

Provides checkpoint creation and restoration for simulation state.
This enables pause/resume functionality by serializing the full simulation
state to JSON files that can be loaded later.

Checkpoint contents:
- Agent personas with current state
- Simulation round number
- Knowledge graph snapshot reference
- Actions log up to checkpoint point
- Configuration parameters
"""

import os
import json
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('posiedon.checkpoint_manager')


@dataclass
class CheckpointMetadata:
    """Metadata about a checkpoint"""
    checkpoint_id: str
    simulation_id: str
    round_number: int
    simulated_hours: int
    created_at: str
    agent_count: int
    twitter_actions_count: int
    reddit_actions_count: int
    graph_id: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CheckpointData:
    """Full checkpoint data"""
    metadata: CheckpointMetadata
    agent_personas: List[Dict[str, Any]]
    config: Dict[str, Any]
    graph_snapshot_id: Optional[str] = None
    actions_file_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "agent_personas": self.agent_personas,
            "config": self.config,
            "graph_snapshot_id": self.graph_snapshot_id,
            "actions_file_path": self.actions_file_path
        }


class CheckpointManager:
    """
    Manages simulation checkpoints for pause/resume functionality.
    
    Checkpoints are stored in: uploads/simulations/{sim_id}/checkpoints/
    Each checkpoint contains:
    - checkpoint.json: Metadata and configuration
    - personas.json: Agent personas with state
    - actions.jsonl: Copy of actions log up to checkpoint
    """
    
    # Base directory for simulations
    SIMULATIONS_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../uploads/simulations'
    )
    
    CHECKPOINTS_DIRNAME = "checkpoints"
    
    @classmethod
    def _get_checkpoint_dir(cls, simulation_id: str, checkpoint_id: str) -> str:
        """Get the directory path for a checkpoint."""
        return os.path.join(
            cls.SIMULATIONS_DIR,
            simulation_id,
            cls.CHECKPOINTS_DIRNAME,
            checkpoint_id
        )
    
    @classmethod
    def _get_checkpoints_base_dir(cls, simulation_id: str) -> str:
        """Get the base checkpoints directory for a simulation."""
        return os.path.join(
            cls.SIMULATIONS_DIR,
            simulation_id,
            cls.CHECKPOINTS_DIRNAME
        )
    
    @classmethod
    def create_checkpoint(
        cls,
        simulation_id: str,
        round_number: int,
        simulated_hours: int,
        agent_personas: List[Dict[str, Any]],
        config: Dict[str, Any],
        graph_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> CheckpointMetadata:
        """
        Create a checkpoint of the current simulation state.
        
        Args:
            simulation_id: The simulation ID
            round_number: Current round number
            simulated_hours: Current simulated time
            agent_personas: List of agent persona dictionaries
            config: Simulation configuration
            graph_id: Optional Zep graph ID
            description: Optional description of checkpoint
            
        Returns:
            CheckpointMetadata for the created checkpoint
        """
        # Generate checkpoint ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_id = f"chkpt_r{round_number}_{timestamp}"
        
        # Create checkpoint directory
        checkpoint_dir = cls._get_checkpoint_dir(simulation_id, checkpoint_id)
        os.makedirs(checkpoint_dir, exist_ok=True)
        
        # Count actions
        sim_dir = os.path.join(cls.SIMULATIONS_DIR, simulation_id)
        twitter_count = cls._count_actions(os.path.join(sim_dir, "twitter", "actions.jsonl"))
        reddit_count = cls._count_actions(os.path.join(sim_dir, "reddit", "actions.jsonl"))
        
        # Create metadata
        metadata = CheckpointMetadata(
            checkpoint_id=checkpoint_id,
            simulation_id=simulation_id,
            round_number=round_number,
            simulated_hours=simulated_hours,
            created_at=datetime.now().isoformat(),
            agent_count=len(agent_personas),
            twitter_actions_count=twitter_count,
            reddit_actions_count=reddit_count,
            graph_id=graph_id,
            description=description
        )
        
        # Save metadata
        metadata_path = os.path.join(checkpoint_dir, "checkpoint.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2)
        
        # Save agent personas
        personas_path = os.path.join(checkpoint_dir, "personas.json")
        with open(personas_path, 'w', encoding='utf-8') as f:
            json.dump(agent_personas, f, ensure_ascii=False, indent=2)
        
        # Save config
        config_path = os.path.join(checkpoint_dir, "config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        # Copy action logs
        cls._copy_actions_to_checkpoint(simulation_id, checkpoint_dir)
        
        logger.info(f"Created checkpoint: {checkpoint_id} for simulation {simulation_id} "
                   f"at round {round_number}")
        
        return metadata
    
    @classmethod
    def _count_actions(cls, actions_path: str) -> int:
        """Count the number of action records in an actions file."""
        if not os.path.exists(actions_path):
            return 0
        
        count = 0
        try:
            with open(actions_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            # Only count actual actions, not events
                            if "agent_id" in data and "event_type" not in data:
                                count += 1
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            logger.warning(f"Error counting actions in {actions_path}: {e}")
        
        return count
    
    @classmethod
    def _copy_actions_to_checkpoint(cls, simulation_id: str, checkpoint_dir: str):
        """Copy action logs to checkpoint directory."""
        sim_dir = os.path.join(cls.SIMULATIONS_DIR, simulation_id)
        
        for platform in ["twitter", "reddit"]:
            src_path = os.path.join(sim_dir, platform, "actions.jsonl")
            if os.path.exists(src_path):
                dst_dir = os.path.join(checkpoint_dir, platform)
                os.makedirs(dst_dir, exist_ok=True)
                dst_path = os.path.join(dst_dir, "actions.jsonl")
                shutil.copy2(src_path, dst_path)
    
    @classmethod
    def load_checkpoint(
        cls,
        simulation_id: str,
        checkpoint_id: str
    ) -> Optional[CheckpointData]:
        """
        Load a checkpoint.
        
        Args:
            simulation_id: The simulation ID
            checkpoint_id: The checkpoint ID to load
            
        Returns:
            CheckpointData or None if not found
        """
        checkpoint_dir = cls._get_checkpoint_dir(simulation_id, checkpoint_id)
        
        if not os.path.exists(checkpoint_dir):
            logger.warning(f"Checkpoint not found: {checkpoint_id}")
            return None
        
        try:
            # Load metadata
            metadata_path = os.path.join(checkpoint_dir, "checkpoint.json")
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata_dict = json.load(f)
            
            metadata = CheckpointMetadata(**metadata_dict)
            
            # Load personas
            personas_path = os.path.join(checkpoint_dir, "personas.json")
            with open(personas_path, 'r', encoding='utf-8') as f:
                agent_personas = json.load(f)
            
            # Load config
            config_path = os.path.join(checkpoint_dir, "config.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            return CheckpointData(
                metadata=metadata,
                agent_personas=agent_personas,
                config=config,
                actions_file_path=checkpoint_dir
            )
            
        except Exception as e:
            logger.error(f"Error loading checkpoint {checkpoint_id}: {e}")
            return None
    
    @classmethod
    def list_checkpoints(cls, simulation_id: str) -> List[CheckpointMetadata]:
        """
        List all checkpoints for a simulation.
        
        Args:
            simulation_id: The simulation ID
            
        Returns:
            List of CheckpointMetadata, sorted by round number (descending)
        """
        checkpoints_dir = cls._get_checkpoints_base_dir(simulation_id)
        
        if not os.path.exists(checkpoints_dir):
            return []
        
        checkpoints = []
        
        for checkpoint_id in os.listdir(checkpoints_dir):
            checkpoint_dir = os.path.join(checkpoints_dir, checkpoint_id)
            if not os.path.isdir(checkpoint_dir):
                continue
            
            metadata_path = os.path.join(checkpoint_dir, "checkpoint.json")
            if not os.path.exists(metadata_path):
                continue
            
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata_dict = json.load(f)
                checkpoints.append(CheckpointMetadata(**metadata_dict))
            except Exception as e:
                logger.warning(f"Error reading checkpoint {checkpoint_id}: {e}")
        
        # Sort by round number (descending)
        checkpoints.sort(key=lambda x: x.round_number, reverse=True)
        
        return checkpoints
    
    @classmethod
    def delete_checkpoint(cls, simulation_id: str, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint.
        
        Args:
            simulation_id: The simulation ID
            checkpoint_id: The checkpoint ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        checkpoint_dir = cls._get_checkpoint_dir(simulation_id, checkpoint_id)
        
        if not os.path.exists(checkpoint_dir):
            return False
        
        try:
            shutil.rmtree(checkpoint_dir)
            logger.info(f"Deleted checkpoint: {checkpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting checkpoint {checkpoint_id}: {e}")
            return False
    
    @classmethod
    def restore_from_checkpoint(
        cls,
        simulation_id: str,
        checkpoint_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Restore simulation state from a checkpoint.
        
        This copies the checkpoint's action logs back to the simulation
        directory and returns the checkpoint data for restarting.
        
        Args:
            simulation_id: The simulation ID
            checkpoint_id: The checkpoint ID to restore from
            
        Returns:
            Dictionary with restoration info or None if failed
        """
        checkpoint = cls.load_checkpoint(simulation_id, checkpoint_id)
        if not checkpoint:
            return None
        
        sim_dir = os.path.join(cls.SIMULATIONS_DIR, simulation_id)
        checkpoint_dir = cls._get_checkpoint_dir(simulation_id, checkpoint_id)
        
        try:
            # Backup current action logs
            backup_dir = os.path.join(sim_dir, "pre_restore_backup")
            os.makedirs(backup_dir, exist_ok=True)
            
            for platform in ["twitter", "reddit"]:
                src_path = os.path.join(sim_dir, platform, "actions.jsonl")
                if os.path.exists(src_path):
                    dst_path = os.path.join(backup_dir, f"{platform}_actions.jsonl")
                    shutil.copy2(src_path, dst_path)
            
            # Restore action logs from checkpoint
            for platform in ["twitter", "reddit"]:
                src_path = os.path.join(checkpoint_dir, platform, "actions.jsonl")
                if os.path.exists(src_path):
                    dst_dir = os.path.join(sim_dir, platform)
                    os.makedirs(dst_dir, exist_ok=True)
                    dst_path = os.path.join(dst_dir, "actions.jsonl")
                    shutil.copy2(src_path, dst_path)
            
            logger.info(f"Restored simulation {simulation_id} from checkpoint {checkpoint_id}")
            
            return {
                "checkpoint_id": checkpoint_id,
                "restored_round": checkpoint.metadata.round_number,
                "agent_count": checkpoint.metadata.agent_count,
                "config": checkpoint.config,
                "backup_dir": backup_dir
            }
            
        except Exception as e:
            logger.error(f"Error restoring from checkpoint {checkpoint_id}: {e}")
            return None
    
    @classmethod
    def auto_checkpoint_interval(cls, total_rounds: int) -> int:
        """
        Calculate automatic checkpoint interval based on total rounds.
        
        Creates checkpoints roughly every 10% of progress, with minimum
        of every 5 rounds and maximum of every 50 rounds.
        
        Args:
            total_rounds: Total number of rounds in simulation
            
        Returns:
            Checkpoint interval in rounds
        """
        interval = max(5, min(50, total_rounds // 10))
        return interval

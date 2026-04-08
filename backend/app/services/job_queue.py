"""
Job Queue Service

Provides a SQLite-backed persistent job queue for simulation state management.
This ensures simulation state survives Flask restarts and allows for:
- Job state persistence across server restarts
- Detection and recovery of interrupted simulations
- Checkpoint-based resume functionality

The jobs table stores simulation job metadata and progress checkpoints.
"""

import os
import json
import sqlite3
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.job_queue')


class JobStatus(str, Enum):
    """Job status values"""
    PENDING = "pending"          # Job created but not started
    RUNNING = "running"          # Job is actively running
    PAUSED = "paused"            # Job paused by user
    COMPLETED = "completed"      # Job finished successfully
    FAILED = "failed"            # Job failed with error
    INTERRUPTED = "interrupted"  # Job was interrupted (server crash, etc.)
    STOPPED = "stopped"          # Job stopped by user


@dataclass
class JobRecord:
    """Represents a job in the queue"""
    job_id: str
    simulation_id: str
    status: JobStatus
    config_json: str
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    pid: Optional[int] = None
    step_current: int = 0
    step_total: int = 0
    checkpoint_round: int = 0
    error_msg: Optional[str] = None
    platform: str = "parallel"
    graph_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "simulation_id": self.simulation_id,
            "status": self.status.value if isinstance(self.status, JobStatus) else self.status,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "pid": self.pid,
            "step_current": self.step_current,
            "step_total": self.step_total,
            "checkpoint_round": self.checkpoint_round,
            "error_msg": self.error_msg,
            "platform": self.platform,
            "graph_id": self.graph_id,
            "progress_percent": round(self.step_current / max(self.step_total, 1) * 100, 1),
        }


class JobQueue:
    """
    SQLite-backed job queue for simulation management.
    
    Features:
    - Persistent job state across server restarts
    - PID tracking for process monitoring
    - Checkpoint support for resume functionality
    - Automatic detection of interrupted jobs
    """
    
    # Database file location
    DB_PATH = os.path.join(
        os.path.dirname(__file__),
        '../../uploads/jobs.db'
    )
    
    # Thread lock for database operations
    _lock = threading.Lock()
    
    # Connection pool (per-thread)
    _local = threading.local()
    
    @classmethod
    def _get_connection(cls) -> sqlite3.Connection:
        """Get a database connection for the current thread."""
        if not hasattr(cls._local, 'conn') or cls._local.conn is None:
            # Ensure directory exists
            os.makedirs(os.path.dirname(cls.DB_PATH), exist_ok=True)
            
            conn = sqlite3.connect(cls.DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cls._local.conn = conn
            
            # Initialize schema
            cls._init_schema(conn)
        
        return cls._local.conn
    
    @classmethod
    def _init_schema(cls, conn: sqlite3.Connection):
        """Initialize the database schema."""
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                simulation_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                config_json TEXT,
                started_at TEXT,
                updated_at TEXT,
                completed_at TEXT,
                pid INTEGER,
                step_current INTEGER DEFAULT 0,
                step_total INTEGER DEFAULT 0,
                checkpoint_round INTEGER DEFAULT 0,
                error_msg TEXT,
                platform TEXT DEFAULT 'parallel',
                graph_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Index for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_simulation_id ON jobs(simulation_id)
        """)
        
        conn.commit()
        logger.debug("Job queue database initialized")
    
    @classmethod
    def create_job(
        cls,
        job_id: str,
        simulation_id: str,
        config: Dict[str, Any],
        platform: str = "parallel",
        graph_id: Optional[str] = None,
        total_steps: int = 0
    ) -> JobRecord:
        """
        Create a new job record.
        
        Args:
            job_id: Unique job identifier
            simulation_id: Associated simulation ID
            config: Simulation configuration dictionary
            platform: Platform type (twitter/reddit/parallel)
            graph_id: Optional Zep graph ID
            total_steps: Total number of steps (rounds)
            
        Returns:
            Created JobRecord
        """
        with cls._lock:
            conn = cls._get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            config_json = json.dumps(config, ensure_ascii=False)
            
            cursor.execute("""
                INSERT INTO jobs (
                    job_id, simulation_id, status, config_json, 
                    updated_at, step_total, platform, graph_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, simulation_id, JobStatus.PENDING.value,
                config_json, now, total_steps, platform, graph_id
            ))
            
            conn.commit()
            
            logger.info(f"Created job: {job_id} for simulation {simulation_id}")
            
            return JobRecord(
                job_id=job_id,
                simulation_id=simulation_id,
                status=JobStatus.PENDING,
                config_json=config_json,
                updated_at=now,
                step_total=total_steps,
                platform=platform,
                graph_id=graph_id
            )
    
    @classmethod
    def get_job(cls, job_id: str) -> Optional[JobRecord]:
        """
        Get a job by ID.
        
        Args:
            job_id: The job ID
            
        Returns:
            JobRecord or None if not found
        """
        conn = cls._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return cls._row_to_record(row)
    
    @classmethod
    def get_job_by_simulation(cls, simulation_id: str) -> Optional[JobRecord]:
        """
        Get the most recent job for a simulation.
        
        Args:
            simulation_id: The simulation ID
            
        Returns:
            JobRecord or None if not found
        """
        conn = cls._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM jobs 
            WHERE simulation_id = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (simulation_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return cls._row_to_record(row)
    
    @classmethod
    def _row_to_record(cls, row: sqlite3.Row) -> JobRecord:
        """Convert a database row to a JobRecord."""
        return JobRecord(
            job_id=row['job_id'],
            simulation_id=row['simulation_id'],
            status=JobStatus(row['status']),
            config_json=row['config_json'],
            started_at=row['started_at'],
            updated_at=row['updated_at'],
            completed_at=row['completed_at'],
            pid=row['pid'],
            step_current=row['step_current'],
            step_total=row['step_total'],
            checkpoint_round=row['checkpoint_round'],
            error_msg=row['error_msg'],
            platform=row['platform'],
            graph_id=row['graph_id'],
        )
    
    @classmethod
    def update_job(
        cls,
        job_id: str,
        status: Optional[JobStatus] = None,
        pid: Optional[int] = None,
        step_current: Optional[int] = None,
        checkpoint_round: Optional[int] = None,
        error_msg: Optional[str] = None,
        completed_at: Optional[str] = None
    ) -> bool:
        """
        Update a job record.
        
        Args:
            job_id: The job ID to update
            status: New status
            pid: Process ID
            step_current: Current step/round
            checkpoint_round: Last checkpointed round
            error_msg: Error message if failed
            completed_at: Completion timestamp
            
        Returns:
            True if updated, False if job not found
        """
        with cls._lock:
            conn = cls._get_connection()
            cursor = conn.cursor()
            
            updates = []
            params = []
            
            if status is not None:
                updates.append("status = ?")
                params.append(status.value if isinstance(status, JobStatus) else status)
            
            if pid is not None:
                updates.append("pid = ?")
                params.append(pid)
                if status == JobStatus.RUNNING:
                    updates.append("started_at = ?")
                    params.append(datetime.now().isoformat())
            
            if step_current is not None:
                updates.append("step_current = ?")
                params.append(step_current)
            
            if checkpoint_round is not None:
                updates.append("checkpoint_round = ?")
                params.append(checkpoint_round)
            
            if error_msg is not None:
                updates.append("error_msg = ?")
                params.append(error_msg)
            
            if completed_at is not None:
                updates.append("completed_at = ?")
                params.append(completed_at)
            
            # Always update updated_at
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            
            params.append(job_id)
            
            cursor.execute(f"""
                UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?
            """, params)
            
            conn.commit()
            
            return cursor.rowcount > 0
    
    @classmethod
    def get_jobs_by_status(cls, status: JobStatus) -> List[JobRecord]:
        """
        Get all jobs with a specific status.
        
        Args:
            status: The status to filter by
            
        Returns:
            List of JobRecords
        """
        conn = cls._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC
        """, (status.value,))
        
        return [cls._row_to_record(row) for row in cursor.fetchall()]
    
    @classmethod
    def get_running_jobs(cls) -> List[JobRecord]:
        """Get all jobs with running status."""
        return cls.get_jobs_by_status(JobStatus.RUNNING)
    
    @classmethod
    def is_process_alive(cls, pid: int) -> bool:
        """
        Check if a process is still running.
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if process is alive, False otherwise
        """
        if pid is None:
            return False
        
        try:
            # On Windows and Unix, os.kill with signal 0 checks if process exists
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    
    @classmethod
    def detect_interrupted_jobs(cls) -> List[JobRecord]:
        """
        Detect jobs that were interrupted (server crash, etc.).
        
        A job is considered interrupted if:
        - Status is RUNNING
        - PID is set
        - Process with that PID is not alive
        
        Returns:
            List of interrupted JobRecords
        """
        interrupted = []
        running_jobs = cls.get_running_jobs()
        
        for job in running_jobs:
            if job.pid and not cls.is_process_alive(job.pid):
                # Mark as interrupted
                cls.update_job(
                    job.job_id,
                    status=JobStatus.INTERRUPTED,
                    error_msg="Process terminated unexpectedly (server restart or crash)"
                )
                job.status = JobStatus.INTERRUPTED
                interrupted.append(job)
                logger.warning(f"Detected interrupted job: {job.job_id} (PID {job.pid} not alive)")
        
        return interrupted
    
    @classmethod
    def get_restartable_jobs(cls) -> List[JobRecord]:
        """
        Get all jobs that can be restarted.
        
        A job is restartable if:
        - Status is INTERRUPTED, FAILED, or PAUSED
        - Has a checkpoint_round > 0 (or can start from beginning)
        
        Returns:
            List of restartable JobRecords
        """
        conn = cls._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM jobs 
            WHERE status IN (?, ?, ?)
            ORDER BY updated_at DESC
        """, (
            JobStatus.INTERRUPTED.value,
            JobStatus.FAILED.value,
            JobStatus.PAUSED.value
        ))
        
        return [cls._row_to_record(row) for row in cursor.fetchall()]
    
    @classmethod
    def get_all_jobs(
        cls,
        limit: int = 100,
        offset: int = 0,
        status_filter: Optional[List[JobStatus]] = None
    ) -> List[JobRecord]:
        """
        Get all jobs with optional filtering.
        
        Args:
            limit: Maximum number of jobs to return
            offset: Offset for pagination
            status_filter: Optional list of statuses to filter by
            
        Returns:
            List of JobRecords
        """
        conn = cls._get_connection()
        cursor = conn.cursor()
        
        if status_filter:
            placeholders = ','.join('?' * len(status_filter))
            status_values = [s.value for s in status_filter]
            cursor.execute(f"""
                SELECT * FROM jobs 
                WHERE status IN ({placeholders})
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, status_values + [limit, offset])
        else:
            cursor.execute("""
                SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?
            """, (limit, offset))
        
        return [cls._row_to_record(row) for row in cursor.fetchall()]
    
    @classmethod
    def delete_job(cls, job_id: str) -> bool:
        """
        Delete a job record.
        
        Args:
            job_id: The job ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        with cls._lock:
            conn = cls._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            conn.commit()
            
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted job: {job_id}")
            
            return deleted
    
    @classmethod
    def cleanup_old_jobs(cls, days: int = 30) -> int:
        """
        Clean up jobs older than specified days.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of jobs deleted
        """
        with cls._lock:
            conn = cls._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM jobs 
                WHERE created_at < datetime('now', ?)
                AND status IN (?, ?, ?)
            """, (
                f'-{days} days',
                JobStatus.COMPLETED.value,
                JobStatus.FAILED.value,
                JobStatus.STOPPED.value
            ))
            
            conn.commit()
            deleted = cursor.rowcount
            
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old jobs (older than {days} days)")
            
            return deleted


def check_and_recover_interrupted_jobs():
    """
    Check for and report interrupted jobs on startup.
    
    This should be called when the Flask app starts to detect
    any simulations that were interrupted by a server restart.
    
    Returns:
        List of interrupted job records
    """
    logger.info("Checking for interrupted simulation jobs...")
    interrupted = JobQueue.detect_interrupted_jobs()
    
    if interrupted:
        logger.warning(f"Found {len(interrupted)} interrupted jobs:")
        for job in interrupted:
            logger.warning(f"  - {job.job_id}: simulation={job.simulation_id}, "
                         f"last_round={job.checkpoint_round}")
    else:
        logger.info("No interrupted jobs found")
    
    return interrupted

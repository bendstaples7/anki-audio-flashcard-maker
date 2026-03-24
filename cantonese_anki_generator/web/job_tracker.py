"""
In-memory job tracker for async processing.

The /process endpoint kicks off work in a background thread and returns
a job_id immediately.  The frontend polls /process/status/<job_id>
until the job completes (or fails).
"""

import copy
import threading
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class Job:
    job_id: str
    status: str = "pending"          # pending | running | complete | failed
    stage: str = ""                  # human-readable current stage
    session_id: Optional[str] = None # set on completion
    error: Optional[str] = None      # set on failure
    created_at: datetime = field(default_factory=datetime.utcnow)
    total_terms: int = 0
    audio_duration: float = 0.0
    low_confidence_count: int = 0


class JobTracker:
    """Thread-safe store for background processing jobs."""

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self) -> Job:
        job = Job(job_id=str(uuid.uuid4()))
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.copy(job) if job else None

    def update_stage(self, job_id: str, stage: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.stage = stage
                job.status = "running"

    def complete(self, job_id: str, session_id: str,
                 total_terms: int, audio_duration: float,
                 low_confidence_count: int):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "complete"
                job.session_id = session_id
                job.total_terms = total_terms
                job.audio_duration = audio_duration
                job.low_confidence_count = low_confidence_count
                job.stage = "complete"

    def fail(self, job_id: str, error: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "failed"
                job.error = error
                job.stage = "failed"


# Singleton shared across the app
job_tracker = JobTracker()

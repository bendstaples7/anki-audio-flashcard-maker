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
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Default time-to-live for completed/failed jobs (seconds).
_DEFAULT_EXPIRY_SECONDS = 3600  # 1 hour


@dataclass
class Job:
    job_id: str
    status: str = "pending"          # pending | running | complete | failed
    stage: str = ""                  # human-readable current stage
    session_id: Optional[str] = None # set on completion
    error: Optional[str] = None      # set on failure
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[float] = None  # monotonic timestamp for TTL
    total_terms: int = 0
    audio_duration: float = 0.0
    low_confidence_count: int = 0


class JobTracker:
    """Thread-safe store for background processing jobs."""

    def __init__(self, expiry_seconds: int = _DEFAULT_EXPIRY_SECONDS):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._expiry_seconds = expiry_seconds
        # Start background cleaner daemon
        self._cleaner = threading.Thread(
            target=self._cleanup_loop, daemon=True
        )
        self._cleaner.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self) -> Job:
        job = Job(job_id=str(uuid.uuid4()))
        with self._lock:
            self._jobs[job.job_id] = job
        return copy.copy(job)

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
                job.completed_at = time.monotonic()

    def fail(self, job_id: str, error: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "failed"
                job.error = error
                job.stage = "failed"
                job.completed_at = time.monotonic()

    # ------------------------------------------------------------------
    # Background cleanup
    # ------------------------------------------------------------------

    def _cleanup_loop(self):
        """Periodically remove expired terminal jobs."""
        while True:
            time.sleep(min(self._expiry_seconds / 2, 300))
            self._purge_expired()

    def _purge_expired(self):
        now = time.monotonic()
        with self._lock:
            expired = [
                jid for jid, job in self._jobs.items()
                if job.completed_at is not None
                and (now - job.completed_at) > self._expiry_seconds
            ]
            for jid in expired:
                del self._jobs[jid]
        if expired:
            logger.debug("Purged %d expired jobs", len(expired))


# Singleton shared across the app
job_tracker = JobTracker()

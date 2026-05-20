from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class JobType(str, Enum):
    CIVIL        = "civil"
    ANTECEDENTES = "antecedentes"


class JobStatus(str, Enum):
    QUEUED    = "queued"
    RUNNING   = "running"
    DONE      = "done"
    ERROR     = "error"
    CANCELLED = "cancelled"


@dataclass
class Job:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    job_type: JobType = JobType.CIVIL
    status: JobStatus = JobStatus.QUEUED
    label: str = ""
    total: int = 0
    current: int = 0
    output_path: str = ""
    error_msg: str = ""

    @property
    def progress_pct(self) -> float:
        return (self.current / self.total * 100) if self.total > 0 else 0.0

    @property
    def is_active(self) -> bool:
        return self.status in (JobStatus.QUEUED, JobStatus.RUNNING)

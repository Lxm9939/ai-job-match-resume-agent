"""Base interface for low-frequency public job source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from src.schemas.models import CrawledJob, JobSearchPreference, JobSource


CRAWLER_USER_AGENT = (
    "AIJobMatchResumeAgent/3.0 "
    "(portfolio project; low-frequency public careers page access)"
)


class BaseJobSource(ABC):
    """Fetch normalized jobs from one explicitly configured public source."""

    @abstractmethod
    def fetch(
        self,
        source: JobSource,
        preference: JobSearchPreference,
        max_jobs: int,
    ) -> List[CrawledJob]:
        """Return normalized jobs without bypassing access controls."""


import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional


@dataclass
class CrawlJob:
    """Representa el estado de un job de crawling"""
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    start_url: str
    max_pages: int
    total_pages: int = 0
    pages_crawled: int = 0
    pages_ingested: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    @property
    def progress_percentage(self) -> float:
        """Calcula el porcentaje de progreso basado en páginas crawleadas vs max_pages"""
        if self.max_pages <= 0:
            return 0.0
        return round((self.pages_crawled / self.max_pages) * 100, 2)

    def to_dict(self) -> dict:
        """Convierte el job a un diccionario para respuestas JSON"""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "start_url": self.start_url,
            "max_pages": self.max_pages,
            "total_pages": self.total_pages,
            "pages_crawled": self.pages_crawled,
            "pages_ingested": self.pages_ingested,
            "progress_percentage": self.progress_percentage,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class CrawlJobManager:
    """
    Gestor de jobs de crawling en memoria (singleton).
    Thread-safe usando asyncio.Lock.
    """
    _instance: Optional["CrawlJobManager"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._jobs: Dict[str, CrawlJob] = {}
            cls._instance._instance_lock = asyncio.Lock()
        return cls._instance

    async def create_job(
        self,
        start_url: str,
        max_pages: int = 650,
        concurrency: int = 5
    ) -> CrawlJob:
        """Crea un nuevo job de crawling y lo almacena"""
        job_id = str(uuid.uuid4())
        job = CrawlJob(
            job_id=job_id,
            status="pending",
            start_url=start_url,
            max_pages=max_pages,
        )

        async with self._instance_lock:
            self._jobs[job_id] = job

        return job

    async def get_job(self, job_id: str) -> Optional[CrawlJob]:
        """Obtiene un job por su ID"""
        async with self._instance_lock:
            return self._jobs.get(job_id)

    async def update_status(
        self,
        job_id: str,
        status: Literal["pending", "running", "completed", "failed"]
    ) -> None:
        """Actualiza el estado de un job"""
        async with self._instance_lock:
            if job_id in self._jobs:
                self._jobs[job_id].status = status
                if status in ["completed", "failed"]:
                    self._jobs[job_id].completed_at = datetime.utcnow()

    async def update_progress(
        self,
        job_id: str,
        pages_crawled: Optional[int] = None,
        total_pages: Optional[int] = None
    ) -> None:
        """Actualiza el progreso de crawling"""
        async with self._instance_lock:
            if job_id in self._jobs:
                if pages_crawled is not None:
                    self._jobs[job_id].pages_crawled = pages_crawled
                if total_pages is not None:
                    self._jobs[job_id].total_pages = total_pages

    async def increment_ingested(self, job_id: str) -> None:
        """Incrementa el contador de páginas ingestadas"""
        async with self._instance_lock:
            if job_id in self._jobs:
                self._jobs[job_id].pages_ingested += 1

    async def add_error(self, job_id: str, error: str) -> None:
        """Agrega un error al job"""
        async with self._instance_lock:
            if job_id in self._jobs:
                self._jobs[job_id].errors.append(error)

    async def list_jobs(self, limit: int = 20) -> List[CrawlJob]:
        """Lista los últimos N jobs (ordenados por fecha de inicio)"""
        async with self._instance_lock:
            sorted_jobs = sorted(
                self._jobs.values(),
                key=lambda j: j.started_at,
                reverse=True
            )
            return sorted_jobs[:limit]


# Singleton global
job_manager = CrawlJobManager()

import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from app.services.crawler import crawl_and_ingest
from app.services.repair import repair
from app.core.job_manager import job_manager
from app.core.config import settings

router = APIRouter()


class CrawlRequest(BaseModel):
    """Request para iniciar un crawl"""
    start_url: HttpUrl
    max_pages: int = 650
    concurrency: int = 5
    out_dir: Optional[str] = None


class CrawlResponse(BaseModel):
    """Response inmediata al iniciar un crawl"""
    job_id: str
    status: str
    message: str
    start_url: str


class JobStatusResponse(BaseModel):
    """Response con el estado detallado de un job"""
    job_id: str
    status: str
    start_url: str
    max_pages: int
    total_pages: int
    pages_crawled: int
    pages_ingested: int
    progress_percentage: float
    errors: List[str]
    started_at: Optional[str]
    completed_at: Optional[str]


class RepairBody(BaseModel):
    """Request para reparar/re-scrapear"""
    start_url: str | None = None
    out_dir: str | None = None
    concurrency: int = 5


async def _run_crawl_background(
    job_id: str,
    start_url: str,
    out_dir: str,
    max_pages: int,
    concurrency: int
):
    """Función que ejecuta el crawl en background"""
    try:
        await crawl_and_ingest(
            start_url=start_url,
            out_dir=out_dir,
            max_pages=max_pages,
            concurrency=concurrency,
            job_manager=job_manager,
            job_id=job_id,
            site_profile="med_unne"  # Usar perfil optimizado
        )
    except Exception as e:
        print(f"Error en background task: {e}")
        await job_manager.update_status(job_id, "failed")
        await job_manager.add_error(job_id, str(e))


@router.post("/crawl", response_model=CrawlResponse)
async def start_crawl(body: CrawlRequest, background_tasks: BackgroundTasks):
    """
    Inicia un crawl en background y retorna inmediatamente.

    El crawl se ejecuta de forma asíncrona y puedes consultar su progreso
    usando el endpoint GET /crawl/status/{job_id}
    """
    # Crear job
    job = await job_manager.create_job(
        start_url=str(body.start_url),
        max_pages=body.max_pages,
        concurrency=body.concurrency
    )

    # Determinar directorio de salida
    out_dir = body.out_dir or settings.SITE_MD_DIR

    # Agregar tarea en background
    background_tasks.add_task(
        _run_crawl_background,
        job_id=job.job_id,
        start_url=str(body.start_url),
        out_dir=out_dir,
        max_pages=body.max_pages,
        concurrency=body.concurrency
    )

    return CrawlResponse(
        job_id=job.job_id,
        status="pending",
        message="Crawling iniciado en background. Usa GET /crawl/status/{job_id} para ver progreso.",
        start_url=str(body.start_url)
    )


@router.get("/crawl/status/{job_id}", response_model=JobStatusResponse)
async def get_crawl_status(job_id: str):
    """
    Consulta el estado y progreso de un job de crawling.

    Retorna información detallada incluyendo:
    - Porcentaje de progreso
    - Páginas crawleadas e ingestadas
    - Errores (si los hay)
    - Timestamps
    """
    job = await job_manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} no encontrado")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        start_url=job.start_url,
        max_pages=job.max_pages,
        total_pages=job.total_pages,
        pages_crawled=job.pages_crawled,
        pages_ingested=job.pages_ingested,
        progress_percentage=job.progress_percentage,
        errors=job.errors,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None
    )


@router.get("/crawl/jobs")
async def list_jobs(limit: int = 20):
    """
    Lista los últimos N jobs de crawling (útil para debugging).

    Args:
        limit: Número máximo de jobs a retornar (default: 20)
    """
    jobs = await job_manager.list_jobs(limit=limit)
    return [job.to_dict() for job in jobs]


@router.post("/repair")
async def repair_route(body: RepairBody):
    """
    Endpoint legacy para reparar/re-scrapear.
    Se mantiene por compatibilidad.
    """
    return await repair(
        folder=body.out_dir,
        start_url=body.start_url,
        concurrency=body.concurrency
    )
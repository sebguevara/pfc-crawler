from pathlib import Path
from typing import Optional
from app.crawler.models import CrawlSettings
from app.crawler.writers import MarkdownWriter
from app.repositories.crawler import crawl_site
from app.services.ingestion import ingest_page_realtime
from app.core.job_manager import CrawlJobManager

async def crawl_and_ingest(
    start_url: str,
    out_dir: str,
    max_pages: int = 600,
    concurrency: int = 5,
    job_manager: Optional[CrawlJobManager] = None,
    job_id: Optional[str] = None,
    site_profile: str = "med_unne"
):
    """
    Crawlea un sitio e ingesta cada página en tiempo real a la base de datos vectorial.

    Args:
        start_url: URL inicial para comenzar el crawl
        out_dir: Directorio donde guardar los archivos .md
        max_pages: Número máximo de páginas a crawlear
        concurrency: Número de workers concurrentes
        job_manager: Manager de jobs para actualizar progreso
        job_id: ID del job actual
        site_profile: Perfil de crawling a usar (default: med_unne)
    """
    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    writer = MarkdownWriter(out_dir_path)
    crawl_cfg = CrawlSettings(
        start_url=start_url,
        out_dir=out_dir_path,
        max_pages=max_pages,
        concurrency=concurrency,
        site_profile=site_profile
    )

    # Actualizar estado del job a "running"
    if job_manager and job_id:
        await job_manager.update_status(job_id, "running")

    try:
        # Crawl con ingestion en tiempo real
        res = await crawl_site(
            cfg=crawl_cfg,
            writer=writer,
            job_manager=job_manager,
            job_id=job_id,
            ingest_callback=ingest_page_realtime  # Callback de ingestion
        )

        # Marcar como completado
        if job_manager and job_id:
            await job_manager.update_status(job_id, "completed")

        return res

    except Exception as e:
        # Marcar como fallido
        if job_manager and job_id:
            await job_manager.update_status(job_id, "failed")
            await job_manager.add_error(job_id, f"Fatal error: {str(e)}")
        raise
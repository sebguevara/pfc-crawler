from pathlib import Path

from app.crawler.models import CrawlSettings
from app.repositories.repair_and_rescrape import rescrape_title_url_only

async def repair(folder: Path, start_url: str, concurrency: int):
    folder_path = Path(folder)
    cfg = CrawlSettings(
        start_url=start_url,
        out_dir=folder_path,
        concurrency=concurrency,
        max_pages=1,
    )

    result = await rescrape_title_url_only(
        folder=cfg.out_dir,
        cfg=cfg,
        concurrency=concurrency,
        do_ingest=True,
    )
    return result

    
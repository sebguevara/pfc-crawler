from pathlib import Path
from app.crawler.models import CrawlSettings
from app.crawler.writers import MarkdownWriter
from app.repositories.crawler import crawl_site

async def crawl_and_ingest(start_url: str, out_dir: str, max_pages: int = 600, concurrency: int = 5):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    writer = MarkdownWriter(out_dir)
    crawl_cfg = CrawlSettings(start_url, out_dir, max_pages, concurrency)
    res = await crawl_site(crawl_cfg, writer)
    return res
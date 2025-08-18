import asyncio
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler
from app.crawler.models import CrawlSettings, PageArtifact
from app.crawler.selectors import build_run_config
from app.crawler.linkers import extract_links, same_site, is_html_like
from app.crawler.naming import name_from_url
from app.crawler.writers import MarkdownWriter

async def crawl_site(cfg: CrawlSettings, writer: MarkdownWriter) -> dict:
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    base_host = (urlparse(cfg.start_url).hostname or "").lower().lstrip("www.")
    seen, enq = set(), set()
    q: asyncio.Queue[str] = asyncio.Queue()
    await q.put(cfg.start_url); enq.add(cfg.start_url)
    sem = asyncio.Semaphore(cfg.concurrency)

    async with AsyncWebCrawler() as crawler:
        async def worker():
            while True:
                url = await q.get()
                try:
                    if url in seen or len(seen) >= cfg.max_pages:
                        continue
                    async with sem:
                        r = await crawler.arun(url, config=build_run_config(cfg))
                    seen.add(url)
                    md = (getattr(r.markdown,"fit_markdown",None)
                          or getattr(r.markdown,"raw_markdown",None)
                          or r.markdown or "")
                    art = PageArtifact(url=url, title=(r.metadata or {}).get("title",""), markdown=md)
                    writer.write(name_from_url(url), art)

                    for link in extract_links(r.html or "", url):
                        if is_html_like(link) and same_site(link, base_host) and link not in seen and link not in enq:
                            await q.put(link); enq.add(link)
                finally:
                    q.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(cfg.concurrency)]
        await q.join()
        for w in workers: w.cancel()
    return {"pages": len(seen), "out_dir": str(cfg.out_dir.resolve())}

import asyncio
from typing import Callable, Awaitable, Optional
from pathlib import Path
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler
from app.crawler.models import CrawlSettings, PageArtifact
from app.crawler.selectors import build_run_config
from app.crawler.linkers import extract_links, same_site, is_html_like
from app.crawler.naming import name_from_url
from app.crawler.writers import MarkdownWriter

async def crawl_site(
    cfg: CrawlSettings,
    writer: MarkdownWriter,
    job_manager: Optional[any] = None,
    job_id: Optional[str] = None,
    ingest_callback: Optional[Callable[[str, str, str, str], Awaitable[None]]] = None
) -> dict:
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    base_host = (urlparse(cfg.start_url).hostname or "").lower().lstrip("www.")
    seen, enq = set(), set()
    q: asyncio.Queue[str] = asyncio.Queue()
    await q.put(cfg.start_url); enq.add(cfg.start_url)
    sem = asyncio.Semaphore(cfg.concurrency)

    async with AsyncWebCrawler() as crawler:
        async def worker():
            MAX_RETRIES = 3
            while True:
                url = await q.get()
                try:
                    if url in seen or len(seen) >= cfg.max_pages:
                        continue

                    # Reintentos con exponential backoff
                    retry_count = 0
                    crawl_success = False
                    r = None

                    while retry_count < MAX_RETRIES and not crawl_success:
                        try:
                            async with sem:
                                r = await crawler.arun(url, config=build_run_config(cfg))
                            crawl_success = True
                        except Exception as e:
                            retry_count += 1
                            if retry_count >= MAX_RETRIES:
                                error_msg = f"Failed after {MAX_RETRIES} retries: {url} - {str(e)}"
                                print(f"❌ {error_msg}")
                                if job_manager and job_id:
                                    await job_manager.add_error(job_id, error_msg)
                                break
                            await asyncio.sleep(2 ** retry_count)  # Exponential backoff

                    if not crawl_success or not r:
                        continue

                    seen.add(url)

                    # Extraer markdown
                    md = (getattr(r.markdown,"fit_markdown",None)
                          or getattr(r.markdown,"raw_markdown",None)
                          or r.markdown or "")

                    # Crear artifact y escribir archivo
                    art = PageArtifact(url=url, title=(r.metadata or {}).get("title",""), markdown=md)
                    file_path = writer.write(name_from_url(url), art)

                    # Actualizar progreso de crawling
                    if job_manager and job_id:
                        await job_manager.update_progress(job_id, pages_crawled=len(seen))

                    # NUEVO: Ingestar en tiempo real
                    if ingest_callback:
                        try:
                            await ingest_callback(
                                url=art.url,
                                title=art.title,
                                markdown_content=art.markdown or "",
                                file_path=str(file_path)
                            )
                            if job_manager and job_id:
                                await job_manager.increment_ingested(job_id)
                        except Exception as e:
                            error_msg = f"Error ingesting {url}: {str(e)}"
                            print(f"⚠️  {error_msg}")
                            if job_manager and job_id:
                                await job_manager.add_error(job_id, error_msg)

                    # Extraer links internos
                    for link in extract_links(r.html or "", url):
                        if is_html_like(link) and same_site(link, base_host) and link not in seen and link not in enq:
                            await q.put(link); enq.add(link)

                except Exception as e:
                    error_msg = f"Unexpected error processing {url}: {str(e)}"
                    print(f"❌ {error_msg}")
                    if job_manager and job_id:
                        await job_manager.add_error(job_id, error_msg)
                finally:
                    q.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(cfg.concurrency)]
        await q.join()
        for w in workers: w.cancel()
    return {"pages": len(seen), "out_dir": str(cfg.out_dir.resolve())}

import os, re, asyncio, hashlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, urljoin, urldefrag, unquote

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter

MEDIA_EXTS = {
    ".jpg",".jpeg",".png",".gif",".webp",".svg",".ico",
    ".mp4",".mp3",".pdf",".zip",".rar",".7z",".gz",".css",".js",".woff",".woff2",".ttf"
}

class LinkExtractor(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=="a":
            for k,v in attrs:
                if k.lower()=="href" and v: self.links.append(v)

def same_site(url, base_host):
    host = urlparse(url).hostname or ""
    return host.lower().lstrip("www.").endswith(base_host)

def sanitize_slug(s:str)->str:
    s = unquote(s)
    s = re.sub(r"[^\w\-]+","-",s, flags=re.UNICODE).strip("-").lower()
    return s or "index"

def choose_name(u:str)->str:
    p = urlparse(u)
    seg = (p.path.rstrip("/") or "/").split("/")[-1]
    base,_ = os.path.splitext(seg)
    if not base: base="index"
    h = hashlib.sha1(u.encode("utf-8")).hexdigest()[:8]
    return f"{sanitize_slug(base)}-{h}.md"

def is_html_like(u:str)->bool:
    path = urlparse(u).path.lower()
    _,ext = os.path.splitext(path)
    return (ext=="" or ext==".html") and ext not in MEDIA_EXTS

def extract_links(raw_html:str, base_url:str):
    p = LinkExtractor(); p.feed(raw_html or "")
    out=[]
    for href in p.links:
        absu = urljoin(base_url, href)
        absu,_ = urldefrag(absu)
        if absu.startswith(("http://","https://")): out.append(absu)
    return out

async def crawl_site(start_url:str, out_dir:Path, max_pages=200, concurrency=5):
    out_dir.mkdir(parents=True, exist_ok=True)
    base_host = (urlparse(start_url).hostname or "").lower().lstrip("www.")
    seen, enq = set(), set()
    q: asyncio.Queue[str] = asyncio.Queue()
    await q.put(start_url); enq.add(start_url)

    prune = PruningContentFilter(threshold=0.3, threshold_type="dynamic", min_word_threshold=1)
    mdgen = DefaultMarkdownGenerator(content_filter=prune)

    run_cfg = CrawlerRunConfig(
        target_elements=[
            "main","article","#content",".entry-content",
            ".elementor-location-single",".elementor-widget-theme-post-content",
            ".e-n-tabs-content",
            ".elementor-tab-content",
            ".elementor-widget-text-editor",
        ],
        excluded_tags=["header","footer","nav","form","aside"],
        excluded_selector=(
            "#masthead, #colophon, .site-header, .site-footer, .widget, .sidebar, "
            ".breadcrumbs, .menu, .elementor-location-header, .elementor-location-footer, "
            ".elementor-nav-menu, .elementor-menu, .elementor-icon-list, "
            ".elementor-widget-social-icons, .elementor-share-buttons"
        ),
        exclude_social_media_links=False,
        exclude_external_images=True,
        word_count_threshold=0,
        markdown_generator=mdgen,
        cache_mode=CacheMode.BYPASS,
    )

    sem = asyncio.Semaphore(concurrency)

    async with AsyncWebCrawler() as crawler:
        async def worker():
            while True:
                url = await q.get()
                try:
                    if url in seen or len(seen) >= max_pages:
                        continue
                    async with sem:
                        r = await crawler.arun(url, config=run_cfg)
                    seen.add(url)

                    md = (getattr(r.markdown, "fit_markdown", None)
                          or getattr(r.markdown, "raw_markdown", None)
                          or r.markdown or "")
                    name = choose_name(url)
                    title = (r.metadata or {}).get("title") or ""
                    content = f"---\ntitle: {title}\nurl: {url}\n---\n\n{md}"
                    (out_dir / name).write_text(content, encoding="utf-8")

                    for link in extract_links(r.html or "", url):
                        if is_html_like(link) and same_site(link, base_host) and link not in seen and link not in enq:
                            await q.put(link); enq.add(link)
                finally:
                    q.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await q.join()
        for w in workers: w.cancel()
    return {"pages": len(seen), "out_dir": str(out_dir.resolve())}


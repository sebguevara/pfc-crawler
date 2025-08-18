import asyncio
import datetime
import re
from pathlib import Path
from typing import List, Tuple

import httpx
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler

from app.crawler.models import CrawlSettings
from app.crawler.selectors import build_run_config
from app.repositories.md_parser import read_md, split_by_headings
from app.repositories.chunker import make_chunks
from app.repositories.embedding import embed_texts
from app.repositories.upserts_bulk import (
    upsert_source,
    upsert_document,
    bulk_upsert_chunks,
)
from app.core.config import settings
from app.db.engine import get_session
from app.utils.urls import canonicalize, path_segments, page_type_from_path, url_hash


# ============ Helpers frontmatter / escritura ============

def _yaml_quote(s: str | None) -> str:
    if not s:
        return '""'
    s = str(s).replace('"', "'").strip()
    return f'"{s}"'

def _build_markdown_file(title: str, url: str, body_md: str) -> str:
    fm = [
        "---",
        f"title: {_yaml_quote(title)}",
        f"url: {url}",
        f"fetched_at: {datetime.datetime.utcnow().isoformat()}Z",
        "---",
        "",
    ]
    return "\n".join(fm) + (body_md or "")

def _is_candidate_md(p: Path) -> Tuple[bool, str, str]:
    """
    Candidato si: HAY url y el CUERPO está vacío (ignoramos title).
    Devuelve (es_candidato, title, url).
    """
    try:
        title, url, body, _ = read_md(p)
        body_stripped = (body or "").strip()
        if url and body_stripped == "":
            return True, (title or ""), url
        return False, (title or ""), (url or "")
    except Exception:
        return False, "", ""


# ============ Crawl principal + Fallback ============

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

async def _fetch_markdown(
    crawler: AsyncWebCrawler,
    url: str,
    cfg: CrawlSettings,
    attempts: int = 2,
) -> Tuple[str, str, str]:
    """
    Intenta con Crawl4AI (Playwright). Devuelve (title, markdown, html).
    Puede devolver markdown vacío; HTML suele venir.
    """
    delay = 1.2
    for _ in range(attempts):
        try:
            r = await crawler.arun(url, config=build_run_config(cfg))
            md = (
                getattr(r.markdown, "fit_markdown", None)
                or getattr(r.markdown, "raw_markdown", None)
                or r.markdown
                or ""
            )
            title = (r.metadata or {}).get("title", "") or ""
            html = r.html or ""
            return title, md, html
        except Exception:
            await asyncio.sleep(delay)
            delay *= 1.8
    return "", "", ""  # seguimos con fallback

def _html_to_md_simple(html: str) -> str:
    """HTML -> Markdown simple (sirve p/HTML viejos y categorías WP)."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()

    # Listados WordPress (archive/category)
    articles = soup.select("article")
    if articles:
        parts = []
        for a in articles:
            h = a.select_one("h1, h2, h3, .entry-title, .post-title")
            if h:
                parts.append(f"## {h.get_text(' ', strip=True)}")
            b = a.select_one(".entry-content, .post-excerpt, p")
            if b:
                parts.append(b.get_text("\n", strip=True))
        if parts:
            return "\n\n".join(parts).strip()

    # Headings -> markdown
    for n in range(6, 0, -1):
        for h in soup.select(f"h{n}"):
            text = h.get_text(" ", strip=True)
            h.replace_with(soup.new_string(f"{'#'*n} {text}\n\n"))

    # Links -> [texto](url)
    for a in soup.find_all("a"):
        txt = a.get_text(" ", strip=True)
        href = a.get("href") or ""
        repl = f"[{txt}]({href})" if txt else href
        a.replace_with(soup.new_string(repl))

    # Listas
    for li in soup.find_all("li"):
        li.insert_before(soup.new_string("- "))
        li.append(soup.new_string("\n"))

    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

async def _http_fallback_markdown(url: str, timeout_s: int = 30) -> Tuple[str, str]:
    """HTTP plano con httpx + BS4 -> Markdown simple (detecta encoding)."""
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    async with httpx.AsyncClient(follow_redirects=True, headers=headers, http2=False, timeout=timeout_s) as client:
        resp = await client.get(url)
        enc = None
        ctype = resp.headers.get("content-type", "")
        m = re.search(r"charset=([\w\-]+)", ctype, re.I)
        if m:
            enc = m.group(1)
        text = resp.content.decode(enc or resp.encoding or "latin-1", errors="ignore")
        title = ""
        mt = re.search(r"<title>(.*?)</title>", text, re.I | re.S)
        if mt:
            title = re.sub(r"\s+", " ", mt.group(1)).strip()
        md = _html_to_md_simple(text)
        return title, md


# ============ Ingesta selectiva (DB + embeddings) ============

def ingest_selected_files(files: List[Path]) -> int:
    total_chunks = 0
    with get_session() as s:
        for p in files:
            title, url, body, content_hash = read_md(p)
            if not url:
                continue

            can = canonicalize(url)
            segs = path_segments(can)
            ptype = page_type_from_path(segs)
            domain = can.split("/")[2]

            source_id = upsert_source(domain, s)
            doc_data = dict(
                source_id=source_id,
                url=url,
                canonical_url=can,
                url_hash=url_hash(can),
                path_segments=segs,
                path_depth=len(segs),
                title=title,
                page_type=ptype,
                language="es",
                fetched_at=datetime.datetime.utcnow(),
                status_code=200,
                content_len=len(body or ""),
                content_hash=content_hash,
                metadata={},
            )
            doc_id = upsert_document(doc_data, s)

            chunks_raw = []
            idx = 0
            for heading_path, start, end, seg_text in split_by_headings(body or ""):
                for piece, tok_count in make_chunks(seg_text, heading_path, start):
                    meta = {
                        "url": can,
                        "title": title,
                        "page_type": ptype,
                        "path_segments": segs,
                        "path_depth": len(segs),
                        "heading_path": heading_path,
                    }
                    chunks_raw.append(
                        {
                            "chunk_index": idx,
                            "start_char": start,
                            "end_char": end,
                            "heading_path": heading_path,
                            "anchor": None,
                            "text": piece,
                            "text_tokens": tok_count,
                            "is_boilerplate": False,
                            "embedding_model": settings.OPENAI_EMBEDDING_MODEL,
                            "embedding": [],
                            "metadata": meta,
                        }
                    )
                    idx += 1

            if chunks_raw:
                texts = [c["text"] for c in chunks_raw]
                embs = embed_texts(texts)
                for c, e in zip(chunks_raw, embs):
                    c["embedding"] = e
                total_chunks += bulk_upsert_chunks(doc_id, chunks_raw, s)

        s.commit()
    return total_chunks


# ============ Orquestador principal ============

async def rescrape_title_url_only(
    folder: str | Path,
    cfg: CrawlSettings,
    concurrency: int = 3,
    do_ingest: bool = False,
) -> dict:
    """
    Recorre TODOS los .md en 'folder', toma los que tienen URL y CUERPO vacío,
    re-scrapea (Playwright; si vacío -> fallback HTTP+BS4), sobrescribe el .md y (opcional) ingesta.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    # 1) Candidatos (AHORA ignora title)
    candidates: List[Tuple[Path, str]] = []
    for p in sorted(folder.glob("*.md")):
        is_candidate, _, _url = _is_candidate_md(p)
        if is_candidate and _url:
            candidates.append((p, _url))

    if not candidates:
        return {
            "scanned": len(list(folder.glob("*.md"))),
            "rescanned": 0,
            "ok": 0,
            "failed": 0,
            "errors": [],
            "ingested": 0,
        }

    sem = asyncio.Semaphore(concurrency)
    results = []

    async with AsyncWebCrawler() as crawler:
        async def handle(p: Path, url: str):
            async with sem:
                try:
                    # 2) Playwright
                    title, md, html = await _fetch_markdown(crawler, url, cfg, attempts=2)

                    # 3) Fallback si quedó vacío
                    if (md or "").strip() == "":
                        t2, md2 = await _http_fallback_markdown(url)
                        title = title or t2
                        md = md2

                    if (md or "").strip() == "":
                        return ("fail", p, url, "empty_after_rescrape_and_fallback")

                    # 4) Sobrescribir el mismo archivo
                    content = _build_markdown_file(title or p.stem, url, md)
                    p.write_text(content, encoding="utf-8")
                    return ("ok", p, url, "")
                except Exception as e:
                    return ("fail", p, url, str(e))

        tasks = [asyncio.create_task(handle(p, url)) for (p, url) in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    ok_files: List[Path] = []
    ok = failed = 0
    errors: list[dict] = []

    for r in results:
        if isinstance(r, tuple):
            st, p, url, err = r
            if st == "ok":
                ok += 1
                ok_files.append(p)
            else:
                failed += 1
                errors.append({"file": str(p), "url": url, "error": err})
        else:
            failed += 1
            errors.append({"error": str(r)})

    ingested = 0
    if do_ingest and ok_files:
        ingested = ingest_selected_files(ok_files)

    return {
        "scanned": len(list(folder.glob("*.md"))),
        "rescanned": len(candidates),
        "ok": ok,
        "failed": failed,
        "errors": errors,
        "ingested": ingested,
    }

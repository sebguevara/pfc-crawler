import frontmatter, re, hashlib
from pathlib import Path

def _sha1(txt: str) -> str:
    return hashlib.sha1(txt.encode("utf-8")).hexdigest()

def read_md(p: Path):
    raw = p.read_text(encoding="utf-8")

    try:
        post = frontmatter.loads(raw)
        meta = post.metadata or {}
        title = meta.get("title")
        url = meta.get("url") or meta.get("canonical_url")
        body = post.content or ""
        ch = meta.get("content_hash") or _sha1(body)
        return title, url, body, ch
    except Exception:
        pass

    fm = {}
    body = raw
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", raw, flags=re.S)
    if m:
        fm_text = m.group(1)
        body = raw[m.end():]
        for line in fm_text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if ":" in s:
                k, v = s.split(":", 1)
                fm[k.strip()] = v.strip().strip("'").strip('"')

    title = fm.get("title")
    url = fm.get("url") or fm.get("canonical_url")
    ch = fm.get("content_hash") or _sha1(body)
    return title, url, body, ch

HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$", re.M)

def split_by_headings(md: str):
    positions = [(m.start(), m.end(), len(m.group(1)), m.group(2).strip()) for m in HEADING_RE.finditer(md)]
    if not positions:
        return [ ([], 0, len(md), md) ]
    segments=[]
    for i,(s,e,level,text) in enumerate(positions):
        end = positions[i+1][0] if i+1<len(positions) else len(md)
        seg = md[e:end].strip()
        segments.append( ([text], e, end, seg) )
    return segments

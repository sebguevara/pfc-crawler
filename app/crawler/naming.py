import re, hashlib
from urllib.parse import urlparse, unquote

def sanitize_slug(s: str) -> str:
    s = unquote(s)
    s = re.sub(r"[^\w\-]+","-",s).strip("-").lower()
    return s or "index"

def name_from_url(u: str) -> str:
    p = urlparse(u)
    seg = (p.path.rstrip("/") or "/").split("/")[-1]
    base = seg or "index"
    slug = sanitize_slug(base)
    h = hashlib.sha1(u.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{h}.md"

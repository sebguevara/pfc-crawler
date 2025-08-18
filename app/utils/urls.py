from urllib.parse import urlparse
import hashlib

def canonicalize(url: str) -> str:
    u = urlparse(url)
    path = u.path.rstrip("/")
    return f"{u.scheme}://{u.netloc}{path or '/'}"

def path_segments(url: str) -> list[str]:
    return [s for s in urlparse(url).path.split('/') if s]

def page_type_from_path(segs: list[str]) -> str | None:
    for key in ("asignatura","catedra","noticia","alumnos","academica","posgrado"):
        if key in segs: return key
    return None

def url_hash(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()

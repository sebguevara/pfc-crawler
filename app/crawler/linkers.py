import os
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin, urldefrag
from typing import List

MEDIA_EXTS = {".jpg",".jpeg",".png",".gif",".webp",".svg",".ico",
              ".mp4",".mp3",".pdf",".zip",".rar",".7z",".gz",".css",".js",".woff",".woff2",".ttf"}

class LinkExtractor(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=="a":
            for k,v in attrs:
                if k.lower()=="href" and v: self.links.append(v)

def same_site(url: str, base_host: str) -> bool:
    host = urlparse(url).hostname or ""
    return host.lower().lstrip("www.").endswith(base_host)

def is_html_like(u: str) -> bool:
    path = urlparse(u).path.lower()
    _, ext = os.path.splitext(path)
    return (ext=="" or ext==".html") and ext not in MEDIA_EXTS

def extract_links(raw_html: str, base_url: str) -> List[str]:
    p = LinkExtractor(); p.feed(raw_html or "")
    out=[]
    for href in p.links:
        absu = urljoin(base_url, href)
        absu,_ = urldefrag(absu)
        if absu.startswith(("http://","https://")): out.append(absu)
    return out

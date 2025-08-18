from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from crawl4ai import CrawlerRunConfig

@dataclass
class CrawlSettings:
    start_url: str
    out_dir: Path
    max_pages: int = 600
    concurrency: int = 5
    bypass_cache: bool = True
    site_profile: str = "wordpress_elementor"

RunConfigFactory = Callable[[CrawlSettings], CrawlerRunConfig]

@dataclass
class PageArtifact:
    url: str
    title: str
    markdown: str
    html: Optional[str] = None

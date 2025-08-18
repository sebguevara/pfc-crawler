from pathlib import Path
from .models import PageArtifact

class MarkdownWriter:
    def __init__(self, out_dir: Path): 
        self.out_dir = out_dir

    def write(self, filename: str, art: PageArtifact) -> Path:
        content = f"---\ntitle: {art.title}\nurl: {art.url}\n---\n\n{art.markdown or ''}"
        path = self.out_dir / filename
        path.write_text(content, encoding="utf-8")
        return path

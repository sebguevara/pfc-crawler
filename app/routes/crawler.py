from fastapi import APIRouter
from pydantic import BaseModel
from app.services.crawler import crawl_and_ingest
from app.services.repair import repair

router = APIRouter()

class Body(BaseModel):
    start_url: str | None = None
    out_dir: str | None = None
    max_pages: int = 650
    concurrency: int = 5

@router.post("/crawl")
async def crawl_and_ingest_route(body: Body):
    return await crawl_and_ingest(
        start_url=body.start_url or "",
        out_dir=body.out_dir or "site_md",
        max_pages=body.max_pages,
        concurrency=body.concurrency
    )

@router.post("/repair")
async def repair_route(body: Body):
    return await repair(
        folder=body.out_dir,
        start_url=body.start_url,
        concurrency=body.concurrency
    )
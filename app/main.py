from fastapi import Depends, FastAPI
from app.routes.crawler import router as crawler_router
from app.routes.rag import router as rag_router
from app.core.dependencies import get_rag_service

app = FastAPI()
app.include_router(crawler_router, prefix="/api")
app.include_router(rag_router, prefix="/api", dependencies=[Depends(get_rag_service)])


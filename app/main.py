from fastapi import FastAPI
from app.routes.crawler import router as crawler_router
from app.routes.rag import router as rag_router

app = FastAPI()
app.include_router(crawler_router, prefix="/api")
app.include_router(rag_router, prefix="/api")


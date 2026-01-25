from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from app.routes.rag import router as rag_router
from app.routes.crawler import router as crawler_router
from app.core.session_manager import session_manager


# Lifecycle manager para iniciar/detener tareas de background
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Iniciar tarea de limpieza de sesiones
    cleanup_task = asyncio.create_task(session_manager.start_cleanup_task())
    print("✅ Gestor de sesiones iniciado - Limpieza automática cada 10 min")

    yield

    # Shutdown: Cancelar tarea de limpieza
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        print("🛑 Gestor de sesiones detenido")


app = FastAPI(
    title="API Medicina UNNE - RAG",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag_router, prefix="/api", tags=["RAG"])
app.include_router(crawler_router, prefix="/api", tags=["Crawler"])

@app.get("/")
def health_check():
    return {"status": "online", "sistema": "RAG Medicina UNNE"}
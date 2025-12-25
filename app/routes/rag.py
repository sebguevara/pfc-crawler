from fastapi import APIRouter, Depends
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from app.services.rag import RAGService
from app.core.dependencies import get_rag_service

router = APIRouter(prefix="/rag", tags=["RAG"])

class QueryRequest(BaseModel):
    query: str

async def stream_generator(response_stream):
    for token in response_stream.response_gen:
        yield token

@router.post("/chat")
async def chat_with_rag(
    request: QueryRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    response_stream = rag_service.ask(request.query)
    return StreamingResponse(stream_generator(response_stream), media_type="text/plain")
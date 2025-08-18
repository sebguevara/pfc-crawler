from fastapi import APIRouter
from pydantic import BaseModel
from app.services.rag import retrieval_app

router = APIRouter(prefix="/rag", tags=["rag"])

class KBQuery(BaseModel):
    query: str
    k: int | None = 5

@router.post("/kb")
def kb_search_route(payload: KBQuery):
    state = retrieval_app.invoke({"question": payload.query, "k": payload.k or 5})
    return {"results": state["results"]}
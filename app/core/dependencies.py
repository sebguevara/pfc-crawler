from app.core.config import settings
from app.db.postgres_store import PostgresVectorStore
from app.services.rag import RAGService
from llama_index.core import Settings as LlamaSettings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

LlamaSettings.llm = OpenAI(model=settings.llm_model)
LlamaSettings.embed_model = OpenAIEmbedding(model=settings.embedding_model)

vector_store_instance = PostgresVectorStore()
rag_service_instance = RAGService(vector_store=vector_store_instance)

def get_rag_service() -> RAGService:
    return rag_service_instance
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.vector_stores import PGVectorStore
from llama_index.core.schema import BaseNode

from app.db.interfaces import VectorStoreInterface
from app.core.config import settings

class PostgresVectorStore(VectorStoreInterface):
    def __init__(self):
        vector_store = PGVectorStore.from_params(
            connection_string=settings.database_url,
            table_name=settings.db_table_name,
            embed_dim=settings.embedding_dim,
        )
        self._index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

    def get_index(self) -> VectorStoreIndex:
        return self._index
    
    def insert_nodes(self, nodes: list[BaseNode]):
        self._index.insert_nodes(nodes)
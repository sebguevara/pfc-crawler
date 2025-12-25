from app.db.interfaces import VectorStoreInterface

class RAGService:
    def __init__(self, vector_store: VectorStoreInterface):
        self.index = vector_store.get_index()
        self.chat_engine = self.index.as_chat_engine(
            chat_mode="condense_plus_context", 
            verbose=False
        )

    def ask(self, query: str):
        return self.chat_engine.stream_chat(query)
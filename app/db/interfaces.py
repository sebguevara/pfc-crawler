from abc import ABC, abstractmethod
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import BaseNode

class VectorStoreInterface(ABC):
    @abstractmethod
    def get_index(self) -> VectorStoreIndex:
        """Devuelve la instancia del índice de LlamaIndex."""
        pass
    
    @abstractmethod
    def insert_nodes(self, nodes: list[BaseNode]):
        """Inserta nodos (documentos procesados) en el índice."""
        pass
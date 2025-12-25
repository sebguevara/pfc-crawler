import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from app.db.postgres_store import PostgresVectorStore
from app.core.dependencies import LlamaSettings

def run_indexing():
    print("🚀 Iniciando pipeline de indexación...")
    
    documents = SimpleDirectoryReader("./data").load_data()
    print(f"📂 Se cargaron {len(documents)} documentos.")

    node_parser = SentenceSplitter(chunk_size=512)
    nodes = node_parser.get_nodes_from_documents(documents)
    print(f"✂️ Documentos divididos en {len(nodes)} nodos.")

    print("🧠 Conectando a la base de datos e insertando nodos...")
    vector_store = PostgresVectorStore()
    vector_store.insert_nodes(nodes)

    print("✅ ¡Indexación completada!")

if __name__ == "__main__":
    run_indexing()
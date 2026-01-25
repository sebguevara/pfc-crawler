import os
import re
import asyncio
import hashlib
from datetime import datetime
from typing import List, Dict, Any
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.database import async_session_maker, init_rag_db
from app.models.rag import Document, Chunk
from app.repositories.rag_repository import RagRepository

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def get_embedding(text: str) -> List[float]:
    """
    Genera embeddings con text-embedding-3-large usando shortening a 1536 dimensiones.
    Esto mantiene compatibilidad con el esquema de BD mientras usa el modelo mejorado.
    """
    text = text.replace("\n", " ")
    try:
        resp = await client.embeddings.create(
            input=[text],
            model=settings.OPENAI_EMBEDDING_MODEL,
            dimensions=settings.EMBEDDING_DIM  # Shortening de 3072 a 1536
        )
        return resp.data[0].embedding
    except Exception as e:
        print(f"Error generando embedding: {e}")
        return [0.0] * settings.EMBEDDING_DIM

def compute_md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()

def extract_url_from_content(content: str) -> str:
    url_pattern = r"(https?://[^\s\)]+)"
    match = re.search(url_pattern, content[:500])
    if match:
        return match.group(1)
    return ""

def extract_keywords_from_url(url: str) -> List[str]:
    """
    Extrae keywords del path de la URL.
    Ejemplo: /carrera/medicina/plan-estudios -> ["carrera", "medicina", "plan", "estudios"]
    """
    from urllib.parse import urlparse
    path = urlparse(url).path
    # Filtrar segmentos vacíos y muy cortos
    segments = [s for s in path.split("/") if len(s) > 2]
    # Separar por guiones
    keywords = []
    for segment in segments:
        keywords.extend(segment.split("-"))
    return keywords

def extract_enhanced_metadata(
    url: str,
    title: str,
    split_metadata: Dict[str, Any],
    chunk_index: int,
    total_chunks: int
) -> Dict[str, Any]:
    """
    Genera metadata enriquecida para cada chunk.
    Incluye jerarquía semántica, posición, keywords de URL, etc.
    """
    from urllib.parse import urlparse

    # Headers jerárquicos del documento
    section_hierarchy = {
        "h1": split_metadata.get("Header 1", ""),
        "h2": split_metadata.get("Header 2", ""),
        "h3": split_metadata.get("Header 3", ""),
        "h4": split_metadata.get("Header 4", ""),
    }

    # Path semántico completo
    semantic_path = " > ".join(filter(None, [
        section_hierarchy["h1"],
        section_hierarchy["h2"],
        section_hierarchy["h3"],
        section_hierarchy["h4"],
    ]))

    return {
        # Identificación
        "url": url,
        "title": title,
        "source": "crawler",

        # Jerarquía semántica
        "section_h1": section_hierarchy["h1"],
        "section_h2": section_hierarchy["h2"],
        "section_h3": section_hierarchy["h3"],
        "section_h4": section_hierarchy["h4"],
        "semantic_path": semantic_path,

        # Posición en el documento
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "position_ratio": round(chunk_index / max(total_chunks, 1), 2),

        # Timestamps y domain
        "crawled_at": datetime.utcnow().isoformat(),
        "domain": urlparse(url).netloc,

        # Keywords de URL
        "url_path": urlparse(url).path,
        "url_keywords": extract_keywords_from_url(url),
    }

async def ingest_page_realtime(
    url: str,
    title: str,
    markdown_content: str,
    file_path: str
) -> None:
    """
    Ingesta una sola página inmediatamente después de ser scrapeada.
    Esta función se llama en tiempo real durante el crawling.

    Args:
        url: URL de la página
        title: Título de la página
        markdown_content: Contenido en markdown
        file_path: Path del archivo .md guardado
    """
    from app.core.database import async_session_maker, init_rag_db
    from app.utils.urls import canonicalize, path_segments as get_path_segments, page_type_from_path, url_hash as compute_url_hash

    # Configurar splitters (igual que ingest_all_markdowns)
    headers_split = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("####", "Header 4"),
    ]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_split)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=300,
        separators=["\n\n\n", "\n\n", "\n", ". ", " "],
    )

    # Procesar URL
    canonical_url = canonicalize(url)
    segments = get_path_segments(url)
    depth = len(segments)
    url_hash_value = compute_url_hash(url)
    page_type = page_type_from_path(segments)

    # Generar hash del contenido
    content_hash = compute_md5(markdown_content)

    async with async_session_maker() as session:
        repo = RagRepository(session)

        # Verificar si ya existe por canonical URL
        existing_doc = await repo.get_doc_by_canonical_url(canonical_url)
        if existing_doc:
            print(f"⏭️  Saltando {title} (Ya indexado)")
            return

        print(f"📄 Procesando en tiempo real: {title}")

        # Obtener o crear source
        source = await repo.get_or_create_source(url)

        # Crear documento con todos los campos
        doc = Document(
            source_id=source.source_id,
            url=url,
            canonical_url=canonical_url,
            url_hash=url_hash_value,
            path_segments=segments,
            path_depth=depth,
            title=title,
            page_type=page_type,
            language="es",
            content_hash=content_hash,
            content_len=len(markdown_content),
            meta={
                "source": "crawler",
                "filename": file_path,
                "url": url
            }
        )
        doc = await repo.create_document(doc)

        # Generar chunks
        md_splits = md_splitter.split_text(markdown_content)
        final_chunks = text_splitter.split_documents(md_splits)

        chunks_buffer = []
        char_position = 0
        for idx, split in enumerate(final_chunks):
            vector = await get_embedding(split.page_content)

            # Calcular posiciones de caracteres
            text = split.page_content
            start_char = char_position
            end_char = char_position + len(text)
            char_position = end_char

            # Extraer heading path del metadata
            heading_path = []
            for i in range(1, 5):
                header_key = f"Header {i}"
                if header_key in split.metadata and split.metadata[header_key]:
                    heading_path.append(split.metadata[header_key])

            # Usar metadata enriquecida
            chunk_meta = extract_enhanced_metadata(
                url=url,
                title=title,
                split_metadata=split.metadata,
                chunk_index=idx,
                total_chunks=len(final_chunks)
            )

            # Estimar tokens (aproximación simple)
            text_tokens = len(text.split())

            chunk = Chunk(
                doc_id=doc.doc_id,
                chunk_index=idx,
                start_char=start_char,
                end_char=end_char,
                heading_path=heading_path,
                text=text,
                text_tokens=text_tokens,
                is_boilerplate=False,
                embedding_model=settings.OPENAI_EMBEDDING_MODEL,
                embedding_dim=settings.EMBEDDING_DIM,
                embedding=vector,
                meta=chunk_meta
            )
            chunks_buffer.append(chunk)

        if chunks_buffer:
            await repo.create_chunks(chunks_buffer)
            await session.commit()
            print(f"✅ Ingestado: {title} ({len(chunks_buffer)} chunks)")

async def ingest_all_markdowns():
    print("⚡ Inicializando base de datos y esquema RAG...")
    await init_rag_db()
    
    # Headers más detallados para mejor granularidad semántica
    headers_split = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("####", "Header 4"),  # Agregado para mayor detalle
    ]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_split)

    # Chunks más grandes para capturar conceptos educativos completos
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,      # Aumentado de 1000
        chunk_overlap=300,    # Aumentado de 200 (20%)
        separators=["\n\n\n", "\n\n", "\n", ". ", " "],
    )

    async with async_session_maker() as session:
        repo = RagRepository(session)
        print(f"📂 Leyendo archivos desde: {settings.SITE_MD_DIR}")

        if not os.path.exists(settings.SITE_MD_DIR):
            print(f"❌ Error: No existe el directorio {settings.SITE_MD_DIR}")
            return

        for root, _, files in os.walk(settings.SITE_MD_DIR):
            for file in files:
                if not file.endswith(".md"): continue
                
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception:
                    continue 

                content_hash = compute_md5(content)
                if await repo.get_doc_by_hash(content_hash):
                    print(f"⏭️  Saltando {file} (Ya indexado)")
                    continue

                print(f"📄 Procesando: {file}")

                detected_url = extract_url_from_content(content)

                if not detected_url:
                    print(f"⚠️  Saltando {file} (URL no detectada)")
                    continue

                from app.utils.urls import canonicalize, path_segments as get_path_segments, page_type_from_path, url_hash as compute_url_hash

                # Procesar URL
                canonical_url = canonicalize(detected_url)
                segments = get_path_segments(detected_url)
                depth = len(segments)
                url_hash_value = compute_url_hash(detected_url)
                page_type = page_type_from_path(segments)

                # Obtener o crear source
                source = await repo.get_or_create_source(detected_url)

                doc = Document(
                    source_id=source.source_id,
                    url=detected_url,
                    canonical_url=canonical_url,
                    url_hash=url_hash_value,
                    path_segments=segments,
                    path_depth=depth,
                    title=file,
                    page_type=page_type,
                    language="es",
                    content_hash=content_hash,
                    content_len=len(content),
                    meta={
                        "source": "crawler",
                        "filename": file,
                        "url": detected_url
                    }
                )
                doc = await repo.create_document(doc)

                md_splits = md_splitter.split_text(content)
                final_chunks = text_splitter.split_documents(md_splits)

                chunks_buffer = []
                char_position = 0
                for idx, split in enumerate(final_chunks):
                    vector = await get_embedding(split.page_content)

                    # Calcular posiciones de caracteres
                    text = split.page_content
                    start_char = char_position
                    end_char = char_position + len(text)
                    char_position = end_char

                    # Extraer heading path del metadata
                    heading_path = []
                    for i in range(1, 5):
                        header_key = f"Header {i}"
                        if header_key in split.metadata and split.metadata[header_key]:
                            heading_path.append(split.metadata[header_key])

                    # Usar metadata enriquecida
                    chunk_meta = extract_enhanced_metadata(
                        url=detected_url,
                        title=file,
                        split_metadata=split.metadata,
                        chunk_index=idx,
                        total_chunks=len(final_chunks)
                    )

                    # Estimar tokens (aproximación simple)
                    text_tokens = len(text.split())

                    chunk = Chunk(
                        doc_id=doc.doc_id,
                        chunk_index=idx,
                        start_char=start_char,
                        end_char=end_char,
                        heading_path=heading_path,
                        text=text,
                        text_tokens=text_tokens,
                        is_boilerplate=False,
                        embedding_model=settings.OPENAI_EMBEDDING_MODEL,
                        embedding_dim=settings.EMBEDDING_DIM,
                        embedding=vector,
                        meta=chunk_meta
                    )
                    chunks_buffer.append(chunk)
                
                if chunks_buffer:
                    await repo.create_chunks(chunks_buffer)
                    await session.commit()
                    
    print("✅ Ingesta Completada. Base de datos lista para consultas.")

if __name__ == "__main__":
    asyncio.run(ingest_all_markdowns())
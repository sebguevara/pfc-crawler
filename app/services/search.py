from typing import List, Dict, AsyncGenerator
from app.core.database import async_session_maker
from app.repositories.rag_repository import RagRepository
from app.core.config import settings
from app.core.session_manager import session_manager
from app.utils.prompts import SYSTEM_RAG
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def rag_search_service(query: str) -> str:
    """
    Servicio RAG original sin streaming (DEPRECATED).
    Usar rag_search_streaming_service para nueva implementación.
    """
    try:
        resp = await client.embeddings.create(input=[query], model=settings.OPENAI_EMBEDDING_MODEL)
        query_vec = resp.data[0].embedding
    except Exception as e:
        return f"Error OpenAI: {e}"

    async with async_session_maker() as session:
        repo = RagRepository(session)

        chunks = await repo.hybrid_search(
            vector=query_vec,
            query_text=query,
            limit=10
        )

        if not chunks:
            return "No encontré información relevante."

        doc_scores = {}
        doc_meta = {}

        for c in chunks:
            doc_id = c.doc_id
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + 1
            doc_meta[doc_id] = c.meta

        top_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:3]

        context_text = ""

        for doc_id, score in top_docs:
            full_text = await repo.get_full_document_text(doc_id)
            meta = doc_meta[doc_id]
            url = meta.get('url', 'Sin URL')
            filename = meta.get('filename', 'Archivo')

            context_text += f"\n\n=== DOCUMENTO COMPLETO: {filename} (URL: {url}) ===\n{full_text}\n"

    system_prompt = SYSTEM_RAG

    user_prompt = f"""A continuación te proporciono la información de la base de conocimiento de la Facultad de Medicina UNNE:

{context_text}

---

PREGUNTA DEL USUARIO:
{query}

RECORDÁ: El usuario YA ESTÁ en el sitio web med.unne.edu.ar. NO le digas que visite el sitio web. Respondé DIRECTAMENTE usando el formato estructurado con secciones y emojis."""

    response = await client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )

    return response.choices[0].message.content


async def rag_search_streaming_service(
    query: str,
    session_id: str,
    history_limit: int = 6
) -> AsyncGenerator[str, None]:
    """
    Servicio RAG con streaming y memoria conversacional.

    Args:
        query: Pregunta del usuario
        session_id: ID de sesión para mantener contexto conversacional
        history_limit: Número máximo de mensajes previos a incluir (por defecto 6 = 3 intercambios)

    Yields:
        Chunks de texto de la respuesta del asistente
    """
    # 1. Guardar pregunta del usuario en la sesión
    session_manager.add_message(session_id, "user", query)

    # 2. Obtener embedding de la pregunta
    try:
        resp = await client.embeddings.create(input=[query], model=settings.OPENAI_EMBEDDING_MODEL)
        query_vec = resp.data[0].embedding
    except Exception as e:
        error_msg = f"Error al procesar tu pregunta: {str(e)}"
        session_manager.add_message(session_id, "assistant", error_msg)
        yield error_msg
        return

    # 3. Búsqueda en base de conocimiento
    async with async_session_maker() as session:
        repo = RagRepository(session)

        chunks = await repo.hybrid_search(
            vector=query_vec,
            query_text=query,
            limit=10
        )

        if not chunks:
            error_msg = "Lo siento, no encontré información relevante sobre eso. ¿Podrías reformular tu pregunta?"
            session_manager.add_message(session_id, "assistant", error_msg)
            yield error_msg
            return

        # Agrupar chunks por documento
        doc_scores = {}
        doc_meta = {}

        for c in chunks:
            doc_id = c.doc_id
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + 1
            doc_meta[doc_id] = c.meta

        top_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:3]

        # Construir contexto completo
        context_text = ""
        sources = []

        for doc_id, score in top_docs:
            full_text = await repo.get_full_document_text(doc_id)
            meta = doc_meta[doc_id]
            url = meta.get('url', 'Sin URL')
            filename = meta.get('filename', 'Archivo')

            context_text += f"\n\n=== DOCUMENTO: {filename} ===\n{full_text}\n"
            sources.append({"filename": filename, "url": url})

    # 4. Construir prompt con historial conversacional
    conversation_history = session_manager.get_history(session_id, limit=history_limit)

    # Crear prompt del sistema
    system_prompt = SYSTEM_RAG

    # Crear prompt del usuario con contexto
    user_prompt = f"""A continuación te proporciono la información de la base de conocimiento de la Facultad de Medicina UNNE:

{context_text}

---

PREGUNTA DEL USUARIO:
{query}

RECORDÁ: El usuario YA ESTÁ en el sitio web med.unne.edu.ar. NO le digas que visite el sitio web. Respondé DIRECTAMENTE usando el formato estructurado con secciones y emojis."""

    # 5. Construir mensajes para OpenAI (sistema + historial + nueva pregunta)
    messages = [{"role": "system", "content": system_prompt}]

    # Agregar historial (excluyendo la última pregunta que ya está en user_prompt)
    if len(conversation_history) > 1:
        messages.extend(conversation_history[:-1])

    # Agregar pregunta actual con contexto
    messages.append({"role": "user", "content": user_prompt})

    # 6. Stream de respuesta
    full_response = ""

    try:
        stream = await client.chat.completions.create(
            model="gpt-5-mini",
            messages=messages,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content

    except Exception as e:
        error_msg = f"\n\n❌ Error al generar respuesta: {str(e)}"
        full_response += error_msg
        yield error_msg

    # 7. Guardar respuesta completa en la sesión
    session_manager.add_message(session_id, "assistant", full_response)
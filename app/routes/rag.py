from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4
from app.services.search import rag_search_service, rag_search_streaming_service
from app.core.session_manager import session_manager

router = APIRouter()

# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class Consulta(BaseModel):
    """Modelo de consulta SIN streaming (legacy)."""
    pregunta: str

class ConsultaStream(BaseModel):
    """Modelo de consulta CON streaming y sesiones."""
    pregunta: str = Field(..., description="Pregunta del usuario")
    session_id: Optional[str] = Field(
        default=None,
        description="ID de sesión. Si no se proporciona, se genera uno nuevo"
    )

class SessionStatsResponse(BaseModel):
    """Respuesta con estadísticas de sesiones."""
    total_sessions: int
    ttl_minutes: int
    sessions: dict


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/consultar")
async def consultar_rag(body: Consulta):
    """
    Endpoint LEGACY sin streaming.
    DEPRECATED: Usar /consultar-stream para nueva implementación.
    """
    try:
        respuesta = await rag_search_service(body.pregunta)
        return {"respuesta": respuesta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/consultar-stream")
async def consultar_rag_stream(body: ConsultaStream):
    """
    Endpoint principal con streaming y memoria conversacional.

    Features:
    - Respuestas en streaming (SSE) para experiencia conversacional natural
    - Memoria de conversación por sesión (TTL: 1h)
    - Contexto conversacional mantenido automáticamente

    Args:
        body: ConsultaStream con pregunta y session_id opcional

    Returns:
        StreamingResponse con chunks de texto (text/event-stream)
    """
    # Generar session_id si no se proporciona
    session_id = body.session_id or str(uuid4())

    try:
        # Wrapper para formatear el stream como SSE
        async def event_stream():
            # Enviar session_id al inicio (para que el frontend lo sepa)
            yield f"data: {{'session_id': '{session_id}', 'type': 'session_start'}}\n\n"

            # Stream de respuesta del asistente
            async for chunk in rag_search_streaming_service(body.pregunta, session_id):
                # Formato SSE (Server-Sent Events)
                yield f"data: {{'chunk': {repr(chunk)}, 'type': 'content'}}\n\n"

            # Señal de fin de stream
            yield f"data: {{'type': 'done'}}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Desactivar buffering en nginx
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/history")
async def get_session_history(session_id: str, limit: Optional[int] = None):
    """
    Obtiene el historial de conversación de una sesión.

    Args:
        session_id: ID de la sesión
        limit: Número máximo de mensajes a retornar (opcional)

    Returns:
        Lista de mensajes con role y content
    """
    try:
        history = session_manager.get_history(session_id, limit)
        return {
            "session_id": session_id,
            "history": history,
            "total_messages": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    Elimina una sesión y su historial.

    Args:
        session_id: ID de la sesión a eliminar

    Returns:
        Confirmación de eliminación
    """
    try:
        session_manager.clear_session(session_id)
        return {
            "message": "Sesión eliminada exitosamente",
            "session_id": session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/stats", response_model=SessionStatsResponse)
async def get_sessions_stats():
    """
    Obtiene estadísticas de todas las sesiones activas.

    Returns:
        Estadísticas del gestor de sesiones
    """
    try:
        stats = session_manager.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
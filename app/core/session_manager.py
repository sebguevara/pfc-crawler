"""
Gestor de sesiones conversacionales en memoria con TTL de 1h.
Mantiene el historial de conversaciones por session_id.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from threading import Lock
import asyncio

@dataclass
class Message:
    """Mensaje individual en una conversación."""
    role: str  # 'user' o 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class Session:
    """Sesión conversacional con historial de mensajes."""
    session_id: str
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)

    def add_message(self, role: str, content: str):
        """Agrega un mensaje al historial."""
        self.messages.append(Message(role=role, content=content))
        self.last_activity = datetime.utcnow()

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Retorna el historial de mensajes formateado para OpenAI.

        Args:
            limit: Número máximo de mensajes a retornar (los más recientes)
        """
        messages = self.messages[-limit:] if limit else self.messages
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def is_expired(self, ttl_minutes: int = 60) -> bool:
        """Verifica si la sesión ha expirado."""
        return datetime.utcnow() - self.last_activity > timedelta(minutes=ttl_minutes)


class SessionManager:
    """
    Gestor global de sesiones conversacionales en memoria.

    Features:
    - Almacenamiento en RAM (no en BD)
    - TTL de 1h por defecto
    - Thread-safe
    - Auto-limpieza de sesiones expiradas
    """

    def __init__(self, ttl_minutes: int = 60, cleanup_interval_minutes: int = 10):
        self.sessions: Dict[str, Session] = {}
        self.ttl_minutes = ttl_minutes
        self.cleanup_interval_minutes = cleanup_interval_minutes
        self._lock = Lock()
        self._cleanup_task = None

    def get_or_create_session(self, session_id: str) -> Session:
        """Obtiene una sesión existente o crea una nueva."""
        with self._lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = Session(session_id=session_id)
            else:
                # Actualizar last_activity
                self.sessions[session_id].last_activity = datetime.utcnow()

            return self.sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str):
        """Agrega un mensaje a una sesión."""
        session = self.get_or_create_session(session_id)
        session.add_message(role, content)

    def get_history(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Obtiene el historial de una sesión."""
        session = self.get_or_create_session(session_id)
        return session.get_history(limit)

    def clear_session(self, session_id: str):
        """Elimina una sesión."""
        with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]

    def cleanup_expired_sessions(self):
        """Elimina sesiones expiradas."""
        with self._lock:
            expired = [
                sid for sid, session in self.sessions.items()
                if session.is_expired(self.ttl_minutes)
            ]
            for sid in expired:
                del self.sessions[sid]

            if expired:
                print(f"🧹 Limpieza: {len(expired)} sesiones expiradas eliminadas")

    async def start_cleanup_task(self):
        """Inicia tarea de limpieza automática en background."""
        while True:
            await asyncio.sleep(self.cleanup_interval_minutes * 60)
            self.cleanup_expired_sessions()

    def get_stats(self) -> Dict:
        """Obtiene estadísticas del gestor."""
        with self._lock:
            return {
                "total_sessions": len(self.sessions),
                "ttl_minutes": self.ttl_minutes,
                "sessions": {
                    sid: {
                        "messages_count": len(session.messages),
                        "created_at": session.created_at.isoformat(),
                        "last_activity": session.last_activity.isoformat(),
                        "is_expired": session.is_expired(self.ttl_minutes)
                    }
                    for sid, session in self.sessions.items()
                }
            }


# Instancia global del gestor de sesiones
session_manager = SessionManager(ttl_minutes=60, cleanup_interval_minutes=10)

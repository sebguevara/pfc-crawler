"""
Script de prueba para el chatbot RAG con streaming.
Demuestra cómo usar el nuevo endpoint /consultar-stream
"""

import asyncio
import httpx
import json
from uuid import uuid4


class ChatbotClient:
    """Cliente para interactuar con el chatbot RAG."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_id = None

    async def send_message_stream(self, pregunta: str):
        """
        Envía un mensaje y muestra la respuesta en streaming.

        Args:
            pregunta: Pregunta del usuario
        """
        url = f"{self.base_url}/api/consultar-stream"

        # Generar session_id si no existe
        if not self.session_id:
            self.session_id = str(uuid4())

        payload = {
            "pregunta": pregunta,
            "session_id": self.session_id
        }

        print(f"\n{'=' * 80}")
        print(f"🙋 Usuario: {pregunta}")
        print(f"{'=' * 80}")
        print("🤖 Asistente: ", end="", flush=True)

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    print(f"\n❌ Error: {response.status_code}")
                    return

                full_response = ""

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Quitar "data: "

                        try:
                            # Reemplazar comillas simples por dobles para JSON válido
                            data_str = data_str.replace("'", '"')
                            data = json.loads(data_str)

                            if data.get("type") == "session_start":
                                self.session_id = data.get("session_id")

                            elif data.get("type") == "content":
                                chunk = data.get("chunk", "")
                                full_response += chunk
                                print(chunk, end="", flush=True)

                            elif data.get("type") == "done":
                                print("\n")
                                break

                        except json.JSONDecodeError as e:
                            print(f"\n⚠️ Error decodificando JSON: {e}")
                            print(f"Datos recibidos: {data_str}")

        print(f"{'=' * 80}\n")
        return full_response

    async def get_history(self, limit: int = None):
        """Obtiene el historial de la sesión actual."""
        if not self.session_id:
            print("⚠️ No hay sesión activa")
            return []

        url = f"{self.base_url}/api/session/{self.session_id}/history"
        params = {"limit": limit} if limit else {}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                return data.get("history", [])
            else:
                print(f"❌ Error al obtener historial: {response.status_code}")
                return []

    async def clear_session(self):
        """Elimina la sesión actual."""
        if not self.session_id:
            print("⚠️ No hay sesión activa")
            return

        url = f"{self.base_url}/api/session/{self.session_id}"

        async with httpx.AsyncClient() as client:
            response = await client.delete(url)

            if response.status_code == 200:
                print(f"✅ Sesión {self.session_id} eliminada")
                self.session_id = None
            else:
                print(f"❌ Error al eliminar sesión: {response.status_code}")


async def demo_conversacion():
    """Demostración de una conversación completa."""

    client = ChatbotClient()

    print("\n" + "🎯" * 40)
    print("DEMO: Chatbot RAG con Streaming y Memoria Conversacional")
    print("🎯" * 40)

    # Conversación de ejemplo
    preguntas = [
        "Hola, ¿qué requisitos necesito para ingresar a Medicina?",
        "¿Y cuánto dura la carrera?",
        "¿Hay algún examen de ingreso?",
        "Perfecto, gracias por la información"
    ]

    for pregunta in preguntas:
        await client.send_message_stream(pregunta)
        await asyncio.sleep(1)  # Pausa entre preguntas

    # Mostrar historial
    print("\n" + "📜" * 40)
    print("HISTORIAL DE LA CONVERSACIÓN")
    print("📜" * 40)

    history = await client.get_history()
    for i, msg in enumerate(history, 1):
        role = "🙋 Usuario" if msg["role"] == "user" else "🤖 Asistente"
        content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
        print(f"{i}. {role}: {content}\n")

    # Limpiar sesión
    print("\n" + "🧹" * 40)
    await client.clear_session()


async def test_single_question():
    """Prueba simple con una sola pregunta."""

    client = ChatbotClient()

    print("\n" + "🧪" * 40)
    print("TEST: Pregunta Individual")
    print("🧪" * 40)

    await client.send_message_stream(
        "¿Qué carreras ofrece la Facultad de Medicina?"
    )


async def test_session_persistence():
    """Prueba de persistencia de sesión."""

    print("\n" + "💾" * 40)
    print("TEST: Persistencia de Sesión")
    print("💾" * 40)

    # Primera interacción
    client1 = ChatbotClient()
    client1.session_id = "test-session-123"

    await client1.send_message_stream("Hola, soy Juan")
    await asyncio.sleep(0.5)

    # Segunda interacción con el mismo session_id
    client2 = ChatbotClient()
    client2.session_id = "test-session-123"

    await client2.send_message_stream("¿Recuerdas mi nombre?")

    # Verificar historial
    history = await client2.get_history()
    print(f"\n📊 Total de mensajes en la sesión: {len(history)}")


async def main():
    """Menú principal de pruebas."""

    print("""
╔════════════════════════════════════════════════════════════════╗
║        CHATBOT RAG - SCRIPT DE PRUEBAS                         ║
║        Facultad de Medicina UNNE                               ║
╚════════════════════════════════════════════════════════════════╝

Selecciona una opción:

1. Demo completa (conversación multi-turno)
2. Pregunta individual
3. Test de persistencia de sesión
4. Todas las pruebas
5. Salir

    """)

    opcion = input("Opción: ").strip()

    if opcion == "1":
        await demo_conversacion()
    elif opcion == "2":
        await test_single_question()
    elif opcion == "3":
        await test_session_persistence()
    elif opcion == "4":
        await test_single_question()
        await asyncio.sleep(2)
        await test_session_persistence()
        await asyncio.sleep(2)
        await demo_conversacion()
    elif opcion == "5":
        print("👋 Hasta luego!")
        return
    else:
        print("❌ Opción inválida")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Pruebas interrumpidas por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")

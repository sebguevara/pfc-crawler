import asyncio
from app.services.search import rag_search_service

async def main():
    pregunta = "Cuales son los requisitos de inscripcion?"
    
    print(f"🔎 Buscando respuesta para: '{pregunta}'...")
    respuesta = await rag_search_service(pregunta)
    
    print("\n" + "="*50)
    print("🤖 RESPUESTA DEL BOT:")
    print("="*50)
    print(respuesta)

if __name__ == "__main__":
    asyncio.run(main())
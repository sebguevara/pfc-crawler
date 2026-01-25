from mcp.server.fastmcp import FastMCP
from app.services.search import rag_search_service

mcp = FastMCP("Medicina_UNNE_Bot")

@mcp.tool()
async def consultar_medicina_unne(pregunta: str) -> str:
    return await rag_search_service(pregunta)

if __name__ == "__main__":
    mcp.run()
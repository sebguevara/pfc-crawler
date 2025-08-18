from openai import OpenAI
from app.core.config import settings

_client = None
def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client
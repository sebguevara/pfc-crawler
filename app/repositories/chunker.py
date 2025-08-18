from typing import Iterable
import tiktoken

def sliding_windows(text: str, max_tokens=1000, overlap=200, enc_name="cl100k_base"):
    enc = tiktoken.get_encoding(enc_name)
    toks = enc.encode(text)
    step = max_tokens - overlap if max_tokens > overlap else max_tokens
    for i in range(0, len(toks), step):
        window = toks[i:i+max_tokens]
        if not window: break
        yield enc.decode(window), len(window)

def make_chunks(body: str, heading_path: list[str], start_char: int, max_tokens=1000, overlap=20):
    for piece, tok_count in sliding_windows(body, max_tokens=max_tokens, overlap=overlap):
        yield piece, tok_count

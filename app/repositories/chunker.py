"""Text chunking utilities for creating semantic chunks from markdown content."""
import tiktoken
from typing import Generator, Tuple

def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception:
        # Fallback: rough estimate
        return len(text) // 4

def make_chunks(
    text: str,
    heading_path: list[str],
    start_char: int = 0,
    max_tokens: int = 500,
    overlap_tokens: int = 50
) -> Generator[Tuple[str, int], None, None]:
    """
    Split text into chunks with token limits.

    Args:
        text: Text to chunk
        heading_path: List of heading hierarchy
        start_char: Starting character position
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Tokens to overlap between chunks

    Yields:
        Tuples of (chunk_text, token_count)
    """
    if not text or not text.strip():
        return

    # For short text, return as single chunk
    token_count = count_tokens(text)
    if token_count <= max_tokens:
        yield (text, token_count)
        return

    # Split into paragraphs first
    paragraphs = text.split('\n\n')
    current_chunk = []
    current_tokens = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_tokens = count_tokens(para)

        # If single paragraph exceeds max, split by sentences
        if para_tokens > max_tokens:
            sentences = para.split('. ')
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                sent_tokens = count_tokens(sent)

                if current_tokens + sent_tokens > max_tokens and current_chunk:
                    # Yield current chunk
                    chunk_text = ' '.join(current_chunk)
                    yield (chunk_text, count_tokens(chunk_text))

                    # Start new chunk with overlap
                    current_chunk = [sent]
                    current_tokens = sent_tokens
                else:
                    current_chunk.append(sent)
                    current_tokens += sent_tokens
        else:
            # Check if adding this paragraph exceeds limit
            if current_tokens + para_tokens > max_tokens and current_chunk:
                # Yield current chunk
                chunk_text = '\n\n'.join(current_chunk)
                yield (chunk_text, count_tokens(chunk_text))

                # Start new chunk
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens

    # Yield remaining chunk
    if current_chunk:
        chunk_text = '\n\n'.join(current_chunk)
        yield (chunk_text, count_tokens(chunk_text))

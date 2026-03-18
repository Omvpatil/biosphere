from search_database.utils.llm_factory import get_embedder
import os
import logging

logger = logging.getLogger(__name__)

def get_embeddings(text_chunk: str) -> list[float]:
    """
    Sends the text to the background Ollama daemon and returns the 1024d vector.
    """
    try:
        embedder = get_embedder()
        logger.info("generating embeddings")
        result = embedder.embed_query(text_chunk)
        return result if isinstance(result, list) else []
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return []


def get_batch_embeddings(text_chunks: list[str]) -> list[list[float]]:
    """
    Sends a list of text chunks to Ollama in parallel for bulk embedding generation
    """
    try:
        embedder = get_embedder()
        logger.info("generating embeddings in batch")
        result = embedder.embed_documents(text_chunks)
        return result if isinstance(result, list) else []
    except Exception as e:
        logger.error(f"Failed to generate batch embeddings: {e}")
        return []

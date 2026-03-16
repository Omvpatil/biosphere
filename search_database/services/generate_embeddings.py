from langchain_ollama import OllamaEmbeddings
import os
import logging

ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
embedder = OllamaEmbeddings(model="mxbai-embed-large:latest", base_url=ollama_url)


logger = logging.getLogger(__name__)



def get_embeddings(text_chunk: str) -> list[float]:
    """
    Sends the text to the background Ollama daemon and returns the 1024d vector.
    """
    logger.info("generating embeddings")
    return embedder.embed_query(text_chunk)


def get_batch_embeddings(text_chunks: str) -> list[list[float]]:
    """
    Sends a list of text chunks to Ollama in parallel for bulk embedding generation
    """
    logger.info("generating embeddings in batch")
    return embedder.embed_documents(text_chunks)

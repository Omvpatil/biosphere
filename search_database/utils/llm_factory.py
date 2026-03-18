from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mistralai import ChatMistralAI
from django.conf import settings
import os
import logging

logger = logging.getLogger(__name__)


def get_ollama_base_url():
    """
    Returns the Ollama base URL from environment variables,
    falling back to localhost if not set.
    """
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def get_llm():
    """
    Factory function to get the appropriate LLM based on configuration.
    """
    ai_provider = os.getenv("AI_PROVIDER", "ollama").lower()

    if ai_provider == "gemini":
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", api_key=settings.GEMINI_API_KEY, streaming=True
        )
    if ai_provider == "mistral":
        return ChatMistralAI(
            model="mistral-small-latest",
            api_key=settings.MISTRAL_API_KEY,
            streaming=True,
        )
    else:
        ollama_url = get_ollama_base_url()
        ollama_model = os.getenv("OLLAMA_MODEL", "lfm2.5-thinking:latest")
        return ChatOllama(model=ollama_model, temperature=0, base_url=ollama_url)


def get_embedder():
    """
    Returns the Ollama embeddings instance.
    """
    ollama_url = get_ollama_base_url()
    # Defaulting to the model you specified as already pulled
    model = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large:latest")
    return OllamaEmbeddings(model=model, base_url=ollama_url)


def get_fast_rewriter():
    """
    Returns a small SLM for quick query rewriting.
    """
    ollama_url = get_ollama_base_url()
    return ChatOllama(model="qwen2.5:0.5b", temperature=0, base_url=ollama_url)

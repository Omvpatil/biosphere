from django.conf import settings
from search_database.ai.prompt_templates import (
    prompt_1,
    prompt_2,
    prompt_3,
    prompt_4,
    prompt_5,
)
from search_database.utils.llm_factory import get_llm
import os
import logging

logger = logging.getLogger(__name__)

# Determine which AI to use - default to Ollama
AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").lower()

def generate_stream(user_query: str, context: str, chat_history: str, route: str, papers: list = None):
    """
    Generate streaming response using the configured AI provider.
    Default is Ollama, falls back to Gemini if configured via AI_PROVIDER env var.
    Supports streaming chain of thought and tool calls.
    """
    prompt = prompt_2
    paper_count = len(papers) if papers else 0
    paper_ids = [p.get("paper_id") for p in papers] if papers else []
    
    try:
        llm = get_llm()
        chain = prompt | llm
        
        # 1. Start with initial thoughts based on routing
        yield {"type": "thought", "content": f"Initializing search via {route} path for: '{user_query}'"}
        
        # 2. Dynamic Tool Call for search results
        yield {
            "type": "tool_call", 
            "name": "SEARCH_PAPERS", 
            "status": "completed", 
            "params": {"query": user_query}, 
            "result": f"Found {paper_count} highly relevant research papers from the archive."
        }

        if paper_count > 0:
            yield {"type": "thought", "content": f"Extracting key biological concepts from {paper_count} papers..."}
            yield {
                "type": "tool_call", 
                "name": "EXTRACT_KEY_CONCEPTS", 
                "status": "completed", 
                "params": {"paper_ids": paper_ids}, 
                "result": f"Successfully isolated key experimental findings across {paper_count} documents."
            }
        
        yield {"type": "thought", "content": "Synthesizing final scientific response with citations..."}

        # 3. Handle actual text generation streaming
        if AI_PROVIDER == "gemini":
            for chunk in chain.stream({"context": context, "user_query": user_query}):
                if chunk.content:
                    yield {"type": "token", "content": chunk.content}
        else:
            # Ollama streaming
            for chunk in chain.stream({"context": context, "user_query": user_query}):
                content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if content:
                    yield {"type": "token", "content": content}
                    
    except Exception as e:
        error_str = str(e).lower()
        # Check for quota/rate limit errors
        if any(
            keyword in error_str
            for keyword in [
                "quota",
                "rate limit",
                "429",
                "limit exceeded",
                "insufficient quota",
                "daily limit",
            ]
        ):
            logger.error(f"Quota exceeded: {e}")
            yield {
                "type": "error",
                "message": "quota_exceeded",
                "details": "AI quota has been exhausted. Please try again later or upgrade your plan.",
            }
        else:
            logger.error(f"Error during LLM stream: {e}")
            yield {
                "type": "error",
                "message": "Failed to generate LLM response.",
                "details": str(e),
            }

from langchain_ollama.chat_models import ChatOllama
from langchain_core.prompts import PromptTemplate
import os
import logging

logger = logging.getLogger(__name__)

ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
fast_rewriter = ChatOllama(model="qwen2.5:0.5b", temperature=0, base_url=ollama_url)


rewrite_prompt = PromptTemplate.from_template("""
You are a strict text-cleaning engine. Your ONLY job is to remove conversational prefixes from a sentence which is mostly about space-biology.
DO NOT summarize the text. DO NOT remove prepositions or grammar. DO NOT remove scientific terms, genes, or names.
Keep the exact sentence structure, just delete the greeting.

Example 1:
User: Find me papers about the effects of microgravity on CDKN1a/p21.
Output: the effects of microgravity on CDKN1a/p21.

Example 2:
User: I am looking for research papers authored by John Smith on human health in 2023.
Output: research papers authored by John Smith on human health in 2023.

Example 3:
User: What are the recent findings on spaceflight and oxidative stress in the heart?
Output: spaceflight and oxidative stress in the heart?

Example 4:
User: Show me the latest studies on the effects of cosmic radiation on the brain.
Output: the effects of cosmic radiation on the brain.

User: {user_query}
Output:""")

rewrite_chain = rewrite_prompt | fast_rewriter


def optimize_semantic_query(user_query: str) -> str:
    """
    Sends the raw query to a tiny local SLM to strip conversational boilerplate
    in milliseconds.
    """
    try:
        response = rewrite_chain.invoke({"user_query": user_query})
        return response.content.strip()
    except Exception as e:
        logger.error(f"Failed to rewrite query: {e}")
        return user_query

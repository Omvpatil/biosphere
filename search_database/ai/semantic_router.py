from pydantic import BaseModel, Field
from enum import Enum


class RouteChoice(str, Enum):
    CHAT = "CHAT"
    SEARCH_PAPERS = "SEARCH_PAPERS"
    SEARCH_GRAPH = "SEARCH_GRAPH"
    SEARCH_BOTH = "SEARCH_BOTH"
    FOLLOW_UP_HISTORY = "FOLLOW_UP_HISTORY"


class SemanticRouter(BaseModel):
    route: RouteChoice = Field(
        description="The category that best matches the user's intent."
    )


router_prompt = """
You are a highly logical traffic controller. Read the recent chat history and the user's NEW input. Classify the NEW input:

- CHAT: General greetings.
- SEARCH_PAPERS: Asking for NEW research papers or biological facts not yet discussed.
- SEARCH_GRAPH: Asking for NEW authors or collaborations not yet discussed.
- SEARCH_BOTH: Asking for NEW papers AND authors.
- FOLLOW_UP_HISTORY: The user is asking a follow-up question about the papers, authors, or topics we JUST discussed in the recent chat history. They are using words like "that paper", "he", "it", or asking for summaries of what was just said.

--- RECENT CHAT HISTORY ---
{short_chat_history}

--- NEW USER INPUT ---
{user_query}
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from django.conf import settings

def get_route(user_query: str, short_chat_history: str = "") -> SemanticRouter:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", api_key=settings.GEMINI_API_KEY)
    structured_llm = llm.with_structured_output(SemanticRouter)
    prompt = router_prompt.format(short_chat_history=short_chat_history, user_query=user_query)
    try:
        response = structured_llm.invoke(prompt)
        return response
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Routing failed: {e}")
        return SemanticRouter(route=RouteChoice.SEARCH_BOTH)


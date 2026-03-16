from langchain_google_genai import ChatGoogleGenerativeAI
from django.conf import settings
from search_database.ai.prompt_templates import prompt_1, prompt_2, prompt_3, prompt_4, prompt_5

# Choose the appropriate prompt based on route or logic. For now, use prompt_1 as default,
# or dynamically pick based on context size or user request.
def generate_stream(user_query: str, context: str, chat_history: str, route: str):
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        api_key=settings.GEMINI_API_KEY,
        streaming=True
    )
    
    # We can choose prompt based on route if we want, but let's use prompt_1 for now
    # or a generic structured chat prompt.
    prompt = prompt_1
    
    chain = prompt | llm
    
    try:
        for chunk in chain.stream({"context": context, "user_query": user_query}):
            if chunk.content:
                yield {"type": "token", "content": chunk.content}
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error during LLM stream: {e}")
        yield {"type": "error", "message": "Failed to generate LLM response."}

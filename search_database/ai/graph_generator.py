import logging
from typing import List
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from django.conf import settings
from langchain_core.prompts import PromptTemplate

logger = logging.getLogger(__name__)

class Node(BaseModel):
    id: str = Field(description="Unique identifier for the node. Use a clean string (e.g., entity name).")
    label: str = Field(description="The display name of the entity.")
    type: str = Field(description="The type/category (e.g., 'Author', 'Paper', 'Gene', 'Organism', 'Concept').")

class Edge(BaseModel):
    source: str = Field(description="The id of the source node.")
    target: str = Field(description="The id of the target node.")
    relation: str = Field(description="The relationship (e.g., 'WROTE', 'MENTIONS', 'AFFECTS', 'INTERACTS_WITH').")

class GraphData(BaseModel):
    nodes: List[Node] = Field(description="List of entities extracted from text.")
    edges: List[Edge] = Field(description="List of relationships between those entities.")

def generate_graph_from_text(text: str) -> dict:
    if not text or len(text.strip()) == 0:
        return {"nodes": [], "edges": []}
        
    try:
        # gemini-1.5-flash is extremely fast and heavily optimized for structured output tasks.
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash", 
            api_key=settings.GEMINI_API_KEY,
            temperature=0, # Deterministic, factual extraction
        )
        
        structured_llm = llm.with_structured_output(GraphData)
        
        prompt = PromptTemplate.from_template(
            "You are an expert data extractor converting scientific text into a precise knowledge graph.\n"
            "Analyze the following text and extract all entities (nodes) and their relationships (edges).\n"
            "Ensure the graph captures the core relationships mentioned in the text accurately.\n\n"
            "Text to analyze:\n{text}\n"
        )
        
        chain = prompt | structured_llm
        
        result = chain.invoke({"text": text})
        
        if result:
            return result.model_dump()
        return {"nodes": [], "edges": []}
        
    except Exception as e:
        logger.error(f"Failed to generate graph from text: {e}")
        return {"nodes": [], "edges": [], "error": str(e)}

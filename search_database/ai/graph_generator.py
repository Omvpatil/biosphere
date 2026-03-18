import logging
import os
from typing import List
from pydantic import BaseModel, Field
from django.conf import settings
from langchain_core.prompts import PromptTemplate
from search_database.utils.llm_factory import get_llm

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

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

def generate_graph_from_text(text: str) -> dict:
    if not text or len(text.strip()) == 0:
        return {"nodes": [], "edges": []}
        
    try:
        llm = get_llm()
        parser = JsonOutputParser(pydantic_object=GraphData)

        prompt = PromptTemplate(
            template="You are a scientific data extractor. Convert the following research summary into a knowledge graph.\n"
                     "{format_instructions}\n"
                     "Rules:\n"
                     "1. Extract nodes for: Paper, Gene, Author, Environment, Concept.\n"
                     "2. Nodes MUST be objects with 'id', 'label', and 'type'.\n"
                     "3. Edges MUST be objects with 'source', 'target', and 'relation'.\n"
                     "4. Use underscores for IDs (e.g. 'muscle_atrophy').\n\n"
                     "Text:\n{text}\n",
            input_variables=["text"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        
        chain = prompt | llm | parser
        
        graph_data = chain.invoke({"text": text})
        
        if graph_data:
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])
            return {
                "nodes": nodes if isinstance(nodes, list) else [],
                "edges": edges if isinstance(edges, list) else []
            }
        return {"nodes": [], "edges": []}
        
    except Exception as e:
        logger.error(f"Failed to generate graph from text: {e}")
        # Return whatever we got if it's partially valid or empty
        return {"nodes": [], "edges": [], "error": str(e)}

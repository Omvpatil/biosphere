# DOCS:
# 1. Entity Extraction (GLiNER)
#   Extracts highly specific facets (keywords, entities) directly from the raw user query to feed the databases.
# 2. Query Understanding & Routing (SLM)
#   Rephrasing: Optimizes the raw query for vector/semantic search.
#   Context Check: Evaluates the meta-summary of previous conversations
#   Decision Engine: Acts as a router based on the context check. It chooses one of four paths:
#         Fetch only from Neo4j.
#         Fetch only from Postgres
#         Fetch from both databases.
#         Skip Retrieval: If the required data is already in the conversation history, bypass the databases entirely.
# 3. Conditional Retrieval Engine
#   Neo4j Path: Uses extracted facets to traverse and retrieve relationships between research papers.
#     Postgres Path: Performs a two-step filter: strict keyword matching using facets, followed by a semantic search on those specific results.
# 4. Generation (LLM)
#     Synthesizes the optimized query, conversation history, and any newly retrieved database context.
#     Applies strict prompt instructions to format the final output.
# DOCSEND:


from collections import OrderedDict

from search_database.models import ResearchPaper
from search_database.search.extract_facets import extract_facets_from_query
from search_database.search.search_papers import (
    bm25_search_chunks,
    facet_search_postgres,
    query_graph_with_facets,
    semantic_search_postgres,
    rerank_chunks,
)
import logging
from search_database.ai.query_rewriter import optimize_semantic_query
from search_database.ai.semantic_router import get_route, RouteChoice
from search_database.ai.response_generator import generate_stream

logger = logging.getLogger(__name__)


def _build_paper_context(bm25_results: list[dict], semantic_results: list[dict]) -> list[dict]:
    """
    Groups BM25 and semantic search results by paper, deduplicates chunks,
    and fetches paper-level metadata (abstract, images with signed URLs).

    Returns a list of paper dicts, each containing:
    - title, abstract, images (with signed URLs & descriptions)
    - relevant_chunks: deduplicated text snippets from both search methods
    """
    # ── Collect unique paper IDs and group chunks ────────────────────────
    # Use OrderedDict so higher-ranked papers appear first
    papers_map: OrderedDict[int, dict] = OrderedDict()

    for chunk in bm25_results:
        pid = chunk["paper_id"]
        if pid not in papers_map:
            papers_map[pid] = {"title": chunk["paper_title"], "chunks": OrderedDict()}
        cid = chunk["id"]
        if cid not in papers_map[pid]["chunks"]:
            papers_map[pid]["chunks"][cid] = {
                "section": chunk["section_title"] or "",
                "text": chunk["text_content"],
            }

    for chunk in semantic_results:
        pid = chunk["paper_id"]
        if pid not in papers_map:
            papers_map[pid] = {"title": chunk["paper_title"], "chunks": OrderedDict()}
        cid = chunk["id"]
        if cid not in papers_map[pid]["chunks"]:
            papers_map[pid]["chunks"][cid] = {
                "section": chunk["section_title"] or "",
                "text": chunk["text_content"],
            }

    if not papers_map:
        return []

    # ── Fetch paper-level data: abstract + images (with signed URLs) ────
    paper_ids = list(papers_map.keys())
    papers_qs = (
        ResearchPaper.objects.filter(id__in=paper_ids)
        .prefetch_related("images")
        .only("id", "title", "abstract")
    )

    paper_db_map = {}
    for paper in papers_qs:
        paper_db_map[paper.id] = {
            "abstract": paper.abstract or "",
            "images": [
                {
                    "description": img.description or "",
                    "signed_url": img.get_secure_link(),
                    "original_url": img.link,
                }
                for img in paper.images.all()
            ],
        }

    # ── Build final structured output ───────────────────────────────────
    result = []
    for pid, data in papers_map.items():
        db_data = paper_db_map.get(pid, {"abstract": "", "images": []})
        result.append(
            {
                "paper_id": pid,
                "title": data["title"],
                "abstract": db_data["abstract"],
                "images": db_data["images"],
                "relevant_chunks": list(data["chunks"].values()),
            }
        )

    return result


def stream_llm_response(user_query: str, chat_history: str = ""):
    yield {"type": "status", "message": "Optimizing semantic query..."}
    optimized_query = optimize_semantic_query(user_query)
    
    yield {"type": "status", "message": "Evaluating chat context and routing intent..."}
    router_decision = get_route(optimized_query, short_chat_history=chat_history)
    route = router_decision.route
    yield {"type": "status", "message": f"Router selected path: {route.value}"}
    
    # Fast path if info is already in history
    if route == RouteChoice.CHAT or route == RouteChoice.FOLLOW_UP_HISTORY:
        yield {"type": "status", "message": "Skipping DB retrieval, generating response from history..."}
        # Yield generator tokens
        yield from generate_stream(user_query, "", chat_history, route.value)
        return

    yield {"type": "status", "message": "Extracting search facets (keywords, entities)..."}
    # Pass the original query to extract facets as GLiNER might need conversational context or capitalized entities
    extracted = extract_facets_from_query(user_query=user_query)
    
    papers_context = []
    graph_results = []

    # POSTGRES PATH
    if route in [RouteChoice.SEARCH_PAPERS, RouteChoice.SEARCH_BOTH]:
        yield {"type": "status", "message": "Searching Postgres (Facets & Semantic)..."}
        filtered_papers = facet_search_postgres(extracted["hard_filters"])
        
        bm25_results = bm25_search_chunks(
            bm25_query=extracted["bm25_query"],
            filtered_papers=filtered_papers,
        )
        
        semantic_results = semantic_search_postgres(
            filtered_papers, extracted["semantic_query"]
        )
        
        yield {"type": "status", "message": "Reranking chunks with Cross-Encoder for maximum relevance..."}
        # Merge results for reranking
        all_chunks = bm25_results + semantic_results
        
        # Rerank to get ONLY the top 5 absolute most relevant chunks to prevent LLM overload
        top_reranked_chunks = rerank_chunks(user_query, all_chunks, top_k=5)
        
        # Since _build_paper_context treats bm25 & semantic separately mainly for grouping, 
        # we can just pass the reranked chunks as one list and an empty list for the other
        papers_context = _build_paper_context(top_reranked_chunks, [])
        yield {"type": "status", "message": f"Successfully isolated {len(top_reranked_chunks)} highly relevant chunks across {len(papers_context)} papers."}
        
    # NEO4J PATH
    if route in [RouteChoice.SEARCH_GRAPH, RouteChoice.SEARCH_BOTH]:
        yield {"type": "status", "message": "Searching Neo4j for relationships..."}
        graph_results = query_graph_with_facets(
            hard_filters=extracted["hard_filters"],
            enrichment_terms=extracted["enrichment_terms"],
        )
        yield {"type": "status", "message": "Graph retrieval complete."}

    # Assembling Context
    yield {"type": "status", "message": "Assembling complete context for LLM..."}
    
    context_str = ""
    if papers_context:
        for p in papers_context:
            context_str += f"\\n\\n--- PAPER ID: {p['paper_id']} | TITLE: {p['title']} ---\\n"
            context_str += f"ABSTRACT: {p['abstract']}\\n"
            for chunk in p["relevant_chunks"]:
                context_str += f"SECTION {chunk['section']}: {chunk['text']}\\n"
            for img in p["images"]:
                context_str += f"![{img['description']}]({img['signed_url']})\\n"
                
    if graph_results:
        context_str += f"\\n\\n--- GRAPH CONTEXT ---\\n{graph_results}\\n"

    # Now generate text
    yield {"type": "status", "message": "Generating final scientific response..."}
    yield {"type": "data", "papers": papers_context} # Optionally send data immediately
    
    yield from generate_stream(user_query, context_str, chat_history, route.value)

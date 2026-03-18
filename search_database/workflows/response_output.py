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


def _build_paper_context(bm25_results: list[dict], semantic_results: list[dict], request=None) -> list[dict]:
    """
    Groups BM25 and semantic search results by paper, deduplicates chunks,
    and fetches paper-level metadata (abstract, images with signed URLs).
    """
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

    paper_ids = list(papers_map.keys())
    papers_qs = (
        ResearchPaper.objects.filter(id__in=paper_ids)
        .prefetch_related("images", "authors")
        .only("id", "title", "abstract", "link")
    )

    paper_db_map = {}
    import re
    for paper in papers_qs:
        images_data = []
        for img in paper.images.all():
            signed_url = img.get_secure_link()
            # If the URL is relative (fallback proxy), make it absolute
            if signed_url.startswith('/') and request:
                signed_url = request.build_absolute_uri(signed_url)
            
            images_data.append({
                "id": img.id,
                "paper_id": paper.id,
                "description": img.description or "",
                "signed_url": signed_url,
                "original_url": img.link,
            })

        # Extract PMCID from link
        match = re.search(r"(PMC\d+)", paper.link or "")
        pmcid = match.group(1) if match else str(paper.id)

        paper_db_map[paper.id] = {
            "pmcid": pmcid,
            "abstract": paper.abstract or "",
            "images": images_data,
            "authors": [a.name for a in paper.authors.all()],
        }

    result = []
    for pid, data in papers_map.items():
        db_data = paper_db_map.get(pid, {"pmcid": str(pid), "abstract": "", "images": [], "authors": []})
        result.append(
            {
                "id": pid, # Keep internal PK for saving/lookups
                "paper_id": db_data["pmcid"], # Use PMCID for LLM context and Citations
                "title": data["title"],
                "abstract": db_data["abstract"],
                "images": db_data["images"],
                "authors": db_data["authors"],
                "relevant_chunks": list(data["chunks"].values()),
            }
        )

    return result


def stream_llm_response(user_query: str, chat_history: str = "", request=None):
    yield {"type": "status", "message": "Optimizing semantic query..."}
    optimized_query = optimize_semantic_query(user_query)
    
    yield {"type": "status", "message": "Evaluating chat context and routing intent..."}
    router_decision = get_route(optimized_query, short_chat_history=chat_history)
    route = router_decision.route
    yield {"type": "status", "message": f"Router selected path: {route.value}"}
    
    if route == RouteChoice.CHAT or route == RouteChoice.FOLLOW_UP_HISTORY:
        yield {"type": "status", "message": "Skipping DB retrieval, generating response from history..."}
        yield from generate_stream(user_query, "", chat_history, route.value)
        return

    yield {"type": "status", "message": "Extracting search facets (keywords, entities)..."}
    extracted = extract_facets_from_query(user_query=user_query)
    
    papers_context = []
    graph_results = []

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
        all_chunks = bm25_results + semantic_results
        top_reranked_chunks = rerank_chunks(user_query, all_chunks, top_k=5)
        
        papers_context = _build_paper_context(top_reranked_chunks, [], request=request)
        yield {"type": "status", "message": f"Successfully isolated {len(top_reranked_chunks)} highly relevant chunks across {len(papers_context)} papers."}
        
    if route in [RouteChoice.SEARCH_GRAPH, RouteChoice.SEARCH_BOTH]:
        yield {"type": "status", "message": "Searching Neo4j for relationships..."}
        graph_results = query_graph_with_facets(
            hard_filters=extracted["hard_filters"],
            enrichment_terms=extracted["enrichment_terms"],
        )
        yield {"type": "status", "message": "Graph retrieval complete."}

    yield {"type": "status", "message": "Assembling complete context for LLM..."}
    
    context_str = ""
    if papers_context:
        for p in papers_context:
            context_str += f"\n\n--- PAPER ID: {p['paper_id']} | TITLE: {p['title']} ---\n"
            context_str += f"ABSTRACT: {p['abstract']}\n"
            for chunk in p["relevant_chunks"]:
                context_str += f"SECTION {chunk['section']}: {chunk['text']}\n"
            for img in p["images"]:
                context_str += f"IMAGE_AVAILABLE: ![{img['description']}]({img['signed_url']})\n"
                
    if graph_results:
        context_str += f"\n\n--- GRAPH CONTEXT ---\n{graph_results}\n"

    yield {"type": "status", "message": "Generating final scientific response..."}
    yield {"type": "data", "papers": papers_context}
    
    yield from generate_stream(user_query, context_str, chat_history, route.value, papers=papers_context)

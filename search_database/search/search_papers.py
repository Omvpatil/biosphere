# services/search.py

from django.db.models import Q, F
from django.contrib.postgres.search import SearchQuery, SearchRank
from pgvector.django import CosineDistance
from search_database.models import DocumentChunks, ResearchPaper
from search_database.services.generate_embeddings import get_embeddings
from graph_database.models import Author, Paper

import logging

logger = logging.getLogger(__name__)


def facet_search_postgres(hard_filters: dict):
    """
    Filters ResearchPaper using only structured DB columns.
    Receives hard_filters from extract_facets_from_query(), NOT the full facets dict.

    hard_filters shape:
    {
        "author_name": "Nickerson",       # → authors__name__icontains
    }
    """
    db_query = Q()

    if author := hard_filters.get("author_name"):
        db_query &= Q(authors__name__icontains=author)

    if year := hard_filters.get("publication_year"):
        try:
            db_query &= Q(published_year=int(year))
        except (ValueError, TypeError):
            logger.warning(f"Could not parse publication_year: {year!r}")

    if journal := hard_filters.get("journal_name"):
        db_query &= Q(citations__journal_name__icontains=journal)

    if db_query == Q():
        return ResearchPaper.objects.all()

    return ResearchPaper.objects.filter(db_query).distinct()


def bm25_search_chunks(
    bm25_query: str,
    filtered_papers,
    top_k: int = 5,
) -> list[dict]:
    """
    BM25-like FTS on DocumentChunks, scoped to papers from faceted filter.
    Receives bm25_query from extract_facets_from_query()["bm25_query"].
    """
    if not bm25_query or not bm25_query.strip():
        return []

    query = SearchQuery(bm25_query, config="english", search_type="websearch")

    results = (
        DocumentChunks.objects.filter(
            paper__in=filtered_papers,
            search_vector__isnull=False,
            search_vector=query,
        )
        .annotate(
            bm25_rank=SearchRank(
                F("search_vector"),
                query,
                weights=[0.1, 0.4, 0.6, 1.0],
                cover_density=True,
                normalization=2,
            )
        )
        .select_related("paper")
        .order_by("-bm25_rank")
        .values(
            "id",
            "paper_id",
            "text_content",
            "section_title",
            "paper__title",
            "bm25_rank",
        )[:top_k]
    )

    return [
        {
            "id": r["id"],
            "paper_id": r["paper_id"],
            "paper_title": r["paper__title"],
            "section_title": r["section_title"],
            "text_content": r["text_content"],
            "bm25_rank": r["bm25_rank"],
        }
        for r in results
    ]


def semantic_search_postgres(
    filtered_papers,
    semantic_query: str,  # ← now uses extracted["semantic_query"]
    top_k: int = 5,
) -> list[dict]:
    """
    Semantic search on DocumentChunks scoped to facet-filtered papers.
    Receives semantic_query from extract_facets_from_query()["semantic_query"].
    """
    embedded_query = get_embeddings(semantic_query)

    results = (
        DocumentChunks.objects.filter(paper__in=filtered_papers)
        .annotate(distance=CosineDistance("embedding", embedded_query))
        .order_by("distance")
        .select_related("paper")
        .values(
            "id",
            "paper_id",
            "text_content",
            "section_title",
            "paper__title",
            "distance",
        )[:top_k]
    )

    return [
        {
            "id": r["id"],
            "paper_id": r["paper_id"],
            "paper_title": r["paper__title"],
            "section_title": r["section_title"],
            "text_content": r["text_content"],
            "semantic_score": 1 - r["distance"],
        }
        for r in results
    ]


def reciprocal_rank_fusion(
    bm25_results: list[dict],
    semantic_results: list[dict],
    k: int = 60,
    bm25_weight: float = 0.4,
    semantic_weight: float = 0.6,
) -> list[dict]:
    """
    Merges BM25 and semantic ranked lists.
    RRF score = bm25_weight/(k + bm25_rank) + semantic_weight/(k + semantic_rank)
    """
    scores: dict[int, float] = {}

    for rank, item in enumerate(bm25_results, start=1):
        chunk_id = item["id"]
        scores[chunk_id] = scores.get(chunk_id, 0.0) + bm25_weight / (k + rank)

    for rank, item in enumerate(semantic_results, start=1):
        chunk_id = item["id"]
        scores[chunk_id] = scores.get(chunk_id, 0.0) + semantic_weight / (k + rank)

    sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [{"id": chunk_id, "rrf_score": score} for chunk_id, score in sorted_ids]


def rerank_chunks(user_query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """
    Reranks a combined list of BM25 and Semantic chunks using a Cross-Encoder.
    This significantly reduces hallucination and context window size for the LLM.
    """
    if not chunks:
        return []

    try:
        from sentence_transformers import CrossEncoder

        # Use a lightweight, fast, and highly accurate cross-encoder
        reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    except ImportError:
        logger.warning("sentence-transformers not installed. Skipping reranking.")
        return chunks[:top_k]
    except Exception as e:
        logger.error(f"Failed to load cross-encoder model: {e}")
        return chunks[:top_k]

    # Deduplicate chunks based on chunk ID (to prevent scoring the same chunk twice if found by both BM25 and Semantic)
    unique_chunks_map = {chunk["id"]: chunk for chunk in chunks}
    unique_chunks = list(unique_chunks_map.values())

    # Prepare inputs for the cross-encoder: pairs of [Query, Chunk Text]
    cross_input = [
        [user_query, chunk.get("text_content", "")] for chunk in unique_chunks
    ]

    try:
        # Predict relevance scores (higher is better)
        scores = reranker.predict(cross_input)

        for i, chunk in enumerate(unique_chunks):
            chunk["rerank_score"] = float(scores[i])

        # Sort by higher score
        ranked_chunks = sorted(
            unique_chunks, key=lambda x: x["rerank_score"], reverse=True
        )
        return ranked_chunks[:top_k]

    except Exception as e:
        logger.error(f"Reranking prediction failed: {e}")
        return unique_chunks[:top_k]


def query_graph_with_facets(hard_filters: dict, enrichment_terms: dict):
    """
    Pulls relationship-heavy context from Neo4j.

    hard_filters    → author_name (for co-author graph traversal)
    enrichment_terms → gene_or_protein, organism_or_species, space_environment
                       (for paper/visual lookups by concept)
    """
    context_segments = []

    if author_name := hard_filters.get("author_name"):
        try:
            author = Author.nodes.get(name__icontains=author_name)
            papers = author.papers.all()[:5]
            paper_titles = [p.title for p in papers]
            context_segments.append(
                f"Author {author.name} has contributed to: {', '.join(paper_titles)}"
            )
            co_authors = set()
            for p in papers:
                for a in p.authors.all():
                    if a.name != author.name:
                        co_authors.add(a.name)
            if co_authors:
                context_segments.append(
                    f"{author.name} frequently collaborates with: {', '.join(list(co_authors)[:5])}"
                )
        except Author.DoesNotExist:
            pass

    concept_keys = ["gene_or_protein", "organism_or_species", "space_environment"]
    for key in concept_keys:
        if term := enrichment_terms.get(key):
            related_papers = Paper.nodes.filter(abstract__icontains=term)[:3]
            for p in related_papers:
                images = [img.image_link for img in p.images.all()]
                context_segments.append(
                    f"Paper on {term}: '{p.title}'. Visuals: {images}"
                )

    return "\n".join(context_segments)


def query_web(query: str):
    """
    Search thorugh web using duckduck go or serXCH or other searching for fact checking the current resutls
    """
    pass

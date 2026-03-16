import re
import logging
from typing import Any, Dict, List
from django.apps import apps

logger = logging.getLogger(__name__)

# Labels that map to real DB columns — used as hard .filter() calls
HARD_FILTER_LABELS = {
    "author_name",
}

# Labels with no DB column — enriched into the BM25/semantic query string
QUERY_ENRICHMENT_LABELS = {
    "organism_or_species",
    "gene_or_protein",
    "anatomy_or_organ",
    "biological_process",
    "space_environment",
    "journal_name",  # no field on ResearchPaper, but useful for BM25 on chunks
}

STOPWORD_PRONOUNS = {"i", "my", "me", "we", "he", "she", "they", "us", "our"}

CONVERSATIONAL_PATTERNS = [
    r"(?i)^(can you )?(find|show me|look for|get me) (articles|papers|studies|research) (about|on|discussing|that investigate)?\s?",
    r"(?i)^(i am )?(looking for|interested in finding) (research|studies|articles|papers) (about|on)?\s?",
    r"(?i)^(what are the )?(recent|latest) (findings|publications|advancements) (on|about|in our understanding of)?\s?",
    r"(?i)^i need information on (the latest research about )?\s?",
    r"(?i)^(tell me about|explain|summarize) (research|papers|studies) (on|about)?\s?",
    r"(?i)^(are there any )?(papers|studies|articles|research) (on|about|that discuss)?\s?",
]


def extract_facets_from_query(user_query: str) -> Dict[str, Any]:
    """
    Splits GLiNER entities into:
      - hard_filters : map directly to DB .filter() calls
      - enrichment_terms : folded into BM25/semantic query string
      - semantic_query : cleaned query + enrichment terms appended

    Returns:
    {
        "hard_filters": {
            "author_name": "Nickerson",           # → authors__name__icontains
        },
        "enrichment_terms": {
            "organism_or_species": "Salmonella",
            "space_environment": "microgravity",
            "gene_or_protein": "Hfq",
            "biological_process": "biofilm formation",
        },
        "bm25_query": "Salmonella microgravity Hfq biofilm formation",  # ← fed to BM25
        "semantic_query": "Salmonella in microgravity Hfq biofilm formation",
        "user_query": "original user query",
        "raw_entities": [...]   # full GLiNER output for debugging
    }
    """
    model = apps.get_app_config("search_database").nlp_model
    if model is None:
        logger.error("GLiNER model not loaded. Skipping entity extraction.")
        return {
            "hard_filters": {},
            "enrichment_terms": {},
            "bm25_query": user_query,
            "semantic_query": user_query,
            "user_query": user_query,
            "raw_entities": [],
        }

    labels = list(HARD_FILTER_LABELS | QUERY_ENRICHMENT_LABELS)
    entities: List[Dict] = model.predict_entities(user_query, labels, threshold=0.45)

    hard_filters: Dict[str, str] = {}
    enrichment_terms: Dict[str, str] = {}

    for entity in entities:
        label = entity["label"]
        text = entity["text"].strip()

        # Skip pronoun false positives on author_name
        if label == "author_name" and text.lower() in STOPWORD_PRONOUNS:
            continue

        # Skip very short extractions (likely noise)
        if len(text) < 2:
            continue

        if label in HARD_FILTER_LABELS:
            hard_filters[label] = text
        elif label in QUERY_ENRICHMENT_LABELS:
            enrichment_terms[label] = text

    # ── Build BM25 query: just the extracted terms concatenated
    # These are the specific biological/environmental terms GLiNER found —
    # they are exactly what BM25 should score against in DocumentChunks
    bm25_terms = list(enrichment_terms.values())
    bm25_query = " ".join(bm25_terms) if bm25_terms else user_query

    semantic_query = user_query
    for pattern in CONVERSATIONAL_PATTERNS:
        semantic_query = re.sub(pattern, "", semantic_query).strip()

    if bm25_terms and semantic_query:
        extra = [t for t in bm25_terms if t.lower() not in semantic_query.lower()]
        if extra:
            semantic_query = f"{semantic_query} {' '.join(extra)}"

    return {
        "hard_filters": hard_filters,
        "enrichment_terms": enrichment_terms,
        "bm25_query": bm25_query,
        "semantic_query": semantic_query,
        "user_query": user_query,
        "raw_entities": entities,
    }

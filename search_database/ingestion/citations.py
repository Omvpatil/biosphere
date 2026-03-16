from typing import Any, Dict
from search_database.models import Citations, ResearchPaper

import logging

logger = logging.getLogger(__name__)


def store_citations(paper_instance: ResearchPaper, data: Dict[str, Any]):
    """
    Takes the saved ResearchPaper instance asn the extracted citaitons are stored into database
    """
    logger.info(f"Storing citations for {data['pmcid']}")
    Citations.objects.filter(paper=paper_instance).delete()

    citation_objects = [
        Citations(
            paper=paper_instance,
            raw_text=(
                cite["raw_text"][:252] + "..."
                if len(cite["raw_text"]) > 255
                else cite["raw_text"]
            ),
            cited_authors=cite.get("cited_authors"),
            publication_year=cite.get("publication_year"),
            journal_name=cite.get("journal_name"),
            doi=cite.get("doi"),
            pmid=cite.get("pmid"),
            pmcid=cite.get("pmcid"),
            citation_context=cite.get("citation_context"),
        )
        for cite in data["citations"]
    ]
    Citations.objects.bulk_create(citation_objects)
    logger.info(f"Stored citations for {data['pmcid']}")

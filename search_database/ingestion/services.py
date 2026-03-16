from typing import Any, Dict

from search_database.extraction.extracters import (
    extract_citations,
    extract_images,
    extract_metadata,
    extract_text_chunks,
)
from search_database.extraction.fetchers import fetch_paper_soup

import logging

logger = logging.getLogger(__name__)


def process_research_paper(pmcid: str) -> Dict[str, Any]:
    """
    Downloads the paper ONCE and runs all extractors.
    Returns a unified dictionary ready for the database.
    """
    logger.info(f"Fetching XML for {pmcid}")
    soup = fetch_paper_soup(pmcid)

    logger.info("Parsing components...")
    return {
        "pmcid": pmcid,
        "metadata": extract_metadata(soup),
        "chunks": extract_text_chunks(soup),
        "citations": extract_citations(soup),
        "images": extract_images(soup, pmcid),
    }

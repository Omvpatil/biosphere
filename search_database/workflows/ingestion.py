import requests
import logging
from django.db import transaction
from tenacity import retry, wait_exponential, stop_after_attempt
from tenacity.retry import retry_if_exception_type

from search_database.ingestion.authors import store_authors
from search_database.ingestion.citations import store_citations
from search_database.ingestion.embeddings import create_embedded_chunks
from search_database.ingestion.images import store_images
from search_database.ingestion.services import process_research_paper
from search_database.models import ResearchPaper

logger = logging.getLogger(__name__)


def on_retry_failure(retry_state):
    logger.error(
        f"All {retry_state.attempt_number} retries failed for "
        f"{retry_state.args[0]} — "  # pmcid argument
        f"Final error: {retry_state.outcome.exception()}"
    )
    return None


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=8),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(
        (requests.RequestException, ConnectionError, TimeoutError)
    ),
    before_sleep=lambda retry_state: logger.warning(
        f"Error occurred: {retry_state.outcome.exception()} — retrying {retry_state.attempt_number} time(s)..."
    ),
    retry_error_callback=on_retry_failure,
)
@transaction.atomic
def add_single_paper_to_database(pmcid: str):
    logger.info(f"Starting ingestion for {pmcid}")
    paper_link = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
    if ResearchPaper.objects.filter(
        link__in=[paper_link, paper_link.rstrip("/")]
    ).exists():
        logger.info(f"{pmcid} Already exist in database skipping...")
        return f"Skipped: {pmcid} already exists"
    data = process_research_paper(pmcid)
    paper_instance = ResearchPaper.objects.create(
        title=data["metadata"]["title"],
        link=f"https://www.ncbi.nlm.nih.gov/pmc/articles/{data['pmcid']}/",
        abstract=data["metadata"]["abstract"],
        distribution=data["metadata"]["distribution"],
    )

    store_authors(paper_instance, data)
    store_images(paper_instance, data)
    store_citations(paper_instance, data)
    create_embedded_chunks(paper_instance, data)
    logger.info(f"Completed ingestion for {pmcid}")
    return {"msg": f"Successfully ingested: {pmcid}"}

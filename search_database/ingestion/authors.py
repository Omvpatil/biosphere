from typing import Any, Dict
from search_database.models import Author, ResearchPaper
import logging

logger = logging.getLogger(__name__)


def store_authors(paper_instance: ResearchPaper, data: Dict[str, Any]):
    logger.info(f"Storing Authors for {data['pmcid']}")
    author_obj_list = []
    for author_name in data["metadata"]["authors"]:
        author_obj, _ = Author.objects.get_or_create(name=author_name)
        author_obj_list.append(author_obj)
    paper_instance.authors.set(author_obj_list)
    logger.info(f"Stored Authors for {data['pmcid']}")

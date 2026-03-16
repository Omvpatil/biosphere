from typing import Any, Dict

from langchain_text_splitters import RecursiveCharacterTextSplitter

from search_database.models import DocumentChunks, ResearchPaper

import logging

from search_database.services.generate_embeddings import get_batch_embeddings

logger = logging.getLogger(__name__)


def create_embedded_chunks(paper_instance: ResearchPaper, data: Dict[str, Any]):
    """
    Takes the saved ResearchPaper instance and the extracted chunks dictionary,
    generates vector embeddings, and saves them to the database.
    """
    logger.info(f"Creating and storing chunks for {data['pmcid']}")
    DocumentChunks.objects.filter(paper=paper_instance).delete()

    text_spitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, length_function=len
    )
    final_chunks = []
    chunk_counter = 1

    for section in data["chunks"]:
        section_title = section["section_title"]
        section_content = section["text_content"]

        split_texts = text_spitter.split_text(section_content)

        for split_text in split_texts:
            final_chunks.append(
                {
                    "chunk_index": chunk_counter,
                    "section_title": section_title,
                    "text_content": split_text,
                }
            )
    texts_to_embed = [
        f"{chunk['section_title']}\n{chunk['text_content']}" for chunk in final_chunks
    ]
    embeddings_list = get_batch_embeddings(texts_to_embed)

    chunk_objects = [
        DocumentChunks(
            paper=paper_instance,
            chunk_index=idx + 1,
            section_title=chunk["section_title"],
            text_content=chunk["text_content"],
            embedding=embeddings_list[idx],
        )
        for idx, chunk in enumerate(final_chunks)
    ]

    DocumentChunks.objects.bulk_create(chunk_objects)
    logger.info(f"Created saved {len(chunk_objects)} chunks")

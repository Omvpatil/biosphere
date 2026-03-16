from typing import Any, Dict, List

from bs4 import BeautifulSoup


def extract_metadata(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extracts top-level data for the ResearchPaper model, including authors."""
    title_tag = soup.find("article-title")
    abstract_tag = soup.find("abstract")

    publisher_tag = soup.find("publisher-name")
    distribution_name = (
        publisher_tag.get_text(strip=True) if publisher_tag else "Unknown Publisher"
    )
    paper_authors = []
    contrib_group = soup.find("contrib-group")

    if contrib_group:
        # Find every contributor labeled specifically as an 'author'
        for contrib in contrib_group.find_all("contrib", {"contrib-type": "author"}):
            name_tag = contrib.find("name")
            if name_tag:
                surname = name_tag.find("surname")
                given = name_tag.find("given-names")

                # Format as "Lastname, Firstname" to keep your database clean
                if surname and given:
                    paper_authors.append(
                        f"{surname.get_text(strip=True)}, {given.get_text(strip=True)}"
                    )
                elif surname:
                    paper_authors.append(surname.get_text(strip=True))

    return {
        "title": title_tag.get_text(strip=True) if title_tag else "Unknown Title",
        "abstract": (
            "\n".join([p.get_text(strip=True) for p in abstract_tag.find_all("p")])
            if abstract_tag
            else ""
        ),
        "authors": paper_authors,
        "distribution": distribution_name,
    }


def extract_text_chunks(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Extracts semantic chunks for the DocumentChunks model."""
    chunks = []

    # Unstructured Body Text
    body_tag = soup.find("body")
    if body_tag:
        loose_paragraphs = body_tag.find_all("p", recursive=False)
        if loose_paragraphs:
            chunks.append(
                {
                    "section_title": "Main Text",
                    "text_content": "\n".join(
                        [p.get_text(strip=True) for p in loose_paragraphs]
                    ),
                }
            )

    # Structured Sections
    for sec in soup.find_all("sec"):
        title_tag = sec.find("title")
        section_title = (
            title_tag.get_text(strip=True) if title_tag else "Untitled Section"
        )
        sec_paragraphs = sec.find_all("p", recursive=False)

        if sec_paragraphs:
            chunks.append(
                {
                    "section_title": section_title,
                    "text_content": "\n".join(
                        [p.get_text(strip=True) for p in sec_paragraphs]
                    ),
                }
            )

    return chunks


def extract_citations(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extracts structured citation data tailored exactly for the Citations Django model.
    """
    reference_map = {}

    # 1. Build the dictionary with all structured metadata
    for ref in soup.find_all("ref"):
        ref_id = ref.get("id")

        # --- RAW TEXT ---
        mixed_citation = ref.find("mixed-citation")
        raw_text = (
            mixed_citation.get_text(strip=True)
            if mixed_citation
            else "Unknown Citation"
        )
        # Truncate to 255 characters to respect Django's max_length=255 constraint
        raw_text = raw_text[:252] + "..." if len(raw_text) > 255 else raw_text

        # --- AUTHORS ---
        authors = []
        for name in ref.find_all("name"):
            surname = name.find("surname")
            given = name.find("given-names")
            if surname and given:
                authors.append(
                    f"{surname.get_text(strip=True)}, {given.get_text(strip=True)}"
                )
            elif surname:
                authors.append(surname.get_text(strip=True))
        author_string = ", ".join(authors) if authors else None

        # --- PUBLICATION YEAR ---
        year_tag = ref.find("year")
        publication_year = None
        if year_tag and year_tag.get_text(strip=True).isdigit():
            publication_year = int(year_tag.get_text(strip=True))

        # --- JOURNAL NAME ---
        source_tag = ref.find("source")
        journal_name = source_tag.get_text(strip=True) if source_tag else None

        # --- IDENTIFIERS (DOI, PMID, PMCID) ---
        doi_tag = ref.find("pub-id", {"pub-id-type": "doi"})
        doi = doi_tag.get_text(strip=True) if doi_tag else None

        pmid_tag = ref.find("pub-id", {"pub-id-type": "pmid"})
        pmid = pmid_tag.get_text(strip=True) if pmid_tag else None

        pmcid_tag = ref.find("pub-id", {"pub-id-type": "pmcid"})
        pmcid = pmcid_tag.get_text(strip=True) if pmcid_tag else None

        # Save all extracted fields to the reference map
        if ref_id:
            reference_map[ref_id] = {
                "raw_text": raw_text,
                "cited_authors": author_string,
                "publication_year": publication_year,
                "journal_name": journal_name,
                "doi": doi,
                "pmid": pmid,
                "pmcid": pmcid,
            }

    # 2. Map the structured references to the body context
    citations_data = []
    for p in soup.find_all("p"):
        citations_in_para = p.find_all("xref", {"ref-type": "bibr"})

        if citations_in_para:
            context_text = p.get_text(strip=True)
            for xref in citations_in_para:
                rid = xref.get("rid")

                # If the citation exists in our map, attach the context and append it
                if rid in reference_map:
                    citation_record = reference_map[rid].copy()
                    citation_record["citation_context"] = context_text
                    citations_data.append(citation_record)

    return citations_data


def extract_images(soup: BeautifulSoup, pmcid: str) -> List[Dict[str, str]]:
    """Extracts stable figure links using the PMC article structure."""
    images = []

    for fig in soup.find_all("fig"):
        # We grab the 'id' attribute from the <fig> tag (e.g., 'Fig1')
        fig_id = fig.get("id")
        caption_tag = fig.find("caption")

        # If the figure has an ID, we can build a stable link
        if fig_id:
            caption_text = (
                caption_tag.get_text(strip=True) if caption_tag else "No Caption"
            )

            images.append({"fig_id": fig_id, "description": caption_text})

    return images

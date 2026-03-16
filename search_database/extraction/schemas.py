from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from pydantic.networks import HttpUrl


class ImageNodeSchema(BaseModel):
    """
    Images containing the Research Papers
    """

    model_config = ConfigDict(title="Extracted_Figure_or_Link", from_attributes=True)
    link: HttpUrl = Field(
        description="Link of the image from where the data is extracted"
    )
    description: str = Field(
        description="Description and captions of image given by research paper"
    )


class CitationSchema(BaseModel):
    """
    Citation schema containing :
    cited authors
    publication year
    journal name
    doi of research paper
    PMID and PMCID of research paper
    Citation Context which tells how the research paper and citaion is related to research paper
    """

    model_config = ConfigDict(title="Bibilography_Citations", from_attributes=True)
    raw_text: str = Field(
        description="The complete, raw citation string exactly as it appears in the bibliography (e.g., 'Smith J, et al. Title. Journal. 2023')."
    )

    cited_authors: str = Field(
        description="A comma-separated list of the authors of the cited work."
    )

    publication_year: Optional[int] = Field(
        description="The 4-digit year the cited paper was published."
    )

    journal_name: Optional[str] = Field(
        default=None,
        description="The name of the journal or publication (e.g., 'npj Microgravity', 'Nature').",
    )
    doi: Optional[str] = Field(
        default=None,
        description="The Digital Object Identifier (DOI) if present, e.g., '10.1038/s41526-024-00419-y'.",
    )
    pmid: Optional[str] = Field(
        default=None,
        description="The PubMed ID (PMID) if present. Usually an 8-digit number.",
    )
    pmcid: Optional[str] = Field(
        default=None,
        description="The PubMed Central ID if present. Always starts with 'PMC' followed by numbers.",
    )
    citation_context: Optional[str] = Field(
        default=None,
        description="The exact sentence or paragraph from the main text where this specific citation was referenced.",
    )


class ResearchPaperExtraction(BaseModel):
    """
    Whole research paper meta data important for defining Relationships between multiple research papers and increasing the accuracy
    """

    model_config = ConfigDict(title="Space_Biology_Research_Paper")

    title: str = Field(description="The main title of the research paper.")
    link: str = Field(
        default="",
        description="The source URL or DOI link of this specific research paper.",
    )
    authors: List[str] = Field(
        description="A list of the authors who wrote this paper. Extract each name as a separate string."
    )
    abstract: Optional[str] = Field(
        default=None, description="The full text of the abstract section."
    )
    description: Optional[str] = Field(
        default=None,
        description="A brief 1-2 sentence summary of the paper's main objective or findings.",
    )
    distribution: Optional[str] = Field(
        default=None,
        description="The distribution rights or license of the paper (e.g., 'Open Access', 'Internal NASA Use Only', 'CC-BY').",
    )

    # Nested Relationships: The LLM will extract these as lists of objects!
    images: List[ImageNodeSchema] = Field(
        default_factory=list,
        description="A list of all figures, charts, and images referenced in the paper.",
    )
    citations: List[CitationSchema] = Field(
        default_factory=list,
        description="A list of all references and citations found in the bibliography section.",
    )


class AuthorSchema(BaseModel):
    model_config = ConfigDict(
        title="Name of author of the research paper with comma seperated values in list format"
    )
    name: str = Field(
        description="A list of the authors who wrote this paper. Extract each name as a separate string."
    )


class AIResponce(BaseModel):
    model_config = ConfigDict(title="")

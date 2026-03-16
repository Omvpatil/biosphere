from typing import List
from pydantic import BaseModel, Field


class StructuredAIResponse(BaseModel):
    answer: str = Field(
        description="The full Markdown-formatted scientific answer for the user. If you reference an image, use the [REF_IMG: ID] format."
    )
    meta_summary: str = Field(
        description="A 1-sentence summary of the main topics and IDs discussed in this turn. Crucial for memory."
    )
    paper_ids: List[int] = Field(
        default_factory=list,
        description="The integer IDs of the papers you actively used or cited in your answer.",
    )
    author_ids: List[int] = Field(
        default_factory=list,
        description="The integer IDs of the authors you explicitly mentioned.",
    )

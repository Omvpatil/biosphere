from django.utils import timezone
from django.conf import settings
from django.db import models
from biosphere.models import Author
from pgvector.django import HnswIndex, VectorField


class ImageNodes(models.Model):
    id = models.BigAutoField(primary_key=True)
    link = models.URLField(default="Link")
    description = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.description[:20]} ..."


class Citations(models.Model):
    id = models.BigAutoField(primary_key=True)
    raw_text = models.CharField(max_length=255, blank=False, default="Title")
    cited_authors = models.TextField(help_text="Comma seperated values of authors")
    publication_year = models.IntegerField(null=True, blank=True)
    journal_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="e.g., 'npj Microgravity', 'Nature'",
    )

    doi = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="e.g., 10.1038/s41526-024-00419-y",
    )
    pmid = models.CharField(
        max_length=50, null=True, blank=True, help_text="PubMed ID (e.g., 39030182)"
    )
    pmcid = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="PubMed Central ID (e.g., PMC11271499)",
    )
    citation_context = models.TextField(
        null=True,
        blank=True,
        help_text="The sentence in the source paper where this was cited",
    )


class ResearchPaper(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255, default="Title")
    link = models.URLField(max_length=255, default="Link")  #
    authors = models.ManyToManyField(Author, related_name="research_papers")
    abstract = models.TextField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    distribution = models.CharField(max_length=255, null=True)
    images = models.ManyToManyField(ImageNodes)
    cites = models.ManyToManyField(
        "self", symmetrical=False, related_name="cited_by", blank=True
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_papers",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.title}"


class DocumentChunks(models.Model):
    class Meta:
        indexes = [
            HnswIndex(
                name="research_paper_vectors_index",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]

    paper = models.ForeignKey(
        ResearchPaper, on_delete=models.CASCADE, related_name="chunks"
    )
    chunk_index = models.IntegerField(help_text="Number of chunk in the paper")
    section_title = models.CharField(max_length=255, blank=True, null=True)
    text_content = models.TextField(default="")

    embedding = VectorField(dimensions=1536, blank=True, null=True)

    def __str__(self):
        return f"{self.paper.title} Chunk - {self.chunk_index}"

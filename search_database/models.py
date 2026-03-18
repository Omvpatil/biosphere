from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.db import models
from django.core import signing
from pgvector.django import HnswIndex, VectorField
from django.contrib.postgres.search import SearchVectorField

class Author(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, default="Name")

    class Meta:
        db_table = "biosphere_author"

    def __str__(self):
        return f"{self.name}"


class ImageNodes(models.Model):
    id = models.BigAutoField(primary_key=True)
    link = models.URLField(default="Link")
    image_file = models.ImageField(upload_to="images/", blank=True, null=True)
    pmcid = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def get_secure_link(self):
        # Prefer the secure proxy for internal files (to solve Docker Loopback/CORS issues)
        if self.image_file:
            token = signing.dumps({"img_id": self.id})
            return reverse("secure_image", kwargs={"token": token})
        
        # If it's an external link, return it directly instead of redirecting through Django
        if self.link and self.link != "Link":
            return self.link

        return None

    def __str__(self) -> str:
        return f"{self.description[:20]} ..."


class ResearchPaper(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255, default="Title")
    link = models.URLField(max_length=255, default="Link")  #
    authors = models.ManyToManyField(Author, related_name="research_papers")
    abstract = models.TextField(null=True, blank=True)
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


class Citations(models.Model):
    id = models.BigAutoField(primary_key=True)
    raw_text = models.CharField(max_length=255, blank=False, default="Title")
    paper = models.ForeignKey(
        ResearchPaper, on_delete=models.CASCADE, related_name="citations", null=True
    )
    cited_authors = models.TextField(
        help_text="Comma seperated values of authors", null=True, blank=True
    )
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
    search_vector = SearchVectorField(null=True, blank=True)
    embedding = VectorField(dimensions=1024, blank=True, null=True)

    def __str__(self):
        return f"{self.paper.title} Chunk - {self.chunk_index}"

from neomodel import RelationshipFrom, RelationshipTo, StructuredNode, StructuredRel
from neomodel.properties import (
    StringProperty,
    UniqueIdProperty,
    DateProperty,
    IntegerProperty,
    FloatProperty,
    BooleanProperty,
    ArrayProperty,
)


# ── Relationship Models (with properties on the edge itself) ──────────────────


class AuthoredRel(StructuredRel):
    """Carries author order — first author vs contributor matters in academia"""

    position = IntegerProperty()  # 1 = first author, 2 = second, etc.
    is_corresponding = BooleanProperty(default=False)


class CitesRel(StructuredRel):
    """Context of where/how the citation appears in the paper"""

    citation_context = StringProperty()  # the sentence where it was cited
    section = StringProperty()  # Introduction, Methods, Results, etc.


class SimilarRel(StructuredRel):
    """Computed similarity score between two papers"""

    score = FloatProperty()  # cosine similarity from embeddings
    method = StringProperty()  # "embedding", "keyword", "manual"


class StudiesRel(StructuredRel):
    """Context of how the organism is studied"""

    study_type = StringProperty()
    condition = StringProperty()


# ── New Domain Nodes ──────────────────────────────────────────────────────────


class Journal(StructuredNode):
    """
    Pulled from Citations.journal_name — centralizes journal info.
    Enables: "Find all papers from Nature about microgravity"
    """

    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True, required=True)
    issn = StringProperty()

    papers = RelationshipFrom("Paper", "PUBLISHED_IN")


class Organism(StructuredNode):
    """
    Space biology is heavily organism-specific.
    Enables: "All papers studying mice in microgravity"
    Populated from GLiNER organism_or_species extractions.
    """

    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True, required=True)  # "Mus musculus"
    common_name = StringProperty()  # "mice"
    taxonomy = StringProperty()  # "mammal", "bacteria"

    studied_in = RelationshipFrom("Paper", "STUDIES_ORGANISM")


class Gene(StructuredNode):
    """
    Critical for space biology — gene expression changes in microgravity.
    Enables: "Which papers mention Hfq gene across different organisms?"
    Populated from GLiNER gene_or_protein extractions.
    """

    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True, required=True)  # "Hfq"
    organism = StringProperty()  # which organism it belongs to

    mentioned_in = RelationshipFrom("Paper", "MENTIONS_GENE")
    interacts_with = RelationshipTo("Gene", "INTERACTS_WITH")  # gene-gene interactions


class SpaceEnvironment(StructuredNode):
    """
    The core context of space biology research.
    Enables: "Papers about ISS vs rotating wall vessel experiments"
    Populated from GLiNER space_environment extractions.
    """

    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True, required=True)
    # e.g: "microgravity", "ISS", "rotating_wall_vessel",
    #       "simulated_microgravity", "spaceflight", "parabolic_flight"
    environment_type = StringProperty()  # "real_space", "simulated", "ground_control"

    papers = RelationshipFrom("Paper", "CONDUCTED_IN")


class BiologicalProcess(StructuredNode):
    """
    Enables: "Find papers about biofilm formation in any environment"
    Populated from GLiNER biological_process extractions.
    """

    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True, required=True)
    # e.g: "biofilm_formation", "virulence", "bone_loss",
    #       "muscle_atrophy", "immune_response"

    papers = RelationshipFrom("Paper", "INVESTIGATES_PROCESS")


# ── New Normalized Nodes ────────────────────────────────────────────────────────


class Year(StructuredNode):
    """
    Extracted from ResearchPaper.created_at.year and Citations.publication_year
    Enables: "All papers from 2020", "Citations from papers published in 2019"
    """

    uid = UniqueIdProperty()
    year = IntegerProperty(unique_index=True, required=True)

    papers = RelationshipFrom("Paper", "PUBLISHED_IN_YEAR")
    citations = RelationshipFrom("Cites", "FROM_YEAR")


class Distribution(StructuredNode):
    """
    Extracted from ResearchPaper.distribution
    Enables: "All open access papers", "Find subscription-only papers"
    Values: "open_access", "subscription", etc.
    """

    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True, required=True)
    description = StringProperty()

    papers = RelationshipFrom("Paper", "HAS_DISTRIBUTION")


class User(StructuredNode):
    """
    Extracted from ResearchPaper.added_by (FK to User)
    Enables: "Papers uploaded by user X", "Find most active contributors"
    """

    uid = UniqueIdProperty()
    name = StringProperty(required=True)
    email = StringProperty(unique_index=True, required=True)
    role = StringProperty()

    uploaded_papers = RelationshipFrom("Paper", "UPLOADED_BY")


class DOI(StructuredNode):
    """
    Extracted from Citations.doi
    Enables: "Find paper by DOI", "All citations with DOI resolved"
    """

    uid = UniqueIdProperty()
    doi = StringProperty(unique_index=True, required=True)

    citations = RelationshipFrom("Cites", "HAS_DOI")


class PMID(StructuredNode):
    """
    Extracted from Citations.pmid
    Enables: "Find citation by PubMed ID", "Link to PubMed"
    """

    uid = UniqueIdProperty()
    pmid = StringProperty(unique_index=True, required=True)

    citations = RelationshipFrom("Cites", "HAS_PMID")


class PMCID(StructuredNode):
    """
    Extracted from Citations.pmcid and ImageNodes.pmcid
    Enables: "Find by PubMed Central ID", "Link to PMC"
    """

    uid = UniqueIdProperty()
    pmcid = StringProperty(unique_index=True, required=True)

    citations = RelationshipFrom("Cites", "HAS_PMCID")
    visuals = RelationshipFrom("Visuals", "HAS_PMCID")


# ── Updated Core Nodes ────────────────────────────────────────────────────────


class Author(StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(required=True, unique_index=True)

    # existing
    papers = RelationshipFrom("Paper", "AUTHORED_BY", model=AuthoredRel)
    cited_papers = RelationshipFrom("Cites", "CONTRIBUTED_BY")

    # ✅ NEW — derived from co-authorship, very useful for collaboration context
    collaborates_with = RelationshipTo("Author", "COLLABORATES_WITH")


class Visuals(StructuredNode):
    uid = UniqueIdProperty()
    image_link = StringProperty(unique_index=True, required=True)
    image_dec = StringProperty()

    # existing
    paper = RelationshipFrom("Paper", "HAS_IMAGE")
    pmcid_node = RelationshipTo(PMCID, "HAS_PMCID")


class Cites(StructuredNode):
    uid = UniqueIdProperty()
    title = StringProperty(required=True, unique_index=True)
    url = StringProperty()
    doi = StringProperty()
    pmid = StringProperty()
    year = IntegerProperty()

    # existing
    authors = RelationshipTo(Author, "CONTRIBUTED_BY")
    cited_by_paper = RelationshipFrom("Paper", "CITES")
    resolves_to = RelationshipTo("Paper", "RESOLVES_TO")

    # NEW: normalized ID nodes
    doi_node = RelationshipTo(DOI, "HAS_DOI")
    pmid_node = RelationshipTo(PMID, "HAS_PMID")
    pmcid_node = RelationshipTo(PMCID, "HAS_PMCID")
    year_node = RelationshipTo(Year, "FROM_YEAR")


class Paper(StructuredNode):
    uid = UniqueIdProperty()
    title = StringProperty(unique_index=True, required=True)
    abstract = StringProperty()
    year = IntegerProperty()  # changed from DateProperty — year is an int
    url = StringProperty()
    pmcid = StringProperty()

    # ── existing ──────────────────────────────────────────────────────────────
    authors = RelationshipTo(Author, "AUTHORED_BY", model=AuthoredRel)
    images = RelationshipTo(Visuals, "HAS_IMAGE")
    cites = RelationshipTo(Cites, "CITES", model=CitesRel)

    # ── NEW: paper-to-paper ───────────────────────────────────────────────────
    # When a cited paper also exists as a Paper node — bypasses Cites intermediary
    directly_cites = RelationshipTo("Paper", "DIRECTLY_CITES")
    # Computed from embedding similarity — no citation needed
    similar_to = RelationshipTo("Paper", "SIMILAR_TO", model=SimilarRel)

    # ── NEW: domain context ───────────────────────────────────────────────────
    published_in = RelationshipTo(Journal, "PUBLISHED_IN")
    studies_organism = RelationshipTo(Organism, "STUDIES_ORGANISM", model=StudiesRel)
    mentions_gene = RelationshipTo(Gene, "MENTIONS_GENE")
    conducted_in = RelationshipTo(SpaceEnvironment, "CONDUCTED_IN")
    investigates_process = RelationshipTo(BiologicalProcess, "INVESTIGATES_PROCESS")

    # ── NEW: normalized nodes ─────────────────────────────────────────────────
    year_node = RelationshipTo(Year, "PUBLISHED_IN_YEAR")
    distribution = RelationshipTo(Distribution, "HAS_DISTRIBUTION")
    uploaded_by = RelationshipTo(User, "UPLOADED_BY")

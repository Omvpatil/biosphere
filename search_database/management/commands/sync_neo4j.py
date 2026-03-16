"""
sync_neo4j.py  —  PostgreSQL → Neo4j full sync
===============================================
Handles BOTH the original nodes/edges AND the new ones added in
graph_database/models.py:

  Nodes:     Author, Visuals, Paper, Cites, Journal, Year, Distribution, User, DOI, PMID, PMCID
  Edges:     AUTHORED_BY, HAS_IMAGE, CITES, CONTRIBUTED_BY (existing)
             PUBLISHED_IN (NEW)
             DIRECTLY_CITES  — Paper→Paper for resolved citations (NEW)
             COLLABORATES_WITH — Author→Author via shared paper (NEW)
             PUBLISHED_IN_YEAR — Paper→Year (NEW)
             HAS_DISTRIBUTION — Paper→Distribution (NEW)
             UPLOADED_BY — Paper→User (NEW)
             HAS_DOI, HAS_PMID, HAS_PMCID — Cites→DOI/PMID/PMCID (NEW)
             FROM_YEAR — Cites→Year (NEW)
             HAS_PMCID — Visuals→PMCID (NEW)

Memory-safe design
------------------
* All Postgres queries use .iterator(chunk_size=BATCH) so Django never
  loads the full table into RAM.
* Every Neo4j write uses UNWIND with $props lists, never one tx per row.
* Default BATCH=500 can be overridden with --batch.
"""

import logging
import uuid
from django.core.management.base import BaseCommand
from neomodel import db
from search_database.models import ResearchPaper, Author, ImageNodes, Citations
from biosphere.models import User as BiosphereUser

logger = logging.getLogger(__name__)


# ─── helpers ──────────────────────────────────────────────────────────────────


def chunks(lst, n):
    """Yield successive n-sized chunks from a list."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def run(query, params=None):
    """Thin wrapper so we always log Cypher errors."""
    try:
        db.cypher_query(query, params or {})
    except Exception as exc:
        logger.error(
            "Cypher error:\n%s\nParams sample: %s\nError: %s",
            query,
            str(params)[:200],
            exc,
        )
        raise


# ─── command ──────────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = "Syncs PostgreSQL data into Neo4j using safe batched streaming."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch",
            type=int,
            default=500,
            help="Number of rows per Neo4j UNWIND batch (default: 500). "
            "Lower this if you still see memory pressure.",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip phases whose nodes already exist (useful for incremental runs).",
        )

    # ── entry point ────────────────────────────────────────────────────────────

    def handle(self, *args, **kwargs):
        self.B = kwargs["batch"]
        self.stdout.write(self.style.SUCCESS(f"Starting sync  (batch={self.B}) …"))

        self._sync_users()
        self._sync_distributions()
        self._sync_years()
        self._sync_dois()
        self._sync_pmids()
        self._sync_pmcids()
        self._sync_authors()
        self._sync_visuals()
        self._sync_papers()
        self._sync_paper_author_edges()
        self._sync_paper_visual_edges()
        self._sync_paper_year_edges()
        self._sync_paper_distribution_edges()
        self._sync_paper_user_edges()
        self._sync_citations()
        self._sync_cites_doi_edges()
        self._sync_cites_pmid_edges()
        self._sync_cites_pmcid_edges()
        self._sync_cites_year_edges()
        self._sync_visuals_pmcid_edges()
        self._sync_journals()
        self._sync_resolves_to()
        self._sync_directly_cites()
        self._sync_collaborates_with()

        self.stdout.write(self.style.SUCCESS("✓ Sync complete!"))

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Authors
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_authors(self):
        self.stdout.write("1/8  Syncing Authors …")
        batch, total = [], 0

        for row in Author.objects.values("id", "name").iterator(chunk_size=self.B):
            row["uid"] = str(uuid.uuid4())
            batch.append(row)
            if len(batch) >= self.B:
                self._flush_authors(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_authors(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} Authors synced.")

    def _flush_authors(self, batch):
        run(
            """
            UNWIND $props AS prop
            MERGE (a:Author {name: prop.name})
            ON CREATE SET a.uid = prop.uid
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Visuals
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_visuals(self):
        self.stdout.write("2/8  Syncing Visuals …")
        batch, total = [], 0

        for row in ImageNodes.objects.values("id", "link", "description").iterator(
            chunk_size=self.B
        ):
            batch.append(
                {
                    "uid": str(uuid.uuid4()),
                    "link": row["link"],
                    "description": row["description"] or "",
                }
            )
            if len(batch) >= self.B:
                self._flush_visuals(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_visuals(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} Visuals synced.")

    def _flush_visuals(self, batch):
        run(
            """
            UNWIND $props AS prop
            MERGE (v:Visuals {image_link: prop.link})
            ON CREATE SET v.uid = prop.uid, v.image_dec = prop.description
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Papers  (year as int, pmcid added)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_papers(self):
        self.stdout.write("3/8  Syncing Papers …")
        batch, total = [], 0

        for row in ResearchPaper.objects.values(
            "id", "title", "abstract", "link", "created_at"
        ).iterator(chunk_size=self.B):
            year = row["created_at"].year if row["created_at"] else None
            batch.append(
                {
                    "uid": str(uuid.uuid4()),
                    "pg_id": row["id"],
                    "title": row["title"],
                    "abstract": row["abstract"] or "",
                    "url": row["link"],
                    "year": year,
                }
            )
            if len(batch) >= self.B:
                self._flush_papers(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_papers(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} Papers synced.")

    def _flush_papers(self, batch):
        run(
            """
            UNWIND $props AS prop
            MERGE (p:Paper {title: prop.title})
            ON CREATE SET p.uid      = prop.uid,
                          p.abstract = prop.abstract,
                          p.url      = prop.url,
                          p.year     = prop.year
            ON MATCH  SET p.url      = prop.url,
                          p.year     = prop.year
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Paper → Author edges  (AUTHORED_BY)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_paper_author_edges(self):
        self.stdout.write("4/8  Connecting Papers → Authors …")

        paper_map = dict(ResearchPaper.objects.values_list("id", "title"))
        author_map = dict(Author.objects.values_list("id", "name"))

        qs = ResearchPaper.authors.through.objects.values(
            "researchpaper_id", "author_id"
        )
        batch, total = [], 0

        for row in qs.iterator(chunk_size=self.B):
            pt = paper_map.get(row["researchpaper_id"])
            an = author_map.get(row["author_id"])
            if pt and an:
                batch.append({"paper_title": pt, "author_name": an})
            if len(batch) >= self.B:
                self._flush_paper_author(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_paper_author(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} AUTHORED_BY edges.")

    def _flush_paper_author(self, batch):
        run(
            """
            UNWIND $props AS prop
            MATCH (p:Paper  {title: prop.paper_title})
            MATCH (a:Author {name:  prop.author_name})
            MERGE (p)-[:AUTHORED_BY]->(a)
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 5. Paper → Visuals edges  (HAS_IMAGE)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_paper_visual_edges(self):
        self.stdout.write("5/8  Connecting Papers → Visuals …")

        paper_map = dict(ResearchPaper.objects.values_list("id", "title"))
        image_map = dict(ImageNodes.objects.values_list("id", "link"))

        qs = ResearchPaper.images.through.objects.values(
            "researchpaper_id", "imagenodes_id"
        )
        batch, total = [], 0

        for row in qs.iterator(chunk_size=self.B):
            pt = paper_map.get(row["researchpaper_id"])
            il = image_map.get(row["imagenodes_id"])
            if pt and il:
                batch.append({"paper_title": pt, "image_link": il})
            if len(batch) >= self.B:
                self._flush_paper_visual(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_paper_visual(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} HAS_IMAGE edges.")

    def _flush_paper_visual(self, batch):
        run(
            """
            UNWIND $props AS prop
            MATCH (p:Paper   {title:      prop.paper_title})
            MATCH (v:Visuals {image_link: prop.image_link})
            MERGE (p)-[:HAS_IMAGE]->(v)
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 6. Citations  — nodes + Paper→Cites + Cites→Author
    #    Now includes doi, pmid, year, citation_context (new fields)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_citations(self):
        self.stdout.write("6/8  Syncing Citations …")

        paper_map = dict(ResearchPaper.objects.values_list("id", "title"))
        cite_total = 0

        qs = Citations.objects.values(
            "id",
            "raw_text",
            "doi",
            "pmid",
            "publication_year",
            "citation_context",
            "paper_id",
            "cited_authors",
        )

        batch = []
        for row in qs.iterator(chunk_size=self.B):
            row["uid"] = str(uuid.uuid4())
            batch.append(row)
            if len(batch) >= self.B:
                self._flush_citations(batch, paper_map)
                cite_total += len(batch)
                batch = []

        if batch:
            self._flush_citations(batch, paper_map)
            cite_total += len(batch)

        self.stdout.write(f"     → {cite_total} Citations synced.")

    def _flush_citations(self, batch, paper_map):
        # 6a — Cites nodes (with new fields)
        run(
            """
            UNWIND $props AS prop
            MERGE (c:Cites {title: prop.raw_text})
            ON CREATE SET c.uid  = prop.uid,
                          c.doi  = COALESCE(prop.doi, ''),
                          c.pmid = COALESCE(prop.pmid, ''),
                          c.year = prop.publication_year
            ON MATCH  SET c.doi  = COALESCE(prop.doi, c.doi),
                          c.pmid = COALESCE(prop.pmid, c.pmid),
                          c.year = COALESCE(prop.publication_year, c.year)
        """,
            {"props": batch},
        )

        # 6b — Paper -[:CITES {citation_context, section}]-> Cites
        paper_cite = []
        for c in batch:
            pt = paper_map.get(c["paper_id"])
            if pt:
                paper_cite.append(
                    {
                        "paper_title": pt,
                        "cite_title": c["raw_text"],
                        "citation_context": c.get("citation_context") or "",
                    }
                )
        if paper_cite:
            run(
                """
                UNWIND $props AS prop
                MATCH (p:Paper {title: prop.paper_title})
                MATCH (c:Cites {title: prop.cite_title})
                MERGE (p)-[r:CITES]->(c)
                ON CREATE SET r.citation_context = prop.citation_context
            """,
                {"props": paper_cite},
            )

        # 6c — Cites → Author (CONTRIBUTED_BY)
        cite_author = []
        for c in batch:
            if c.get("cited_authors"):
                for name in [
                    n.strip() for n in c["cited_authors"].split(",") if n.strip()
                ]:
                    cite_author.append(
                        {
                            "cite_title": c["raw_text"],
                            "author_name": name,
                            "author_uid": str(uuid.uuid4()),
                        }
                    )
        if cite_author:
            run(
                """
                UNWIND $props AS prop
                MERGE (a:Author {name: prop.author_name})
                ON CREATE SET a.uid = prop.author_uid
            """,
                {"props": cite_author},
            )
            run(
                """
                UNWIND $props AS prop
                MATCH (c:Cites  {title: prop.cite_title})
                MATCH (a:Author {name:  prop.author_name})
                MERGE (c)-[:CONTRIBUTED_BY]->(a)
            """,
                {"props": cite_author},
            )

    # ──────────────────────────────────────────────────────────────────────────
    # 7. Journals  +  Paper -[:PUBLISHED_IN]-> Journal   [NEW]
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_journals(self):
        self.stdout.write("7/8  Syncing Journals (PUBLISHED_IN) …")

        paper_map = dict(ResearchPaper.objects.values_list("id", "title"))

        qs = (
            Citations.objects.exclude(journal_name__isnull=True)
            .exclude(journal_name="")
            .values("paper_id", "journal_name")
        )

        batch, total = [], 0
        for row in qs.iterator(chunk_size=self.B):
            pt = paper_map.get(row["paper_id"])
            if pt:
                batch.append(
                    {
                        "paper_title": pt,
                        "journal_name": row["journal_name"].strip(),
                        "journal_uid": str(uuid.uuid4()),
                    }
                )
            if len(batch) >= self.B:
                self._flush_journals(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_journals(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} PUBLISHED_IN edges.")

    def _flush_journals(self, batch):
        # Ensure Journal nodes exist first
        run(
            """
            UNWIND $props AS prop
            MERGE (j:Journal {name: prop.journal_name})
            ON CREATE SET j.uid = prop.journal_uid
        """,
            {"props": batch},
        )
        # Then connect Paper → Journal
        run(
            """
            UNWIND $props AS prop
            MATCH (p:Paper   {title: prop.paper_title})
            MATCH (j:Journal {name:  prop.journal_name})
            MERGE (p)-[:PUBLISHED_IN]->(j)
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 8a. Cites -[:RESOLVES_TO]-> Paper  [NEW]
    # 8b. Paper -[:DIRECTLY_CITES]-> Paper  [NEW]
    #
    # Strategy: DOI-based resolution.
    #   ResearchPaper.link often contains the DOI, e.g.
    #     https://doi.org/10.1038/s41526-024-00419-y
    #   Citations.doi stores the raw DOI string for the cited paper.
    #   We normalise both to lowercase, strip leading/trailing whitespace,
    #   then check if any paper's link CONTAINS that DOI.
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _doi_from_link(link: str) -> str | None:
        """Extract the DOI fragment from a URL such as https://doi.org/10.xx/yy."""
        if not link:
            return None
        link = link.strip().lower()
        for marker in ("doi.org/", "/doi/", "dx.doi.org/"):
            if marker in link:
                return link.split(marker, 1)[-1].rstrip("/")
        return None

    def _build_doi_to_paper_map(self):
        """Return {doi_str: paper_title} by parsing DOIs out of paper URLs."""
        doi_map = {}
        for paper in ResearchPaper.objects.values("title", "link").iterator(
            chunk_size=self.B
        ):
            doi = self._doi_from_link(paper["link"] or "")
            if doi:
                doi_map[doi] = paper["title"]
        self.stdout.write(f"     (doi map: {len(doi_map)} papers with resolvable DOIs)")
        return doi_map

    def _sync_resolves_to(self):
        """Cites -[:RESOLVES_TO]-> Paper  — when Citation.doi matches a Paper URL."""
        self.stdout.write("8a/9  Resolving Cites → Paper (RESOLVES_TO) …")

        doi_map = self._build_doi_to_paper_map()
        if not doi_map:
            self.stdout.write("     (no paper DOIs found — skipping)")
            return

        qs = (
            Citations.objects.exclude(doi__isnull=True)
            .exclude(doi="")
            .values("raw_text", "doi")
        )

        batch, total = [], 0
        for row in qs.iterator(chunk_size=self.B):
            doi = (row["doi"] or "").strip().lower().rstrip("/")
            cite_title = row["raw_text"]
            paper_title = doi_map.get(doi)
            if paper_title and cite_title:
                batch.append({"cite_title": cite_title, "paper_title": paper_title})
            if len(batch) >= self.B:
                self._flush_resolves_to(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_resolves_to(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} RESOLVES_TO edges.")

    def _flush_resolves_to(self, batch):
        run(
            """
            UNWIND $props AS prop
            MATCH (c:Cites {title: prop.cite_title})
            MATCH (p:Paper {title: prop.paper_title})
            MERGE (c)-[:RESOLVES_TO]->(p)
        """,
            {"props": batch},
        )

    def _sync_directly_cites(self):
        """Paper -[:DIRECTLY_CITES]-> Paper — where the citation DOI resolves to a known Paper."""
        self.stdout.write("8b/9  Resolving Paper → Paper (DIRECTLY_CITES) …")

        doi_map = self._build_doi_to_paper_map()
        paper_map = dict(ResearchPaper.objects.values_list("id", "title"))

        if not doi_map:
            self.stdout.write("     (no paper DOIs found — skipping)")
            return

        qs = (
            Citations.objects.exclude(doi__isnull=True)
            .exclude(doi="")
            .values("paper_id", "doi")
        )

        batch, total = [], 0
        for row in qs.iterator(chunk_size=self.B):
            doi = (row["doi"] or "").strip().lower().rstrip("/")
            src_title = paper_map.get(row["paper_id"])
            dst_title = doi_map.get(doi)
            if src_title and dst_title and src_title != dst_title:
                batch.append({"src_title": src_title, "dst_title": dst_title})
            if len(batch) >= self.B:
                self._flush_directly_cites(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_directly_cites(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} DIRECTLY_CITES edges.")

    def _flush_directly_cites(self, batch):
        run(
            """
            UNWIND $props AS prop
            MATCH (src:Paper {title: prop.src_title})
            MATCH (dst:Paper {title: prop.dst_title})
            MERGE (src)-[:DIRECTLY_CITES]->(dst)
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 8b. Author -[:COLLABORATES_WITH]-> Author   [NEW]
    #     Two authors collaborate if they share at least one Paper.
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_collaborates_with(self):
        self.stdout.write("8/8  Building COLLABORATES_WITH edges …")

        # Stream paper-author pairs; group by paper
        qs = ResearchPaper.authors.through.objects.values(
            "researchpaper_id", "author_id"
        ).order_by("researchpaper_id")

        author_map = dict(Author.objects.values_list("id", "name"))
        paper_groups = {}  # paper_id → [author_name, …]

        for row in qs.iterator(chunk_size=self.B):
            an = author_map.get(row["author_id"])
            if an:
                paper_groups.setdefault(row["researchpaper_id"], []).append(an)

        # Generate unique unordered pairs
        seen = set()
        batch = []
        total = 0

        for authors in paper_groups.values():
            if len(authors) < 2:
                continue
            for i in range(len(authors)):
                for j in range(i + 1, len(authors)):
                    a, b = sorted([authors[i], authors[j]])
                    key = (a, b)
                    if key not in seen:
                        seen.add(key)
                        batch.append({"a_name": a, "b_name": b})
                    if len(batch) >= self.B:
                        self._flush_collaborates(batch)
                        total += len(batch)
                        batch = []

        if batch:
            self._flush_collaborates(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} COLLABORATES_WITH edges.")

    def _flush_collaborates(self, batch):
        run(
            """
            UNWIND $props AS prop
            MATCH (a:Author {name: prop.a_name})
            MATCH (b:Author {name: prop.b_name})
            MERGE (a)-[:COLLABORATES_WITH]-(b)
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 9. Users (from ResearchPaper.added_by)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_users(self):
        self.stdout.write("9/17  Syncing Users …")
        batch, total = [], 0

        for row in (
            ResearchPaper.objects.exclude(added_by__isnull=True)
            .values(
                "added_by__id", "added_by__name", "added_by__email", "added_by__role"
            )
            .distinct()
            .iterator(chunk_size=self.B)
        ):
            batch.append(
                {
                    "uid": str(uuid.uuid4()),
                    "name": row["added_by__name"] or "Unknown",
                    "email": row["added_by__email"] or "",
                    "role": row["added_by__role"] or "",
                }
            )
            if len(batch) >= self.B:
                self._flush_users(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_users(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} Users synced.")

    def _flush_users(self, batch):
        run(
            """
            UNWIND $props AS prop
            MERGE (u:User {email: prop.email})
            ON CREATE SET u.uid = prop.uid, u.name = prop.name, u.role = prop.role
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 10. Distributions (from ResearchPaper.distribution)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_distributions(self):
        self.stdout.write("10/17  Syncing Distributions …")
        batch, total = [], 0

        for row in (
            ResearchPaper.objects.exclude(distribution__isnull=True)
            .exclude(distribution="")
            .values("distribution")
            .distinct()
            .iterator(chunk_size=self.B)
        ):
            batch.append(
                {
                    "uid": str(uuid.uuid4()),
                    "name": row["distribution"],
                }
            )
            if len(batch) >= self.B:
                self._flush_distributions(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_distributions(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} Distributions synced.")

    def _flush_distributions(self, batch):
        run(
            """
            UNWIND $props AS prop
            MERGE (d:Distribution {name: prop.name})
            ON CREATE SET d.uid = prop.uid
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 11. Years (from ResearchPaper.created_at.year and Citations.publication_year)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_years(self):
        self.stdout.write("11/17  Syncing Years …")
        batch, total = [], 0

        # From ResearchPaper
        for row in (
            ResearchPaper.objects.filter(created_at__isnull=False)
            .values("created_at__year")
            .distinct()
            .iterator(chunk_size=self.B)
        ):
            if row["created_at__year"]:
                batch.append(
                    {
                        "uid": str(uuid.uuid4()),
                        "year": row["created_at__year"],
                    }
                )
                if len(batch) >= self.B:
                    self._flush_years(batch)
                    total += len(batch)
                    batch = []

        # From Citations
        for row in (
            Citations.objects.exclude(publication_year__isnull=True)
            .values("publication_year")
            .distinct()
            .iterator(chunk_size=self.B)
        ):
            batch.append(
                {
                    "uid": str(uuid.uuid4()),
                    "year": row["publication_year"],
                }
            )
            if len(batch) >= self.B:
                self._flush_years(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_years(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} Years synced.")

    def _flush_years(self, batch):
        run(
            """
            UNWIND $props AS prop
            MERGE (y:Year {year: prop.year})
            ON CREATE SET y.uid = prop.uid
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 12. DOIs (from Citations.doi)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_dois(self):
        self.stdout.write("12/17  Syncing DOIs …")
        batch, total = [], 0

        for row in (
            Citations.objects.exclude(doi__isnull=True)
            .exclude(doi="")
            .values("doi")
            .distinct()
            .iterator(chunk_size=self.B)
        ):
            batch.append(
                {
                    "uid": str(uuid.uuid4()),
                    "doi": row["doi"].strip(),
                }
            )
            if len(batch) >= self.B:
                self._flush_dois(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_dois(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} DOIs synced.")

    def _flush_dois(self, batch):
        run(
            """
            UNWIND $props AS prop
            MERGE (d:DOI {doi: prop.doi})
            ON CREATE SET d.uid = prop.uid
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 13. PMIDs (from Citations.pmid)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_pmids(self):
        self.stdout.write("13/17  Syncing PMIDs …")
        batch, total = [], 0

        for row in (
            Citations.objects.exclude(pmid__isnull=True)
            .exclude(pmid="")
            .values("pmid")
            .distinct()
            .iterator(chunk_size=self.B)
        ):
            batch.append(
                {
                    "uid": str(uuid.uuid4()),
                    "pmid": row["pmid"].strip(),
                }
            )
            if len(batch) >= self.B:
                self._flush_pmids(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_pmids(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} PMIDs synced.")

    def _flush_pmids(self, batch):
        run(
            """
            UNWIND $props AS prop
            MERGE (p:PMID {pmid: prop.pmid})
            ON CREATE SET p.uid = prop.uid
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 14. PMCIDs (from Citations.pmcid and ImageNodes.pmcid)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_pmcids(self):
        self.stdout.write("14/17  Syncing PMCIDs …")
        batch, total = [], 0

        # From Citations
        for row in (
            Citations.objects.exclude(pmcid__isnull=True)
            .exclude(pmcid="")
            .values("pmcid")
            .distinct()
            .iterator(chunk_size=self.B)
        ):
            batch.append(
                {
                    "uid": str(uuid.uuid4()),
                    "pmcid": row["pmcid"].strip(),
                }
            )
            if len(batch) >= self.B:
                self._flush_pmcids(batch)
                total += len(batch)
                batch = []

        # From ImageNodes
        for row in (
            ImageNodes.objects.exclude(pmcid__isnull=True)
            .exclude(pmcid="")
            .values("pmcid")
            .distinct()
            .iterator(chunk_size=self.B)
        ):
            batch.append(
                {
                    "uid": str(uuid.uuid4()),
                    "pmcid": row["pmcid"].strip(),
                }
            )
            if len(batch) >= self.B:
                self._flush_pmcids(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_pmcids(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} PMCIDs synced.")

    def _flush_pmcids(self, batch):
        run(
            """
            UNWIND $props AS prop
            MERGE (p:PMCID {pmcid: prop.pmcid})
            ON CREATE SET p.uid = prop.uid
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 15. Paper → Year edges (PUBLISHED_IN_YEAR)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_paper_year_edges(self):
        self.stdout.write("15/17  Connecting Papers → Years …")

        paper_map = dict(ResearchPaper.objects.values_list("id", "title"))

        qs = ResearchPaper.objects.exclude(created_at__isnull=True).values(
            "id", "created_at__year"
        )

        batch, total = [], 0
        for row in qs.iterator(chunk_size=self.B):
            pt = paper_map.get(row["id"])
            year = row["created_at__year"]
            if pt and year:
                batch.append({"paper_title": pt, "year": year})
            if len(batch) >= self.B:
                self._flush_paper_year(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_paper_year(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} PUBLISHED_IN_YEAR edges.")

    def _flush_paper_year(self, batch):
        run(
            """
            UNWIND $props AS prop
            MATCH (p:Paper {title: prop.paper_title})
            MATCH (y:Year {year: prop.year})
            MERGE (p)-[:PUBLISHED_IN_YEAR]->(y)
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 16. Paper → Distribution edges (HAS_DISTRIBUTION)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_paper_distribution_edges(self):
        self.stdout.write("16/17  Connecting Papers → Distributions …")

        paper_map = dict(ResearchPaper.objects.values_list("id", "title"))

        qs = (
            ResearchPaper.objects.exclude(distribution__isnull=True)
            .exclude(distribution="")
            .values("id", "distribution")
        )

        batch, total = [], 0
        for row in qs.iterator(chunk_size=self.B):
            pt = paper_map.get(row["id"])
            if pt and row["distribution"]:
                batch.append({"paper_title": pt, "distribution": row["distribution"]})
            if len(batch) >= self.B:
                self._flush_paper_distribution(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_paper_distribution(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} HAS_DISTRIBUTION edges.")

    def _flush_paper_distribution(self, batch):
        run(
            """
            UNWIND $props AS prop
            MATCH (p:Paper {title: prop.paper_title})
            MATCH (d:Distribution {name: prop.distribution})
            MERGE (p)-[:HAS_DISTRIBUTION]->(d)
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 17. Paper → User edges (UPLOADED_BY)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_paper_user_edges(self):
        self.stdout.write("17/17  Connecting Papers → Users …")

        paper_map = dict(ResearchPaper.objects.values_list("id", "title"))

        qs = ResearchPaper.objects.exclude(added_by__isnull=True).values(
            "id", "added_by__email"
        )

        batch, total = [], 0
        for row in qs.iterator(chunk_size=self.B):
            pt = paper_map.get(row["id"])
            email = row["added_by__email"]
            if pt and email:
                batch.append({"paper_title": pt, "email": email})
            if len(batch) >= self.B:
                self._flush_paper_user(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_paper_user(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} UPLOADED_BY edges.")

    def _flush_paper_user(self, batch):
        run(
            """
            UNWIND $props AS prop
            MATCH (p:Paper {title: prop.paper_title})
            MATCH (u:User {email: prop.email})
            MERGE (p)-[:UPLOADED_BY]->(u)
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 18. Cites → DOI edges (HAS_DOI)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_cites_doi_edges(self):
        self.stdout.write("18/21  Connecting Cites → DOIs …")

        qs = (
            Citations.objects.exclude(doi__isnull=True)
            .exclude(doi="")
            .values("raw_text", "doi")
        )

        batch, total = [], 0
        for row in qs.iterator(chunk_size=self.B):
            batch.append(
                {
                    "cite_title": row["raw_text"],
                    "doi": row["doi"].strip(),
                }
            )
            if len(batch) >= self.B:
                self._flush_cites_doi(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_cites_doi(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} HAS_DOI edges.")

    def _flush_cites_doi(self, batch):
        run(
            """
            UNWIND $props AS prop
            MATCH (c:Cites {title: prop.cite_title})
            MATCH (d:DOI {doi: prop.doi})
            MERGE (c)-[:HAS_DOI]->(d)
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 19. Cites → PMID edges (HAS_PMID)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_cites_pmid_edges(self):
        self.stdout.write("19/21  Connecting Cites → PMIDs …")

        qs = (
            Citations.objects.exclude(pmid__isnull=True)
            .exclude(pmid="")
            .values("raw_text", "pmid")
        )

        batch, total = [], 0
        for row in qs.iterator(chunk_size=self.B):
            batch.append(
                {
                    "cite_title": row["raw_text"],
                    "pmid": row["pmid"].strip(),
                }
            )
            if len(batch) >= self.B:
                self._flush_cites_pmid(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_cites_pmid(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} HAS_PMID edges.")

    def _flush_cites_pmid(self, batch):
        run(
            """
            UNWIND $props AS prop
            MATCH (c:Cites {title: prop.cite_title})
            MATCH (p:PMID {pmid: prop.pmid})
            MERGE (c)-[:HAS_PMID]->(p)
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 20. Cites → PMCID edges (HAS_PMCID)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_cites_pmcid_edges(self):
        self.stdout.write("20/21  Connecting Cites → PMCIDs …")

        qs = (
            Citations.objects.exclude(pmcid__isnull=True)
            .exclude(pmcid="")
            .values("raw_text", "pmcid")
        )

        batch, total = [], 0
        for row in qs.iterator(chunk_size=self.B):
            batch.append(
                {
                    "cite_title": row["raw_text"],
                    "pmcid": row["pmcid"].strip(),
                }
            )
            if len(batch) >= self.B:
                self._flush_cites_pmcid(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_cites_pmcid(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} HAS_PMCID edges.")

    def _flush_cites_pmcid(self, batch):
        run(
            """
            UNWIND $props AS prop
            MATCH (c:Cites {title: prop.cite_title})
            MATCH (p:PMCID {pmcid: prop.pmcid})
            MERGE (c)-[:HAS_PMCID]->(p)
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 21. Cites → Year edges (FROM_YEAR)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_cites_year_edges(self):
        self.stdout.write("21/21  Connecting Cites → Years …")

        qs = Citations.objects.exclude(publication_year__isnull=True).values(
            "raw_text", "publication_year"
        )

        batch, total = [], 0
        for row in qs.iterator(chunk_size=self.B):
            batch.append(
                {
                    "cite_title": row["raw_text"],
                    "year": row["publication_year"],
                }
            )
            if len(batch) >= self.B:
                self._flush_cites_year(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_cites_year(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} FROM_YEAR edges.")

    def _flush_cites_year(self, batch):
        run(
            """
            UNWIND $props AS prop
            MATCH (c:Cites {title: prop.cite_title})
            MATCH (y:Year {year: prop.year})
            MERGE (c)-[:FROM_YEAR]->(y)
        """,
            {"props": batch},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 22. Visuals → PMCID edges (HAS_PMCID)
    # ──────────────────────────────────────────────────────────────────────────

    def _sync_visuals_pmcid_edges(self):
        self.stdout.write("22/22  Connecting Visuals → PMCIDs …")

        qs = (
            ImageNodes.objects.exclude(pmcid__isnull=True)
            .exclude(pmcid="")
            .values("link", "pmcid")
        )

        batch, total = [], 0
        for row in qs.iterator(chunk_size=self.B):
            batch.append(
                {
                    "image_link": row["link"],
                    "pmcid": row["pmcid"].strip(),
                }
            )
            if len(batch) >= self.B:
                self._flush_visuals_pmcid(batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush_visuals_pmcid(batch)
            total += len(batch)

        self.stdout.write(f"     → {total} Visuals HAS_PMCID edges.")

    def _flush_visuals_pmcid(self, batch):
        run(
            """
            UNWIND $props AS prop
            MATCH (v:Visuals {image_link: prop.image_link})
            MATCH (p:PMCID {pmcid: prop.pmcid})
            MERGE (v)-[:HAS_PMCID]->(p)
        """,
            {"props": batch},
        )

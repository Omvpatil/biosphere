from django.core.management.base import BaseCommand
from django.contrib.postgres.search import SearchVector
from search_database.models import DocumentChunks


class Command(BaseCommand):
    help = "Backfill search_vector field on DocumentChunks for BM25 search"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of chunks to update per batch (default: 500)",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]

        total = DocumentChunks.objects.filter(search_vector__isnull=True).count()
        self.stdout.write(f"Found {total} chunks without search_vector. Starting backfill...")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to backfill. All chunks already have search_vector."))
            return

        updated = 0
        offset = 0

        while True:
            batch_ids = list(
                DocumentChunks.objects.filter(search_vector__isnull=True)
                .values_list("id", flat=True)[:batch_size]
            )

            if not batch_ids:
                break

            # Weight A = section_title (highest relevance for BM25 scoring)
            # Weight B = text_content (body text)
            DocumentChunks.objects.filter(id__in=batch_ids).update(
                search_vector=(
                    SearchVector("section_title", weight="A", config="english")
                    + SearchVector("text_content", weight="B", config="english")
                )
            )

            updated += len(batch_ids)
            self.stdout.write(f"  Updated {updated}/{total} chunks...")

        self.stdout.write(self.style.SUCCESS(f"Done. Backfilled search_vector for {updated} DocumentChunks."))

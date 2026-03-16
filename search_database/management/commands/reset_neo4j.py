from django.core.management.base import BaseCommand
from neomodel import db


class Command(BaseCommand):
    help = "Wipes all nodes and relationships from Neo4j — run before a full re-sync."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Required flag to confirm you want to delete ALL Neo4j data.",
        )

    def handle(self, *args, **kwargs):
        if not kwargs["confirm"]:
            self.stderr.write(
                self.style.ERROR(
                    "Aborted. Pass --confirm to actually wipe the database.\n"
                    "Usage: python manage.py reset_neo4j --confirm"
                )
            )
            return

        self.stdout.write(self.style.WARNING("Wiping ALL Neo4j nodes and relationships..."))

        # Delete in batches to avoid OOM on large graphs
        batch_size = 10_000
        deleted = 0
        while True:
            result, _ = db.cypher_query(
                f"MATCH (n) WITH n LIMIT {batch_size} DETACH DELETE n RETURN count(n) AS cnt"
            )
            cnt = result[0][0] if result else 0
            deleted += cnt
            self.stdout.write(f"  Deleted {deleted} nodes so far...")
            if cnt == 0:
                break

        self.stdout.write(self.style.SUCCESS(f"Done. Deleted {deleted} nodes total."))

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django_pg_jsonschema.fields import JSONSchemaField


class Nodes:
    image_node = {
        "node_id": 1234,
        "node_type": "image",
        "data": {"image_link": "https://image.jpg", "image_dec": "another one desc"},
        "from_node": 12345,
        "to_node": 6789,
    }
    show_source_node = {
        "node_id": 1234,
        "node_type": "show_source",
        "data": {
            "link": "https://source-link.com",
        },
        "from_node": 12345,
        "to_node": 6789,
    }
    regular_node = {
        "node_id": 12345,
        "node_type": ["ask_ai", "image", "show_source", "show_paper"],
        "data": {
            "title": "...",
            "query": "...",
            "link": "optional",
            "description": "...",
            "images": [
                {
                    "image_link": "...",
                    "image_dec": "...",
                },
                {
                    "image_link": "...",
                    "image_dec": "...",
                },
            ],
            "cites": [
                {
                    "title": "...",
                    "link": "...",
                    "authors": ["..."],
                },
                {
                    "title": "...",
                    "link": "...",
                    "authors": ["..."],
                },
            ],
        },
        "ranking": {
            "importance": ["high", "medium", "low"],
            "is_imp_topic": ["true", "false"],
        },
        "source": "regular_node['node_id']",
        "target": [image_node["node_id"], show_source_node["node_id"]],
    }


class Roles(models.TextChoices):
    STUDENT = "Student"
    RESEARCHER = "Researcher"
    EXPLORER = "Explorer"


class User(models.Model):
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    role = models.CharField(choices=Roles.choices, default=Roles.EXPLORER)
    graphs = ArrayField(JSONSchemaField(schema=Nodes.regular_node), blank=True)

    def __str__(self):
        return {self.name, self.id}

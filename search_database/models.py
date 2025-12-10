from django.db import models
from django_pg_jsonschema.fields import JSONSchemaField


class AbstractInfo(models.Model):
    data_format = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "authors": {"type": "array", "items": {"type": "string"}},
            "link": {"type": "string", "format": "uri"},
            "description": {"type": "string"},
            "images": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "image_link": {"type": "string", "format": "uri"},
                        "image_desc": {"type": "string"},
                    },
                    "required": ["image_link", "image_desc"],
                },
            },
            "cites": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "link": {"type": "string", "format": "uri"},
                        "authors": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "link", "authors"],
                },
            },
        },
        "required": ["title", "authors", "link", "description"],
    }

    sample_data = {
        "title": "title of research paper",
        "link": "https://link-of-researchpaper.com",
        "authers": ["john doe", "vladimir putin", "heatler"],
        "description": "A huge descritption of that research paper",
        "images": [
            {
                "image_link": "https://image.jpg",
                "image_dec": "description of that image",
            },
            {
                "image_link": "https://image2.jpg",
                "image_dec": "another one description",
            },
        ],
        "cites": [
            {
                "title": "referenvce research paper",
                "link": "https://another-link.com",
                "authors": ["john doe", "toby maguire"],
            },
            {
                "title": "referenvce research paper",
                "link": "https://another-link.com",
                "authors": ["john doe", "toby maguire"],
            },
            {
                "title": "referenvce research paper",
                "link": "https://another-link.com",
                "authors": ["john doe", "toby maguire"],
            },
        ],
    }
    # NOTE: abstracted info will be in json or jsonb format in postgres with vector embeddings
    data = JSONSchemaField(schema=data_format, check_schema_in_db=True)

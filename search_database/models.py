from django.db import models


class AbstractInfo(models.Model):
    # NOTE: abstracted info will be in json or jsonb format in postgres with vector embeddings
    data = models.JSONField()
    data_format = {
        "title": "title of research paper",
        "authers": ["john doe", "vladimir putin", "heatler"],
        "link": "https://link-of-researchpaper.com",
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

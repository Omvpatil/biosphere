from django.db import models
from django.contrib.postgres.fields import ArrayField


class Roles(models.TextChoices):
    STUDENT = "Student"
    RESEARCHER = "Researcher"
    EXPLORER = "Explorer"


class User(models.Model):
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    role = models.CharField(choices=Roles.choices, default=Roles.EXPLORER)
    searched_graphs = ArrayField(models.JSONField(), blank=True)

    def __str__(self):
        return {self.name, self.id}

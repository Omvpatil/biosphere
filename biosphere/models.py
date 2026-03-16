from django.conf import settings
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)


class ChatRole(models.TextChoices):
    USER = ("user", "User")
    ASSISTANT = ("assistant", "Assistant")


class Roles(models.TextChoices):
    STUDENT = "Student"
    RESEARCHER = "Researcher"
    EXPLORER = "Explorer"


class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None):
        if not email:
            raise ValueError("Users must have an email address")
        user = self.model(email=self.normalize_email(email), name=name)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None):
        user = self.create_user(email, name, password)
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=255, default="Biosphere User")
    email = models.EmailField(max_length=255, unique=True)
    role = models.CharField(choices=Roles.choices, default=Roles.EXPLORER)
    google_id = models.CharField(max_length=255, blank=True, null=True, unique=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}"


class UploadedPapers(models.Model):
    id = models.BigAutoField(primary_key=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="papers_uploaded_by",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255, null=True, blank=True)
    link = models.CharField(max_length=255, null=True, blank=True)
    paper_state = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.title} - {self.link}"


class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, default="New Conversation")
    created_at = models.DateTimeField(auto_now_add=True)


class ChatMessage(models.Model):
    session = models.ForeignKey(
        ChatSession, related_name="messages", on_delete=models.CASCADE
    )
    role = models.CharField(max_length=10, choices=ChatRole)

    content = models.TextField()

    meta_summary = models.CharField(max_length=500, blank=True)

    papers = models.ManyToManyField("search_database.ResearchPaper", blank=True)
    images = models.ManyToManyField("search_database.ImageNodes", blank=True)
    authors = models.ManyToManyField("search_database.Author", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)


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
    name = models.CharField(max_length=255, default="Name")
    email = models.EmailField(max_length=255, unique=True)
    role = models.CharField(choices=Roles.choices, default=Roles.EXPLORER)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}"


class Author(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, default="Name")

    def __str__(self):
        return f"{self.name}"

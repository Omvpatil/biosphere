from django.contrib import admin
from biosphere.models import UploadedPapers, User
from search_database.models import Author


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "role")


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("id", "name")


@admin.register(UploadedPapers)
class UploadedPapersAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "uploaded_by",
    )

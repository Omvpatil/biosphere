from django.contrib import admin
from biosphere.models import User, Author


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "role")


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("id", "name")

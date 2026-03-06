from django.contrib import admin
from .models import ResearchPaper, DocumentChunks, ImageNodes

admin.site.register(ResearchPaper)
admin.site.register(DocumentChunks)
admin.site.register(ImageNodes)

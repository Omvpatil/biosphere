from rest_framework import serializers
from .models import Citations, ImageNodes, ResearchPaper


class ImageNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageNodes
        fields = ("link", "description")


class CitationsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Citations
        fields = ("title", "authors", "link")


class ResearchPaperSerializer(serializers.ModelSerializer):
    image_links = ImageNodeSerializer(many=True, read_only=True)
    citations = CitationsSerializer(many=True, read_only=True)

    class Meta:
        model = ResearchPaper
        fields = (
            "id",
            "title",
            "authors",
            "abstract",
            "description",
            "image_links",
            "citations",
        )


class CsvDataSerializer(serializers.Serializer):
    file = serializers.FileField()

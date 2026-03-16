from rest_framework import serializers
from .models import Citations, DocumentChunks, ImageNodes, ResearchPaper


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


class UserQuerySerializer(serializers.Serializer):
    user_query = serializers.CharField()


class DocumentChunksSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentChunks
        # fields = "__all__"
        exclude = ("embedding",)


class ChunkSerializer(serializers.Serializer):
    section = serializers.CharField(allow_blank=True)
    text = serializers.CharField()


class ImageContextSerializer(serializers.Serializer):
    description = serializers.CharField(allow_blank=True)
    signed_url = serializers.CharField()
    original_url = serializers.URLField()


class PaperContextSerializer(serializers.Serializer):
    paper_id = serializers.IntegerField()
    title = serializers.CharField()
    abstract = serializers.CharField(allow_blank=True)
    images = ImageContextSerializer(many=True)
    relevant_chunks = ChunkSerializer(many=True)


class FinalOutputSerializer(serializers.Serializer):
    papers = PaperContextSerializer(many=True)
    graph_context = serializers.CharField(allow_blank=True)


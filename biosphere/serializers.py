from django.contrib.auth import get_user_model
from django.core import signing
from django.urls import reverse
from pydantic import fields
from rest_framework import serializers

from biosphere.models import ChatMessage, ChatRole, ChatSession
from search_database.models import Author, ImageNodes, ResearchPaper

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("name", "email", "role", "graph_data")

    name = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    role = serializers.CharField()


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("name", "email", "password", "role")
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            name=validated_data["name"],
            password=validated_data["password"]
        )
        user.role = validated_data.get("role", "Explorer")
        user.save()
        return user


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class GoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField()
    client_id = serializers.CharField()
    role = serializers.CharField(required=False)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6)


# INFO: Chat Serializers
# =======================
class ImageSerializer(serializers.ModelSerializer):
    secure_link = serializers.SerializerMethodField()

    class Meta:
        model = ImageNodes
        fields = ["id", "description", "pmcid", "secure_link"]

    def get_secure_link(self, obj):
        link = obj.get_secure_link()
        request = self.context.get("request")
        if link and link.startswith("/") and request:
            return request.build_absolute_uri(link)
        return link


class PaperSerializer(serializers.ModelSerializer):
    authors = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")
    images = ImageSerializer(many=True, read_only=True)
    relevant_chunks = serializers.SerializerMethodField()
    pmcid = serializers.SerializerMethodField()

    class Meta:
        model = ResearchPaper
        fields = ["id", "title", "link", "authors", "abstract", "images", "relevant_chunks", "pmcid"]

    def get_pmcid(self, obj):
        import re
        match = re.search(r"(PMC\d+)", obj.link or "")
        return match.group(1) if match else None

    def get_relevant_chunks(self, obj):
        # Return first few chunks as context for history viewing
        chunks = obj.chunks.all().order_by("chunk_index")[:3]
        return [{"section": c.section_title or "General", "text": c.text_content} for c in chunks]


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name"]


class ChatMessageSerializer(serializers.ModelSerializer):
    papers = PaperSerializer(many=True, read_only=True)
    images = ImageSerializer(many=True, read_only=True)
    authors = AuthorSerializer(many=True, read_only=True)

    paper_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    image_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    author_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "session",
            "role",
            "content",
            "meta_summary",
            "papers",
            "images",
            "authors",
            "paper_ids",
            "image_ids",
            "author_ids",
            "created_at",
        ]

    def create(self, validated_data):
        paper_ids = list(set(validated_data.pop("paper_ids", [])))
        image_ids = list(set(validated_data.pop("image_ids", [])))
        author_ids = list(set(validated_data.pop("author_ids", [])))

        message = ChatMessage.objects.create(**validated_data)

        if paper_ids:
            papers = ResearchPaper.objects.filter(id__in=paper_ids)
            if papers.count() != len(paper_ids):
                raise serializers.ValidationError(
                    {
                        "paper_ids": "Some paper IDs hallucinated by the LLM do not exist."
                    }
                )
            message.papers.set(papers)

        if image_ids:
            images = ImageNodes.objects.filter(id__in=image_ids)
            if images.count() != len(image_ids):
                raise serializers.ValidationError(
                    {
                        "image_ids": "Some image IDs hallucinated by the LLM do not exist."
                    }
                )
            message.images.set(images)

        if author_ids:
            authors = Author.objects.filter(id__in=author_ids)
            if authors.count() != len(author_ids):
                raise serializers.ValidationError(
                    {
                        "author_ids": "Some author IDs hallucinated by the LLM do not exist."
                    }
                )
            message.authors.set(authors)
        return message

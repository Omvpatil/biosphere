from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("name", "email", "role", "graph_data")

    name = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    role = serializers.CharField()

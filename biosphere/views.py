from django.shortcuts import render
from django.http import HttpResponse
from django.views import View
from rest_framework import generics

from neo4j_haystack import Neo4jDocumentStore, Neo4jEmbeddingRetriever, document_stores


class Search(View):
    def index(request):
        return HttpResponse("Hellow world this is Biosphere.!")

    def hybrid_search(query):
        document_store = Neo4jDocumentStore(
            url="bolt://localhost:7687",
            username="neo4j",
            password="passw0rd",
            database="neo4j",
            embedding_dim=318,
            index="document_embeddings",
        )
        pass

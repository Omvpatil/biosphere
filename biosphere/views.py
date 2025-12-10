from django.shortcuts import render
from django.http import HttpResponse
from django.views import View
from rest_framework import generics


class Search(View):
    def index(request):
        return HttpResponse("Hellow world this is Biosphere.!")

    def hybrid_search(query):
        pass

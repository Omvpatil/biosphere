from django.http import HttpResponse
from django.shortcuts import render


def greet(request):
    return HttpResponse("This is graph_database")

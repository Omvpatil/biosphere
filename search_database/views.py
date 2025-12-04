from django.http import HttpResponse
from django.shortcuts import render


def search(request):
    return HttpResponse("This is search_database")

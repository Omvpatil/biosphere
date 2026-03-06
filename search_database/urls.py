from django.urls import path
from . import views

urlpatterns = [
    path("papers", views.ResearchPaperListAPIView.as_view()),
    path("papers/<int:pk>", views.ResearchPaperDetailAPIView.as_view()),
    path("papers/upload_csv", views.upload_csv),
]

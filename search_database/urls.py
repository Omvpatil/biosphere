from django.urls import path
from . import views

urlpatterns = [
    path("papers", views.ResearchPaperListAPIView.as_view(), name="paper-list"),
    path(
        "papers/<int:pk>",
        views.ResearchPaperDetailAPIView.as_view(),
        name="paper-detail",
    ),
    path("papers/upload_csv", views.upload_csv, name="upload_csv"),
    path("test", views.test_functions, name="test_functions"),
    path("chat/stream", views.chat_search_stream_view, name="chat_search_stream"),
    path("chat/graph", views.generate_graph_view, name="generate_graph"),
    path("image/<str:token>", views.secure_image, name="secure_image"),
]

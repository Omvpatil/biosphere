from django.urls import path
from . import views

urlpatterns = [
    path("google/", views.GooglLoginAPIView.as_view(), name="google-login"),
    path("login/", views.LogInAPIView.as_view(), name="login"),
    path("register/", views.RegisterAPIView.as_view(), name="register"),
    path("google-register/", views.GoogleRegisterAPIView.as_view(), name="google-register"),
    path("logout/", views.LogOutAPIView.as_view(), name="logout"),
    path("sessions/", views.ChatSessionListAPIView.as_view(), name="chat-sessions"),
    path("history/<int:session_id>/", views.ChatSessionHistoryAPIView.as_view(), name="chat-history"),
]

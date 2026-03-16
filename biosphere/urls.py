from django.urls import path
from . import views

urlpatterns = [
    path("google/", views.GooglLoginAPIView.as_view(), name="google-login"),
    path("login/", views.LogInAPIView.as_view(), name="login"),
    path("logout/", views.LogOutAPIView.as_view(), name="logout"),
]

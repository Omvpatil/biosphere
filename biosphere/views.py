from math import log
from django.contrib.auth import authenticate, get_user_model
from rest_framework.exceptions import status
from rest_framework.views import APIView, Response
import logging
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from biosphere.exeptions import (
    EmailNotFoundError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from biosphere.models import ChatSession
from biosphere.serializers import (
    GoogleLoginSerializer,
    LoginSerializer,
    LogoutSerializer,
    ChatMessageSerializer,
    RegisterSerializer,
)

logger = logging.getLogger(__name__)

User = get_user_model()


class GooglLoginAPIView(APIView):
    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Invalid data format : {serializer.errors}")
            raise InvalidCredentialsError("Invalid data format")
        id_token_str = serializer.validated_data.get("id_token")
        client_id = serializer.validated_data.get("client_id")
        role = serializer.validated_data.get("role")

        if not id_token_str:
            logger.error(msg=f"missing credentials : {id_token_str} - {client_id}")
            return Response(
                {"Error": "Missing credentials"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            id_info = id_token.verify_oauth2_token(
                id_token_str, google_requests.Request(), audience=client_id
            )
            email = id_info.get("email")
            name = id_info.get("name")
            picture = id_info.get("picture")
            google_id = id_info.get("sub")

            if not id_info.get("email_verified"):
                logger.error("Google email not verified")
                raise InvalidCredentialsError("Google email not verified")

            if not email:
                logger.error("Email not found from the token")
                raise EmailNotFoundError()

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "name": name or email.split("@")[0],
                    "email": email,
                    "google_id": google_id,
                    "role": role or "Explorer",
                },
            )
            if not user.google_id:
                user.google_id = google_id
                user.save()
            
            # If role is provided during login, update it
            if role and user.role != role:
                user.role = role
                user.save()

            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "email": user.email,
                    "name": user.name,
                    "picture": picture,
                    "role": user.role,
                    "is_new": created,
                }
            )
        except ValueError as e:
            logger.error(f"Invalid Token : {e}")
            raise InvalidTokenError()


class ChatSessionListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = ChatSession.objects.filter(user=request.user).order_by("-created_at")
        # Simple list return
        data = [{"id": s.id, "title": s.title, "created_at": s.created_at} for s in sessions]
        return Response(data, status=status.HTTP_200_OK)


class ChatSessionHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id, user=request.user)
            messages = session.messages.order_by("created_at")
            serializer = ChatMessageSerializer(messages, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ChatSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)


class LogInAPIView(APIView):
    def post(self, request):
        serializer = LoginSerializer(request.data)
        if serializer.is_valid():
            user = authenticate(
                request,
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
            )
            if user and user.is_email_verified():
                refresh = RefreshToken.for_user(user)
                return Response(
                    {"access": str(refresh.access_token), "refresh": str(refresh)},
                    status=status.HTTP_200_OK,
                )
            raise InvalidCredentialsError()
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogOutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(request.data)
        if serializer.is_valid():
            try:
                refresh_token = serializer.validated_data["refresh"]
                token = RefreshToken(refresh_token)
                token.blacklist()
                return Response({"msg": "Logged out"}, status=status.HTTP_200_OK)
            except Exception:
                logger.error("Got invalid token while logging out")
                raise InvalidTokenError()
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterAPIView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "email": user.email,
                    "name": user.name,
                    "role": user.role,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GoogleRegisterAPIView(APIView):
    def post(self, request):
        id_token_str = request.data.get("id_token")
        client_id = request.data.get("client_id")
        password = request.data.get("password")
        role = request.data.get("role", "Explorer")

        if not id_token_str or not password:
            return Response(
                {"error": "Missing credentials or password"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            id_info = id_token.verify_oauth2_token(
                id_token_str, google_requests.Request(), audience=client_id
            )
            email = id_info.get("email")
            name = id_info.get("name")
            google_id = id_info.get("sub")

            if User.objects.filter(email=email).exists():
                return Response(
                    {"error": "User with this email already exists. Please login."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = User.objects.create_user(email=email, name=name, password=password)
            user.google_id = google_id
            user.role = role
            user.save()

            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "email": user.email,
                    "name": user.name,
                    "role": user.role,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            logger.error(f"Google registration error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

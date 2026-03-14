from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout
import logging

from .serializers import (
    UserRegistrationSerializer,
    LoginSerializer,
    UserSerializer
)
from home.serializers import StudentSerializer

logger = logging.getLogger(__name__)


class RegisterAPIView(APIView):
    """Register a new user"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)

        login(request, user)

        logger.info(f"New user registered: {user.username}")

        return Response({
            "message": f"Welcome {user.username}! Account created successfully.",
            "token": token.key,
            "user": UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class LoginAPIView(APIView):
    """User login"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)

        login(request, user)

        logger.info(f"User logged in: {user.username}")

        return Response({
            "message": f"Welcome back {user.username}",
            "token": token.key,
            "user": UserSerializer(user).data
        }, status=status.HTTP_200_OK)


class LogoutAPIView(APIView):
    """User logout"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        username = request.user.username

        try:
            token = Token.objects.filter(user=request.user)
            if token.exists():
                token.delete()
        except Exception as e:
            logger.error(f"Logout token deletion error: {str(e)}")

        logout(request)

        logger.info(f"User logged out: {username}")

        return Response({
            "message": f"Goodbye {username}, you are logged out."
        }, status=status.HTTP_200_OK)


class UserProfileAPIView(APIView):
    """Get and update user profile"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_serializer = UserSerializer(request.user)
        data = user_serializer.data

        student_profile = None
        try:
            if hasattr(request.user, "student"):
                student_profile = StudentSerializer(request.user.student).data
        except Exception as e:
            logger.error(f"Student profile error: {str(e)}")

        data["student_profile"] = student_profile
        return Response(data)


    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()

        return Response({
            "message": "Profile updated successfully",
            "user": serializer.data
        })


    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()

        return Response({
            "message": "Profile updated successfully",
            "user": serializer.data
        })

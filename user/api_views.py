from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout
from .serializers import (
    UserRegistrationSerializer, LoginSerializer,
    UserSerializer
)
from home.serializers import StudentSerializer
import logging

logger = logging.getLogger(__name__)


class RegisterAPIView(APIView):
    """API view for user registration"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Register a new user"""
        serializer = UserRegistrationSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            # Create auth token
            token, created = Token.objects.get_or_create(user=user)
            
            # Auto-login the user
            login(request, user)
            
            return Response(
                {
                    'message': f'Welcome, {user.username}! Your account has been created successfully.',
                    'token': token.key,
                    'user': UserSerializer(user).data
                },
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginAPIView(APIView):
    """API view for user login"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Login user and return token"""
        serializer = LoginSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Get or create auth token
            token, created = Token.objects.get_or_create(user=user)
            
            # Login the user
            login(request, user)
            
            return Response(
                {
                    'message': f'Welcome back, {user.username}!',
                    'token': token.key,
                    'user': UserSerializer(user).data
                },
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutAPIView(APIView):
    """API view for user logout"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Logout user and delete token"""
        try:
            # Delete the user's token
            request.user.auth_token.delete()
        except:
            pass
        
        # Logout the user
        username = request.user.username
        logout(request)
        
        return Response(
            {'message': f'Goodbye, {username}! You have been logged out successfully.'},
            status=status.HTTP_200_OK
        )


class UserProfileAPIView(APIView):
    """API view for user profile"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current user's profile"""
        serializer = UserSerializer(request.user)
        
        # Include student profile if exists
        data = serializer.data
        try:
            if hasattr(request.user, 'student'):
                student_serializer = StudentSerializer(request.user.student)
                data['student_profile'] = student_serializer.data
            else:
                data['student_profile'] = None
        except Exception as e:
            logger.error(f"Error fetching student profile for user {request.user.id}: {str(e)}")
            data['student_profile'] = None
        
        return Response(data)
    
    def put(self, request):
        """Update current user's profile"""
        serializer = UserSerializer(request.user, data=request.data, partial=False)
        
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'message': 'Profile updated successfully.',
                    'user': serializer.data
                },
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request):
        """Partially update current user's profile"""
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'message': 'Profile updated successfully.',
                    'user': serializer.data
                },
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

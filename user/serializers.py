from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from home.models import Student


class UserSerializer(serializers.ModelSerializer):
    """Basic User serializer"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, min_length=6, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, min_length=6, style={'input_type': 'password'}, label='Confirm Password')
    
    # Student profile fields
    classroom = serializers.CharField(max_length=10, required=False, default='N/A')
    branch = serializers.CharField(max_length=10, required=False, default='N/A')
    roll_no = serializers.CharField(max_length=3, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=10, required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2', 'first_name', 'last_name',
                  'classroom', 'branch', 'roll_no', 'phone']
    
    def validate(self, data):
        """Validate passwords match"""
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password2': 'Passwords do not match.'})
        return data
    
    def validate_username(self, value):
        """Check if username already exists"""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists.')
        return value
    
    def validate_email(self, value):
        """Check if email already exists"""
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email address already in use.')
        return value
    
    def create(self, validated_data):
        """Create user and student profile"""
        # Remove password2 and student fields
        validated_data.pop('password2')
        classroom = validated_data.pop('classroom', 'N/A')
        branch = validated_data.pop('branch', 'N/A')
        roll_no = validated_data.pop('roll_no', '')
        phone = validated_data.pop('phone', '')
        
        # Create user
        user = User.objects.create_user(**validated_data)
        
        # Create student profile
        Student.objects.create(
            user=user,
            classroom=classroom,
            branch=branch,
            roll_no=roll_no,
            phone=phone
        )
        
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    
    def validate(self, data):
        """Validate credentials"""
        username = data.get('username')
        password = data.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError('Invalid username or password.')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled.')
            data['user'] = user
        else:
            raise serializers.ValidationError('Must include username and password.')
        
        return data


class TokenSerializer(serializers.ModelSerializer):
    """Serializer for authentication token with user details"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Token
        fields = ['key', 'user']

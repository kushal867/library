from django.urls import path
from . import api_views

urlpatterns = [
    path('auth/register/', api_views.RegisterAPIView.as_view(), name='api-register'),
    path('auth/login/', api_views.LoginAPIView.as_view(), name='api-login'),
    path('auth/logout/', api_views.LogoutAPIView.as_view(), name='api-logout'),
    path('auth/profile/', api_views.UserProfileAPIView.as_view(), name='api-profile'),
]

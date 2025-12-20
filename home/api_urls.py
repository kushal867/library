from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

# Create router and register viewsets
router = DefaultRouter()
router.register(r'categories', api_views.CategoryViewSet, basename='category')
router.register(r'books', api_views.BookViewSet, basename='book')
router.register(r'students', api_views.StudentViewSet, basename='student')
router.register(r'issued-books', api_views.IssuedBookViewSet, basename='issued-book')

urlpatterns = [
    path('', include(router.urls)),
]

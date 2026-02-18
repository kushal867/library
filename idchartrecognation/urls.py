from django.urls import path
from . import views, api_views

app_name = 'idchartrecognation'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('enroll/', views.enroll_face, name='enroll_face'),
    path('recognize/', views.recognize_face, name='recognize_face'),
    path('manage/', views.manage_enrollments, name='manage_enrollments'),
    path('deactivate/<int:encoding_id>/', views.deactivate_encoding, name='deactivate_encoding'),
    path('activate/<int:encoding_id>/', views.activate_encoding, name='activate_encoding'),
    path('system-status/', views.system_status, name='system_status'),
    
    # API endpoints
    path('api/recognize/', api_views.FaceRecognizeAPIView.as_view(), name='api_recognize'),
    path('api/history/', api_views.RecognitionHistoryAPIView.as_view(), name='api_history'),
]

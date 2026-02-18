from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
import base64
from django.core.files.base import ContentFile
from .views import process_recognition_image
from .serializers import RecognitionLogSerializer
from .models import RecognitionLog

class FaceRecognizeAPIView(APIView):
    """API view for recognizing a face from an image"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Recognize face from uploaded image
        Accepts: 
        - image: File
        - OR image_data: Base64 string
        """
        image_file = request.FILES.get('image')
        image_data = request.data.get('image_data')

        if not image_file and not image_data:
            return Response(
                {'error': 'No image provided. Use "image" field for file or "image_data" for base64.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if image_data and not image_file:
            try:
                if ';base64,' in image_data:
                    format, imgstr = image_data.split(';base64,')
                else:
                    imgstr = image_data
                
                ext = "jpg" # Default
                image_file = ContentFile(base64.b64decode(imgstr), name=f"api_upload.{ext}")
            except Exception as e:
                return Response(
                    {'error': f'Invalid base64 image data: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Use the existing logic from views.py
        student, confidence, result = process_recognition_image(image_file, request)

        response_data = {
            'result': result,
            'confidence': confidence,
        }

        if student:
            from home.serializers import StudentSerializer
            response_data['student'] = StudentSerializer(student).data
            response_data['message'] = f"Recognized: {student.user.get_full_name() or student.user.username}"
        else:
            response_data['message'] = "Student not recognized"

        return Response(response_data, status=status.HTTP_200_OK if result == 'success' else status.HTTP_200_OK)

class RecognitionHistoryAPIView(APIView):
    """API view for recognition history"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logs = RecognitionLog.objects.all()[:20]
        serializer = RecognitionLogSerializer(logs, many=True)
        return Response(serializer.data)

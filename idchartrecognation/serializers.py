from rest_framework import serializers
from .models import IDCard, FaceEncoding, RecognitionLog
from home.serializers import StudentSerializer

class IDCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = IDCard
        fields = '__all__'

class FaceEncodingSerializer(serializers.ModelSerializer):
    student_details = StudentSerializer(source='student', read_only=True)
    
    class Meta:
        model = FaceEncoding
        fields = ['id', 'student', 'student_details', 'confidence_score', 'enrolled_at', 'updated_at', 'is_active']
        read_only_fields = ['enrolled_at', 'updated_at']

class RecognitionLogSerializer(serializers.ModelSerializer):
    student_details = StudentSerializer(source='matched_student', read_only=True)
    
    class Meta:
        model = RecognitionLog
        fields = ['id', 'result', 'matched_student', 'student_details', 'confidence', 'timestamp', 'details']
        read_only_fields = ['timestamp']

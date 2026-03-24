from rest_framework import serializers
from .models import IDCard, FaceEncoding, RecognitionLog
from home.serializers import StudentSerializer


class IDCardSerializer(serializers.ModelSerializer):
    """Serializer for ID Card uploads"""

    student_details = StudentSerializer(source='student', read_only=True)

    class Meta:
        model = IDCard
        fields = [
            'id',
            'student',
            'student_details',
            'image',
            'uploaded_at',
            'is_active'
        ]
        read_only_fields = ['uploaded_at']

    def validate_image(self, value):
        # Extra API-level validation (optional)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image must be under 5MB.")
        return value


class FaceEncodingSerializer(serializers.ModelSerializer):
    """Serializer for stored face encodings"""

    student_details = StudentSerializer(source='student', read_only=True)

    class Meta:
        model = FaceEncoding
        fields = [
            'id',
            'student',
            'student_details',
            'confidence_score',
            'enrolled_at',
            'updated_at',
            'is_active'
        ]
        read_only_fields = ['enrolled_at', 'updated_at']

    def validate_confidence_score(self, value):
        if value < 0 or value > 1:
            raise serializers.ValidationError("Confidence score must be between 0 and 1.")
        return value

    def validate(self, data):
        """Prevent duplicate active encodings"""
        student = data.get('student')

        if student:
            existing = FaceEncoding.objects.filter(
                student=student,
                is_active=True
            ).exclude(id=self.instance.id if self.instance else None)

            if existing.exists():
                raise serializers.ValidationError(
                    "This student already has an active face encoding."
                )

        return data


class RecognitionLogSerializer(serializers.ModelSerializer):
    """Serializer for recognition attempts/logs"""

    student_details = StudentSerializer(source='matched_student', read_only=True)

    class Meta:
        model = RecognitionLog
        fields = [
            'id',
            'result',
            'matched_student',
            'student_details',
            'confidence',
            'timestamp',
            'details'
        ]
        read_only_fields = ['timestamp']

    def validate_confidence(self, value):
        if value is not None and (value < 0 or value > 1):
            raise serializers.ValidationError("Confidence must be between 0 and 1.")
        return value

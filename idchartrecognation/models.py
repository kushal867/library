from django.db import models
from django.core.exceptions import ValidationError
from home.models import Student
import numpy as np
import logging

logger = logging.getLogger(__name__)


class IDCard(models.Model):
    """Stores uploaded ID card images for face enrollment"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='id_cards')
    image = models.ImageField(upload_to='id_cards/', help_text='Upload student ID card with clear face photo')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, help_text='Error details if processing failed')
    
    def __str__(self):
        return f"ID Card - {self.student.user.username} ({self.status})"
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "ID Card"
        verbose_name_plural = "ID Cards"


class FaceEncoding(models.Model):
    """Stores face recognition encodings (128-D vectors) for students"""
    
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='face_encoding')
    # Store face encoding as binary data (128-D numpy array)
    encoding_data = models.BinaryField(help_text='128-dimensional face encoding vector')
    confidence_score = models.FloatField(
        help_text='Quality score of the face encoding (0-1)',
        default=0.0
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(
        default=True,
        help_text='Active encodings are used for recognition'
    )
    id_card = models.ForeignKey(
        IDCard,
        on_delete=models.SET_NULL,
        null=True, 
        blank=True,
        related_name='face_encodings',
        help_text='Source ID card for this encoding'
    )
    
    def __str__(self):
        return f"Face Encoding - {self.student.user.username}"
    
    def save_encoding(self, encoding_array):
        """
        Save a numpy array as binary data
        
        Args:
            encoding_array: numpy array of shape (128,)
        """
        if not isinstance(encoding_array, np.ndarray):
            encoding_array = np.array(encoding_array)
        
        if encoding_array.shape != (128,):
            raise ValidationError(f"Invalid encoding shape: {encoding_array.shape}. Expected (128,)")
        
        self.encoding_data = encoding_array.tobytes()
    
    def get_encoding(self):
        """
        Retrieve the face encoding as a numpy array
        
        Returns:
            numpy array of shape (128,)
        """
        if not self.encoding_data:
            return None
        
        # Try to read as float32 first (standard format)
        encoding = np.frombuffer(self.encoding_data, dtype=np.float32)
        
        # Check if it's the correct size for float32
        if encoding.shape[0] == 128:
            return encoding
            
        # If the size is 256, it might be an old float64 encoding
        if encoding.shape[0] == 256:
            encoding_64 = np.frombuffer(self.encoding_data, dtype=np.float64)
            if encoding_64.shape[0] == 128:
                return encoding_64.astype(np.float32)
        
        logger.warning(f"Invalid encoding shape: {encoding.shape} for student {self.student.id}")
        return None

    def migrate_to_float32(self):
        """
        Migrate old float64 encoding storage to float32 to save space and ensure consistency.
        Should be called manually or during a background task.
        """
        if not self.encoding_data:
            return False
            
        encoding = np.frombuffer(self.encoding_data, dtype=np.float32)
        if encoding.shape[0] == 256:
            encoding_64 = np.frombuffer(self.encoding_data, dtype=np.float64)
            if encoding_64.shape[0] == 128:
                encoding_32 = encoding_64.astype(np.float32)
                self.encoding_data = encoding_32.tobytes()
                self.save(update_fields=['encoding_data'])
                return True
        return False
    
    def clean(self):
        """Validate that only one active encoding exists per student"""
        super().clean()
        
        if self.is_active:
            # Check if another active encoding exists for this student
            existing = FaceEncoding.objects.filter(
                student=self.student,
                is_active=True
            ).exclude(pk=self.pk)
            
            if existing.exists():
                raise ValidationError(
                    f'An active face encoding already exists for {self.student.user.username}. '
                    'Deactivate the existing encoding first.'
                )
    
    class Meta:
        ordering = ['-enrolled_at']
        verbose_name = "Face Encoding"
        verbose_name_plural = "Face Encodings"
        indexes = [
            models.Index(fields=['student', 'is_active']),
        ]


class RecognitionLog(models.Model):
    """Log all face recognition attempts for auditing and analytics"""
    
    RESULT_CHOICES = [
        ('success', 'Success'),
        ('no_match', 'No Match Found'),
        ('no_face', 'No Face Detected'),
        ('multiple_faces', 'Multiple Faces Detected'),
        ('poor_quality', 'Poor Quality Image'),
        ('error', 'Error'),
    ]
    
    image = models.ImageField(upload_to='recognition_logs/', null=True, blank=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    matched_student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recognition_logs'
    )
    confidence = models.FloatField(
        null=True,
        blank=True,
        help_text='Match confidence score (lower is better, < 0.6 is good match)'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, help_text='Additional details or error messages')
    
    def __str__(self):
        if self.matched_student:
            return f"Recognition: {self.matched_student.user.username} - {self.result} ({self.timestamp})"
        return f"Recognition: {self.result} ({self.timestamp})"
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Recognition Log"
        verbose_name_plural = "Recognition Logs"
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['matched_student', '-timestamp']),
        ]

from django import forms
from django.core.exceptions import ValidationError
from home.models import Student
from .models import IDCard


class IDCardUploadForm(forms.ModelForm):
    """Form for uploading ID card images to enroll student faces"""
    
    class Meta:
        model = IDCard
        fields = ['student', 'image']
        widgets = {
            'student': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'required': True
            })
        }
        help_texts = {
            'image': 'Upload ID card with clear, front-facing photo (JPG, PNG). Max 5MB.'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active students without face encodings
        self.fields['student'].queryset = Student.objects.filter(
            is_active=True
        ).select_related('user')
        self.fields['student'].label_from_instance = lambda obj: f"{obj.user.get_full_name() or obj.user.username} - {obj.roll_no}"
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        
        if image:
            # Check file size (5MB limit)
            if image.size > 5 * 1024 * 1024:
                raise ValidationError('Image file size must be under 5MB')
            
            # Check file type
            if not image.content_type in ['image/jpeg', 'image/jpg', 'image/png']:
                raise ValidationError('Only JPG and PNG images are allowed')
        
        return image
    
    def clean_student(self):
        student = self.cleaned_data.get('student')
        
        if student:
            # Check if student already has an active face encoding
            if hasattr(student, 'face_encoding') and student.face_encoding.is_active:
                raise ValidationError(
                    f'{student.user.username} already has an active face encoding. '
                    'Deactivate the existing encoding first to re-enroll.'
                )
        
        return student


class FaceRecognitionForm(forms.Form):
    """Form for uploading image for face recognition"""
    
    image = forms.ImageField(
        label='Upload Photo',
        help_text='Upload a clear photo of the person to recognize',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'required': True
        })
    )
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        
        if image:
            # Check file size (5MB limit)
            if image.size > 5 * 1024 * 1024:
                raise ValidationError('Image file size must be under 5MB')
            
            # Check file type
            if not image.content_type in ['image/jpeg', 'image/jpg', 'image/png']:
                raise ValidationError('Only JPG and PNG images are allowed')
        
        return image


class WebcamCaptureForm(forms.Form):
    """Form for capturing image from webcam (base64 data)"""
    
    image_data = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    
    def clean_image_data(self):
        data = self.cleaned_data.get('image_data')
        
        # Validate base64 data format
        if not data or not data.startswith('data:image'):
            raise ValidationError('Invalid image data')
        
        return data

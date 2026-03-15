from django import forms
from django.core.exceptions import ValidationError
from home.models import Student
from .models import IDCard
import imghdr


MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_IMAGE_TYPES = ['jpeg', 'png', 'jpg']


def validate_image_file(image):
    """Utility to validate uploaded images"""
    if not image:
        return
    if image.size > MAX_IMAGE_SIZE:
        raise ValidationError(f'Image size must be under {MAX_IMAGE_SIZE // (1024*1024)}MB.')
    
    # Use imghdr to validate image content type
    image_type = imghdr.what(image)
    if image_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError('Only JPG and PNG images are allowed.')


class IDCardUploadForm(forms.ModelForm):
    """Form for uploading ID card images to enroll student faces"""

    class Meta:
        model = IDCard
        fields = ['student', 'image']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control', 'required': True}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*', 'required': True}),
        }
        help_texts = {
            'image': 'Upload ID card with clear, front-facing photo (JPG, PNG). Max 5MB.'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show only active students
        self.fields['student'].queryset = Student.objects.filter(is_active=True).select_related('user')
        self.fields['student'].label_from_instance = lambda obj: f"{obj.user.get_full_name() or obj.user.username} - {obj.roll_no}"

    def clean_image(self):
        image = self.cleaned_data.get('image')
        validate_image_file(image)
        return image

    def clean_student(self):
        student = self.cleaned_data.get('student')
        if student and hasattr(student, 'face_encoding') and student.face_encoding.is_active:
            raise ValidationError(
                f'{student.user.get_full_name() or student.user.username} already has an active face encoding. '
                'Deactivate the existing encoding first to re-enroll.'
            )
        return student


class FaceRecognitionForm(forms.Form):
    """Form for uploading image for face recognition"""

    image = forms.ImageField(
        label='Upload Photo',
        help_text='Upload a clear photo of the person to recognize',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*', 'required': True})
    )

    def clean_image(self):
        image = self.cleaned_data.get('image')
        validate_image_file(image)
        return image


class WebcamCaptureForm(forms.Form):
    """Form for capturing image from webcam (base64 data)"""

    image_data = forms.CharField(widget=forms.HiddenInput(), required=True)

    def clean_image_data(self):
        data = self.cleaned_data.get('image_data')
        if not data or not data.startswith('data:image'):
            raise ValidationError('Invalid image data. Ensure it is base64-encoded image data.')
        return data

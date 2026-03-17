from django import forms
from django.core.exceptions import ValidationError
from home.models import Student
from .models import IDCard
from PIL import Image
import base64
import imghdr

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_FORMATS = ['JPEG', 'PNG']


class ImageValidator:
    """Reusable image validator"""

    @staticmethod
    def validate(image):
        if not image:
            raise ValidationError("No image uploaded.")

        # File size check
        if image.size > MAX_IMAGE_SIZE:
            raise ValidationError("Image must be under 5MB.")

        # Validate image content using Pillow
        try:
            img = Image.open(image)
            img.verify()  # Check corruption
        except Exception:
            raise ValidationError("Invalid or corrupted image file.")

        # Re-open after verify (Pillow requirement)
        image.seek(0)
        img = Image.open(image)

        if img.format not in ALLOWED_FORMATS:
            raise ValidationError("Only JPG and PNG formats are allowed.")


class IDCardUploadForm(forms.ModelForm):
    """Upload ID card image for face enrollment"""

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
                'accept': 'image/jpeg,image/png',
                'required': True
            }),
        }
        help_texts = {
            'image': 'Upload a clear ID card image (JPG/PNG, max 5MB).'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['student'].queryset = (
            Student.objects
            .filter(is_active=True)
            .select_related('user')
        )

        self.fields['student'].label_from_instance = (
            lambda obj: f"{obj.user.get_full_name() or obj.user.username} ({obj.roll_no})"
        )

    def clean_image(self):
        image = self.cleaned_data.get('image')
        ImageValidator.validate(image)
        return image

    def clean_student(self):
        student = self.cleaned_data.get('student')

        if not student:
            raise ValidationError("Student is required.")

        if hasattr(student, 'face_encoding') and getattr(student.face_encoding, 'is_active', False):
            raise ValidationError(
                f"{student} already has an active face encoding. Disable it before re-enrolling."
            )

        return student


class FaceRecognitionForm(forms.Form):
    """Upload image for face recognition"""

    image = forms.ImageField(
        label='Upload Photo',
        help_text='Upload a clear face image',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/png',
            'required': True
        })
    )

    def clean_image(self):
        image = self.cleaned_data.get('image')
        ImageValidator.validate(image)
        return image


class WebcamCaptureForm(forms.Form):
    """Handle base64 webcam image"""

    image_data = forms.CharField(widget=forms.HiddenInput(), required=True)

    def clean_image_data(self):
        data = self.cleaned_data.get('image_data')

        if not data or not data.startswith('data:image'):
            raise ValidationError("Invalid image data format.")

        try:
            header, encoded = data.split(',', 1)
            decoded = base64.b64decode(encoded)

            # Validate size
            if len(decoded) > MAX_IMAGE_SIZE:
                raise ValidationError("Captured image exceeds 5MB.")

            # Validate type
            file_type = imghdr.what(None, decoded)
            if file_type not in ['jpeg', 'png']:
                raise ValidationError("Only JPG and PNG images are allowed.")

        except Exception:
            raise ValidationError("Invalid base64 image data.")

        return data

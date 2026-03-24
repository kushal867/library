from django import forms
from django.core.exceptions import ValidationError
from home.models import Student
from .models import IDCard

from PIL import Image
from io import BytesIO
import base64
import imghdr

# Constants
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_TYPES = ['jpeg', 'png']
MAX_WIDTH = 2000
MAX_HEIGHT = 2000


class ImageValidator:
    """Reusable and secure image validator"""

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
            img.load()  # fully load image
        except Exception:
            raise ValidationError("Invalid or corrupted image file.")

        # Reset pointer after reading
        image.seek(0)

        # Validate file type using imghdr (more reliable than img.format)
        file_type = imghdr.what(image)
        if file_type not in ALLOWED_TYPES:
            raise ValidationError("Only JPG and PNG formats are allowed.")

        # Validate dimensions
        if img.width > MAX_WIDTH or img.height > MAX_HEIGHT:
            raise ValidationError("Image resolution too high (max 2000x2000).")

        # Normalize (useful for face recognition)
        img = img.convert('RGB')


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

        face_encoding = getattr(student, 'face_encoding', None)

        if face_encoding and getattr(face_encoding, 'is_active', False):
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

    image_data = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )

    def clean_image_data(self):
        data = self.cleaned_data.get('image_data')

        if not data or not data.startswith('data:image'):
            raise ValidationError("Invalid image data format.")

        try:
            header, encoded = data.split(',', 1)
            decoded = base64.b64decode(encoded)

            # Size validation
            if len(decoded) > MAX_IMAGE_SIZE:
                raise ValidationError("Captured image exceeds 5MB.")

            # Type validation
            file_type = imghdr.what(None, decoded)
            if file_type not in ALLOWED_TYPES:
                raise ValidationError("Only JPG and PNG images are allowed.")

            # Validate using Pillow
            try:
                img = Image.open(BytesIO(decoded))
                img.load()
            except Exception:
                raise ValidationError("Invalid image content.")

            # Dimension check
            if img.width > MAX_WIDTH or img.height > MAX_HEIGHT:
                raise ValidationError("Image resolution too high (max 2000x2000).")

        except Exception:
            raise ValidationError("Invalid base64 image data.")

        return data

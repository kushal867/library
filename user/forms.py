from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import re


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'placeholder': 'Username',
            'class': 'form-control'
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Password',
            'class': 'form-control'
        })
    )


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Password',
            'class': 'form-control'
        })
    )

    confirm_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm Password',
            'class': 'form-control'
        })
    )

    classroom = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g., 10-A',
            'class': 'form-control'
        })
    )

    branch = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g., Science',
            'class': 'form-control'
        })
    )

    roll_no = forms.CharField(
        max_length=5,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Roll Number',
            'class': 'form-control'
        })
    )

    phone = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': '98XXXXXXXX',
            'class': 'form-control'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={
                'placeholder': 'Username',
                'class': 'form-control'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'Email address',
                'class': 'form-control'
            }),
        }

    # -------------------------
    # FIELD VALIDATIONS
    # -------------------------

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise forms.ValidationError("Email is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email already registered.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')

        # Nepal phone number validation (starts with 98 or 97 and 10 digits)
        if not re.match(r'^(98|97)\d{8}$', phone):
            raise forms.ValidationError(
                "Enter valid 10-digit Nepal mobile number (98XXXXXXXX or 97XXXXXXXX)."
            )
        return phone

    def clean_password(self):
        password = self.cleaned_data.get('password')

        if not password:
            raise forms.ValidationError("Password is required.")

        try:
            validate_password(password)
        except ValidationError as e:
            raise forms.ValidationError(e.messages)

        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")

        return cleaned_data

    # -------------------------
    # SAVE METHOD
    # -------------------------

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])  # Hash password

        if commit:
            user.save()

        return user

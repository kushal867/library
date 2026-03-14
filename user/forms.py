from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import re


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            "placeholder": "Username",
            "class": "form-control"
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "Password",
            "class": "form-control"
        })
    )


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "Password",
            "class": "form-control"
        })
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "Confirm Password",
            "class": "form-control"
        })
    )

    classroom = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. 10-A",
            "class": "form-control"
        })
    )

    branch = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            "placeholder": "Science / Management",
            "class": "form-control"
        })
    )

    roll_no = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            "placeholder": "Roll Number",
            "class": "form-control"
        })
    )

    phone = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            "placeholder": "98XXXXXXXX",
            "class": "form-control"
        })
    )

    class Meta:
        model = User
        fields = ["username", "email"]
        widgets = {
            "username": forms.TextInput(attrs={
                "placeholder": "Username",
                "class": "form-control"
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "Email",
                "class": "form-control"
            }),
        }

    # -------------------------
    # FIELD VALIDATION
    # -------------------------

    def clean_username(self):
        username = self.cleaned_data["username"]

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Username already exists.")

        return username


    def clean_email(self):
        email = self.cleaned_data["email"]

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email already registered.")

        return email


    def clean_phone(self):
        phone = self.cleaned_data["phone"]

        if not re.fullmatch(r"(98|97)\d{8}", phone):
            raise forms.ValidationError(
                "Enter valid Nepal mobile number (98XXXXXXXX or 97XXXXXXXX)."
            )

        return phone


    def clean_password(self):
        password = self.cleaned_data.get("password")

        try:
            validate_password(password)
        except ValidationError as e:
            raise forms.ValidationError(e.messages)

        return password


    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password:
            if password != confirm_password:
                self.add_error("confirm_password", "Passwords do not match.")

        return cleaned_data


    # -------------------------
    # SAVE USER
    # -------------------------

    def save(self, commit=True):
        user = super().save(commit=False)

        user.set_password(self.cleaned_data["password"])

        if commit:
            user.save()

        return user

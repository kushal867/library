from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from home.models import Student
from .forms import LoginForm, RegisterForm


def user_login(request):
    """User login view with error handling"""
    if request.user.is_authenticated:
        return redirect('index')

    form = LoginForm()

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password']
            )
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('index')
            else:
                messages.error(request, "Invalid username or password. Please try again.")
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, 'login.html', {'form': form})


def user_register(request):
    """User registration view with validation"""
    if request.user.is_authenticated:
        return redirect('index')

    form = RegisterForm()

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            # Check if username already exists
            if User.objects.filter(username=form.cleaned_data['username']).exists():
                messages.error(request, "Username already exists. Please choose a different one.")
            else:
                try:
                    # Use transaction to ensure both user and student profile are created
                    with transaction.atomic():
                        user = form.save(commit=False)
                        user.set_password(form.cleaned_data['password'])
                        user.save()
                        
                        # Auto-create Student profile for the new user
                        Student.objects.create(
                            user=user,
                            classroom=form.cleaned_data.get('classroom', 'N/A'),
                            branch=form.cleaned_data.get('branch', 'N/A'),
                            roll_no=form.cleaned_data.get('roll_no', ''),
                            phone=form.cleaned_data.get('phone', ''),
                        )
                        
                        login(request, user)
                        messages.success(
                            request, 
                            f"Welcome, {user.username}! Your account and student profile have been created successfully."
                        )
                        return redirect('index')
                except Exception as e:
                    messages.error(request, f"Error creating account: {str(e)}")
        else:
            # Display form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)

    return render(request, 'register.html', {'form': form})


def user_logout(request):
    """User logout view"""
    username = request.user.username if request.user.is_authenticated else None
    logout(request)
    if username:
        messages.info(request, f"Goodbye, {username}! You have been logged out successfully.")
    return redirect('login')

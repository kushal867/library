from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta
import base64
import io
from PIL import Image

from home.models import Student
from .models import IDCard, FaceEncoding, RecognitionLog
from .forms import IDCardUploadForm, FaceRecognitionForm, WebcamCaptureForm
from .utils import (
    extract_face_from_image,
    calculate_face_quality,
    find_matching_student
)
import logging

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """Main dashboard for face recognition system"""
    
    # Statistics
    total_enrolled = FaceEncoding.objects.filter(is_active=True).count()
    total_students = Student.objects.filter(is_active=True).count()
    enrollment_percentage = (total_enrolled / total_students * 100) if total_students > 0 else 0
    
    # Recent enrollments
    recent_enrollments = FaceEncoding.objects.filter(
        is_active=True
    ).select_related('student__user').order_by('-enrolled_at')[:10]
    
    # Recognition stats (last 7 days)
    week_ago = timezone.now() - timedelta(days=7)
    recognition_stats = RecognitionLog.objects.filter(
        timestamp__gte=week_ago
    ).values('result').annotate(count=Count('result'))
    
    # Recent recognition attempts
    recent_recognitions = RecognitionLog.objects.select_related(
        'matched_student__user'
    ).order_by('-timestamp')[:10]
    
    context = {
        'total_enrolled': total_enrolled,
        'total_students': total_students,
        'enrollment_percentage': enrollment_percentage,
        'recent_enrollments': recent_enrollments,
        'recognition_stats': recognition_stats,
        'recent_recognitions': recent_recognitions,
    }
    
    return render(request, 'idchartrecognation/dashboard.html', context)


@login_required
def enroll_face(request):
    """Enroll a student's face from ID card image"""
    
    if request.method == 'POST':
        # Check if it's webcam capture or file upload
        if 'image_data' in request.POST and request.POST.get('image_data'):
            # Webcam capture
            webcam_form = WebcamCaptureForm(request.POST)
            
            if webcam_form.is_valid():
                # Get student ID from POST data
                student_id = request.POST.get('student')
                if not student_id:
                    messages.error(request, 'Please select a student first.')
                    return redirect('idchartrecognation:enroll_face')
                
                try:
                    student = Student.objects.get(id=student_id)
                except Student.DoesNotExist:
                    messages.error(request, 'Invalid student selected.')
                    return redirect('idchartrecognation:enroll_face')
                
                # Decode base64 image
                image_data = webcam_form.cleaned_data['image_data']
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                
                # Create image file
                image_file = ContentFile(
                    base64.b64decode(imgstr),
                    name=f'id_card_{student.user.username}_{timezone.now().timestamp()}.{ext}'
                )
                
                # Create ID card with webcam image
                id_card = IDCard(student=student, status='pending')
                id_card.image.save(image_file.name, image_file, save=True)
                
                # Process enrollment (same logic as file upload)
                process_enrollment(request, id_card)
                return redirect('idchartrecognation:dashboard' if id_card.status == 'processed' else 'idchartrecognation:enroll_face')
        else:
            # File upload
            form = IDCardUploadForm(request.POST, request.FILES)
            
            if form.is_valid():
                id_card = form.save(commit=False)
                id_card.status = 'pending'
                id_card.save()
                
                # Process enrollment
                process_enrollment(request, id_card)
                return redirect('idchartrecognation:dashboard' if id_card.status == 'processed' else 'idchartrecognation:enroll_face')
    else:
        form = IDCardUploadForm()
    
    webcam_form = WebcamCaptureForm()
    
    # Get enrolled students
    enrolled_students = FaceEncoding.objects.filter(
        is_active=True
    ).select_related('student__user').order_by('-enrolled_at')
    
    context = {
        'form': form,
        'webcam_form': webcam_form,
        'enrolled_students': enrolled_students,
    }
    
    return render(request, 'idchartrecognation/enroll.html', context)


def process_enrollment(request, id_card):
    """
    Process ID card for face enrollment
    
    Args:
        request: HTTP request object
        id_card: IDCard model instance
    """
    try:
        # Extract face from image
        result = extract_face_from_image(id_card.image.path)
        
        if not result['success']:
            id_card.status = 'failed'
            id_card.error_message = result['error']
            id_card.save()
            messages.error(request, f"Failed to process ID card: {result['error']}")
            return
        
        # Check face quality
        quality = calculate_face_quality(id_card.image.path, result['face_location'])
        
        if not quality['is_good_quality']:
            id_card.status = 'failed'
            id_card.error_message = 'Poor image quality. Please upload a clearer image.'
            id_card.save()
            
            # Build detailed error message
            issues = []
            brightness = quality.get('brightness', 0)
            sharpness = quality.get('sharpness', 0)
            face_size = quality.get('size', 0)
            
            if brightness <= 30 or brightness >= 230:
                issues.append(f"lighting issue (brightness: {brightness:.0f}, need 30-230)")
            if sharpness <= 50:
                issues.append(f"image too blurry (sharpness: {sharpness:.0f}, need >50)")
            if face_size > 0 and face_size <= 80:
                issues.append(f"face too small ({face_size}px, need >80px)")
            
            error_detail = ", ".join(issues) if issues else "multiple quality issues"
            
            messages.warning(
                request,
                f"Image quality check failed: {error_detail}. Please capture/upload a clearer, well-lit image with a larger face."
            )
            return
        
        # Create or update face encoding
        face_encoding, created = FaceEncoding.objects.get_or_create(
            student=id_card.student,
            defaults={'id_card': id_card}
        )
        
        # Save the encoding
        face_encoding.save_encoding(result['encoding'])
        face_encoding.confidence_score = quality.get('sharpness', 0) / 1000.0  # Normalize
        face_encoding.is_active = True
        face_encoding.id_card = id_card
        face_encoding.save()
        
        # Update ID card status
        id_card.status = 'processed'
        id_card.save()
        
        messages.success(
            request,
            f'Successfully enrolled {id_card.student.user.username}! '
            f'Face encoding created with quality score: {face_encoding.confidence_score:.2f}'
        )
        
    except Exception as e:
        logger.error(f"Error processing ID card: {str(e)}")
        id_card.status = 'failed'
        id_card.error_message = str(e)
        id_card.save()
        messages.error(request, f'Error processing ID card: {str(e)}')


@login_required
def recognize_face(request):
    """Recognize a student from uploaded photo"""
    
    recognized_student = None
    confidence = None
    recognition_result = None
    
    if request.method == 'POST':
        # Check if it's webcam capture or file upload
        if 'image_data' in request.POST:
            # Webcam capture
            webcam_form = WebcamCaptureForm(request.POST)
            
            if webcam_form.is_valid():
                # Decode base64 image
                image_data = webcam_form.cleaned_data['image_data']
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                
                # Create image file
                image_file = ContentFile(
                    base64.b64decode(imgstr),
                    name=f'webcam_capture_{timezone.now().timestamp()}.{ext}'
                )
                
                # Process the image
                recognized_student, confidence, recognition_result = process_recognition_image(
                    image_file,
                    request
                )
        else:
            # File upload
            form = FaceRecognitionForm(request.POST, request.FILES)
            
            if form.is_valid():
                image = form.cleaned_data['image']
                recognized_student, confidence, recognition_result = process_recognition_image(
                    image,
                    request
                )
    
    form = FaceRecognitionForm()
    webcam_form = WebcamCaptureForm()
    
    context = {
        'form': form,
        'webcam_form': webcam_form,
        'recognized_student': recognized_student,
        'confidence': confidence,
        'recognition_result': recognition_result,
    }
    
    return render(request, 'idchartrecognation/recognize.html', context)


def process_recognition_image(image_file, request):
    """
    Process uploaded image for face recognition
    
    Returns:
        tuple: (recognized_student, confidence, result_message)
    """
    recognized_student = None
    confidence = None
    result_message = None
    
    try:
        # Save to temporary file or use in-memory
        if hasattr(image_file, 'temporary_file_path'):
            image_path = image_file.temporary_file_path()
        else:
            # Convert to PIL Image for processing
            img = Image.open(image_file)
            
            # Save to temporary location
            import tempfile
            import os
            temp_dir = tempfile.mkdtemp()
            image_path = os.path.join(temp_dir, 'temp_recognition.jpg')
            img.save(image_path)
        
        # Extract face from image
        result = extract_face_from_image(image_path)
        
        if not result['success']:
            # Log failed recognition
            RecognitionLog.objects.create(
                result='no_face' if 'No face' in result['error'] else 'error',
                details=result['error']
            )
            messages.error(request, f"Recognition failed: {result['error']}")
            return None, None, result['error']
        
        if result['num_faces'] > 1:
            RecognitionLog.objects.create(
                result='multiple_faces',
                details=f"Detected {result['num_faces']} faces"
            )
            messages.warning(
                request,
                f"Multiple faces detected ({result['num_faces']}). Using the most prominent one."
            )
        
        # Find matching student
        active_encodings = FaceEncoding.objects.filter(is_active=True)
        match_result = find_matching_student(result['encoding'], active_encodings)
        
        if match_result['found']:
            recognized_student = match_result['student']
            confidence = match_result['confidence']
            
            # Log successful recognition
            RecognitionLog.objects.create(
                result='success',
                matched_student=recognized_student,
                confidence=confidence,
                details=f"Matched against {match_result['num_compared']} enrolled students"
            )
            
            messages.success(
                request,
                f'Student recognized: {recognized_student.user.get_full_name() or recognized_student.user.username} '
                f'(Confidence: {confidence:.3f})'
            )
            result_message = 'success'
        else:
            # Log no match
            RecognitionLog.objects.create(
                result='no_match',
                confidence=match_result['confidence'],
                details=f"No match found among {match_result['num_compared']} enrolled students"
            )
            
            messages.warning(
                request,
                f'No matching student found. Compared against {match_result["num_compared"]} enrolled students.'
            )
            result_message = 'no_match'
        
    except Exception as e:
        logger.error(f"Error during face recognition: {str(e)}")
        RecognitionLog.objects.create(
            result='error',
            details=str(e)
        )
        messages.error(request, f'Error during recognition: {str(e)}')
        result_message = 'error'
    
    return recognized_student, confidence, result_message


@login_required
def manage_enrollments(request):
    """Manage enrolled students - view, deactivate, re-enroll"""
    
    enrolled_students = FaceEncoding.objects.select_related(
        'student__user',
        'id_card'
    ).order_by('-enrolled_at')
    
    context = {
        'enrolled_students': enrolled_students,
    }
    
    return render(request, 'idchartrecognation/manage.html', context)


@login_required
def deactivate_encoding(request, encoding_id):
    """Deactivate a face encoding"""
    
    encoding = get_object_or_404(FaceEncoding, id=encoding_id)
    
    if request.method == 'POST':
        encoding.is_active = False
        encoding.save()
        messages.success(
            request,
            f'Face encoding for {encoding.student.user.username} has been deactivated.'
        )
        return redirect('idchartrecognation:manage_enrollments')
    
    return redirect('idchartrecognation:manage_enrollments')


@login_required
def activate_encoding(request, encoding_id):
    """Activate a face encoding"""
    
    encoding = get_object_or_404(FaceEncoding, id=encoding_id)
    
    if request.method == 'POST':
        # Check if student already has an active encoding
        existing = FaceEncoding.objects.filter(
            student=encoding.student,
            is_active=True
        ).exclude(id=encoding_id)
        
        if existing.exists():
            messages.error(
                request,
                f'{encoding.student.user.username} already has an active encoding.'
            )
        else:
            encoding.is_active = True
            encoding.save()
            messages.success(
                request,
                f'Face encoding for {encoding.student.user.username} has been activated.'
            )
        
        return redirect('idchartrecognation:manage_enrollments')
    
    return redirect('idchartrecognation:manage_enrollments')

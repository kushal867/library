"""
Utility functions for face recognition operations
"""
import face_recognition
import numpy as np
from PIL import Image
import cv2
import logging

logger = logging.getLogger(__name__)

# Recognition threshold - lower is more strict
# Increased to 0.65 for more lenient matching (reduces false negatives)
FACE_MATCH_THRESHOLD = 0.65


def extract_face_from_image(image_path, model='hog'):
    """
    Extract face location and encoding from an image
    
    Args:
        image_path: Path to image file or PIL Image object
        model: 'hog' (faster, CPU) or 'cnn' (more accurate, GPU)
    
    Returns:
        dict with keys:
            - success: bool
            - encoding: numpy array (128,) if successful
            - face_location: tuple (top, right, bottom, left)
            - error: str if failed
            - num_faces: int
    """
    try:
        # Load image
        if isinstance(image_path, str):
            image = face_recognition.load_image_file(image_path)
        else:
            # Convert PIL Image to numpy array
            image = np.array(image_path)
        
        # Find face locations
        face_locations = face_recognition.face_locations(image, model=model)
        
        if len(face_locations) == 0:
            return {
                'success': False,
                'error': 'No face detected in the image',
                'num_faces': 0
            }
        
        if len(face_locations) > 1:
            logger.warning(f"Multiple faces detected ({len(face_locations)}), using the largest one")
            # Use the largest face
            face_locations = [max(face_locations, key=lambda loc: (loc[2] - loc[0]) * (loc[1] - loc[3]))]
        
        # Generate face encoding
        face_encodings = face_recognition.face_encodings(image, face_locations)
        
        if len(face_encodings) == 0:
            return {
                'success': False,
                'error': 'Could not generate face encoding',
                'num_faces': len(face_locations)
            }
        
        return {
            'success': True,
            'encoding': face_encodings[0],
            'face_location': face_locations[0],
            'num_faces': len(face_locations)
        }
        
    except Exception as e:
        logger.error(f"Error extracting face: {str(e)}")
        return {
            'success': False,
            'error': f'Error processing image: {str(e)}',
            'num_faces': 0
        }


def calculate_face_quality(image_path, face_location=None):
    """
    Calculate quality metrics for a face image
    
    Args:
        image_path: Path to image file
        face_location: Optional tuple (top, right, bottom, left)
    
    Returns:
        dict with quality metrics:
            - brightness: 0-255
            - sharpness: float
            - size: int (face width in pixels)
            - is_good_quality: bool
    """
    try:
        # Load image
        img = cv2.imread(str(image_path))
        if img is None:
            return {'is_good_quality': False, 'error': 'Could not load image'}
        
        # Convert to grayscale for analysis
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Calculate brightness
        brightness = np.mean(gray)
        
        # Calculate sharpness using Laplacian variance
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Get face size if location provided
        face_size = 0
        if face_location:
            top, right, bottom, left = face_location
            face_size = right - left
        
        # Quality thresholds - relaxed for better acceptance
        is_good_quality = (
            brightness > 30 and brightness < 230 and  # Not too dark or bright (relaxed)
            laplacian_var > 50 and  # Sharp enough (relaxed from 100)
            (face_size == 0 or face_size > 80)  # Face large enough (relaxed from 100)
        )
        
        return {
            'brightness': float(brightness),
            'sharpness': float(laplacian_var),
            'size': int(face_size),
            'is_good_quality': is_good_quality
        }
        
    except Exception as e:
        logger.error(f"Error calculating face quality: {str(e)}")
        return {'is_good_quality': False, 'error': str(e)}


def compare_faces(known_encodings, face_encoding_to_check, tolerance=FACE_MATCH_THRESHOLD):
    """
    Compare a face encoding against a list of known encodings
    
    Args:
        known_encodings: List of numpy arrays (128,)
        face_encoding_to_check: numpy array (128,)
        tolerance: float, match threshold (default 0.6)
    
    Returns:
        dict with keys:
            - matches: list of bool
            - face_distances: list of float
            - best_match_index: int or None
            - best_match_distance: float or None
    """
    if len(known_encodings) == 0:
        return {
            'matches': [],
            'face_distances': [],
            'best_match_index': None,
            'best_match_distance': None
        }
    
    # Calculate distances
    face_distances = face_recognition.face_distance(known_encodings, face_encoding_to_check)
    
    # Determine matches
    matches = list(face_distances <= tolerance)
    
    # Find best match
    best_match_index = None
    best_match_distance = None
    
    if any(matches):
        best_match_index = int(np.argmin(face_distances))
        best_match_distance = float(face_distances[best_match_index])
    
    return {
        'matches': matches,
        'face_distances': face_distances.tolist(),
        'best_match_index': best_match_index,
        'best_match_distance': best_match_distance
    }


def find_matching_student(face_encoding, face_encodings_qs, tolerance=FACE_MATCH_THRESHOLD):
    """
    Find the best matching student from database encodings
    
    Args:
        face_encoding: numpy array (128,) to match
        face_encodings_qs: QuerySet of FaceEncoding objects
        tolerance: float, match threshold
    
    Returns:
        dict with keys:
            - found: bool
            - student: Student object or None
            - confidence: float (distance score)
            - num_compared: int
    """
    from .models import FaceEncoding
    
    # Get all active encodings
    known_encodings = []
    student_map = {}
    
    for idx, face_enc_obj in enumerate(face_encodings_qs):
        encoding = face_enc_obj.get_encoding()
        if encoding is not None:
            known_encodings.append(encoding)
            student_map[idx] = face_enc_obj.student
    
    if len(known_encodings) == 0:
        return {
            'found': False,
            'student': None,
            'confidence': None,
            'num_compared': 0
        }
    
    # Compare faces
    result = compare_faces(known_encodings, face_encoding, tolerance)
    
    if result['best_match_index'] is not None:
        return {
            'found': True,
            'student': student_map[result['best_match_index']],
            'confidence': result['best_match_distance'],
            'num_compared': len(known_encodings)
        }
    
    return {
        'found': False,
        'student': None,
        'confidence': result['face_distances'][0] if result['face_distances'] else None,
        'num_compared': len(known_encodings)
    }


def crop_face_from_image(image_path, face_location, output_path=None, padding=20):
    """
    Crop face from image using face location
    
    Args:
        image_path: Path to source image
        face_location: tuple (top, right, bottom, left)
        output_path: Optional path to save cropped image
        padding: int, pixels to add around face
    
    Returns:
        PIL Image object or None
    """
    try:
        img = Image.open(image_path)
        top, right, bottom, left = face_location
        
        # Add padding
        width, height = img.size
        top = max(0, top - padding)
        right = min(width, right + padding)
        bottom = min(height, bottom + padding)
        left = max(0, left - padding)
        
        # Crop
        cropped = img.crop((left, top, right, bottom))
        
        if output_path:
            cropped.save(output_path)
        
        return cropped
        
    except Exception as e:
        logger.error(f"Error cropping face: {str(e)}")
        return None

"""
Utility functions for face recognition operations
"""
import face_recognition
import numpy as np
from PIL import Image
import cv2
import logging
from pathlib import Path
from typing import Union, List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Recognition threshold - lower is more strict
FACE_MATCH_THRESHOLD = 0.6  # Standard threshold
FACE_MATCH_THRESHOLD_STRICT = 0.5  # For high-security scenarios
FACE_MATCH_THRESHOLD_LENIENT = 0.65  # For challenging conditions

# Quality thresholds
MIN_BRIGHTNESS = 40
MAX_BRIGHTNESS = 220
MIN_SHARPNESS = 75
MIN_FACE_SIZE = 100


@dataclass
class FaceExtractionResult:
    """Result of face extraction operation"""
    success: bool
    encoding: Optional[np.ndarray] = None
    face_location: Optional[Tuple[int, int, int, int]] = None
    error: Optional[str] = None
    num_faces: int = 0
    quality_metrics: Optional[Dict] = None


@dataclass
class FaceMatchResult:
    """Result of face matching operation"""
    found: bool
    student: Optional[object] = None
    confidence: Optional[float] = None
    match_distance: Optional[float] = None
    num_compared: int = 0


def load_image(image_input: Union[str, Path, Image.Image, np.ndarray]) -> Optional[np.ndarray]:
    """
    Load image from various input types
    
    Args:
        image_input: Path, PIL Image, or numpy array
    
    Returns:
        numpy array or None
    """
    try:
        if isinstance(image_input, (str, Path)):
            return face_recognition.load_image_file(str(image_input))
        elif isinstance(image_input, Image.Image):
            return np.array(image_input)
        elif isinstance(image_input, np.ndarray):
            return image_input
        else:
            logger.error(f"Unsupported image input type: {type(image_input)}")
            return None
    except Exception as e:
        logger.error(f"Error loading image: {str(e)}")
        return None


def extract_face_from_image(
    image_path: Union[str, Path, Image.Image],
    model: str = 'hog',
    include_quality: bool = True,
    num_jitters: int = 1
) -> FaceExtractionResult:
    """
    Extract face location and encoding from an image
    
    Args:
        image_path: Path to image file or PIL Image object
        model: 'hog' (faster, CPU) or 'cnn' (more accurate, GPU)
        include_quality: Whether to calculate quality metrics
        num_jitters: Number of times to re-sample face for encoding (higher = more accurate but slower)
    
    Returns:
        FaceExtractionResult object
    """
    try:
        # Load image
        image = load_image(image_path)
        if image is None:
            return FaceExtractionResult(
                success=False,
                error='Could not load image'
            )
        
        # Find face locations
        face_locations = face_recognition.face_locations(image, model=model)
        
        if len(face_locations) == 0:
            return FaceExtractionResult(
                success=False,
                error='No face detected in the image',
                num_faces=0
            )
        
        # Handle multiple faces
        if len(face_locations) > 1:
            logger.warning(f"Multiple faces detected ({len(face_locations)}), using the largest one")
            face_locations = [_get_largest_face(face_locations)]
        
        face_location = face_locations[0]
        
        # Generate face encoding with jittering for better accuracy
        face_encodings = face_recognition.face_encodings(
            image, 
            face_locations,
            num_jitters=num_jitters
        )
        
        if len(face_encodings) == 0:
            return FaceExtractionResult(
                success=False,
                error='Could not generate face encoding',
                num_faces=len(face_locations)
            )
        
        # Calculate quality if requested
        quality_metrics = None
        if include_quality and isinstance(image_path, (str, Path)):
            quality_metrics = calculate_face_quality(image_path, face_location)
        
        return FaceExtractionResult(
            success=True,
            encoding=face_encodings[0],
            face_location=face_location,
            num_faces=len(face_locations),
            quality_metrics=quality_metrics
        )
        
    except Exception as e:
        logger.error(f"Error extracting face: {str(e)}", exc_info=True)
        return FaceExtractionResult(
            success=False,
            error=f'Error processing image: {str(e)}',
            num_faces=0
        )


def _get_largest_face(face_locations: List[Tuple]) -> Tuple:
    """Get the largest face from a list of face locations"""
    return max(face_locations, key=lambda loc: (loc[2] - loc[0]) * (loc[1] - loc[3]))


def calculate_face_quality(
    image_path: Union[str, Path],
    face_location: Optional[Tuple[int, int, int, int]] = None
) -> Dict:
    """
    Calculate quality metrics for a face image
    
    Args:
        image_path: Path to image file
        face_location: Optional tuple (top, right, bottom, left)
    
    Returns:
        dict with quality metrics
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
        
        # Calculate contrast
        contrast = gray.std()
        
        # Get face size if location provided
        face_size = 0
        aspect_ratio = 1.0
        if face_location:
            top, right, bottom, left = face_location
            face_size = right - left
            face_height = bottom - top
            aspect_ratio = face_size / face_height if face_height > 0 else 1.0
        
        # Quality assessment with detailed feedback
        quality_issues = []
        if brightness < MIN_BRIGHTNESS:
            quality_issues.append('too_dark')
        elif brightness > MAX_BRIGHTNESS:
            quality_issues.append('too_bright')
        
        if laplacian_var < MIN_SHARPNESS:
            quality_issues.append('blurry')
        
        if face_size > 0 and face_size < MIN_FACE_SIZE:
            quality_issues.append('face_too_small')
        
        # Unusual aspect ratio might indicate partial face
        if aspect_ratio < 0.6 or aspect_ratio > 1.4:
            quality_issues.append('unusual_aspect_ratio')
        
        is_good_quality = len(quality_issues) == 0
        
        return {
            'brightness': float(brightness),
            'sharpness': float(laplacian_var),
            'contrast': float(contrast),
            'size': int(face_size),
            'aspect_ratio': float(aspect_ratio),
            'is_good_quality': is_good_quality,
            'quality_issues': quality_issues,
            'quality_score': _calculate_quality_score(brightness, laplacian_var, contrast, face_size)
        }
        
    except Exception as e:
        logger.error(f"Error calculating face quality: {str(e)}", exc_info=True)
        return {'is_good_quality': False, 'error': str(e)}


def _calculate_quality_score(brightness: float, sharpness: float, contrast: float, face_size: int) -> float:
    """Calculate overall quality score (0-100)"""
    brightness_score = min(100, max(0, 100 - abs(brightness - 128) * 0.5))
    sharpness_score = min(100, (sharpness / 200) * 100)
    contrast_score = min(100, (contrast / 100) * 100)
    size_score = min(100, (face_size / 200) * 100) if face_size > 0 else 50
    
    return (brightness_score + sharpness_score + contrast_score + size_score) / 4


def compare_faces(
    known_encodings: List[np.ndarray],
    face_encoding_to_check: np.ndarray,
    tolerance: float = FACE_MATCH_THRESHOLD
) -> Dict:
    """
    Compare a face encoding against a list of known encodings
    
    Args:
        known_encodings: List of numpy arrays (128,)
        face_encoding_to_check: numpy array (128,)
        tolerance: float, match threshold
    
    Returns:
        dict with comparison results
    """
    if len(known_encodings) == 0:
        return {
            'matches': [],
            'face_distances': [],
            'best_match_index': None,
            'best_match_distance': None,
            'confidence_score': None
        }
    
    # Calculate distances
    face_distances = face_recognition.face_distance(known_encodings, face_encoding_to_check)
    
    # Determine matches
    matches = list(face_distances <= tolerance)
    
    # Find best match
    best_match_index = None
    best_match_distance = None
    confidence_score = None
    
    if any(matches):
        best_match_index = int(np.argmin(face_distances))
        best_match_distance = float(face_distances[best_match_index])
        # Convert distance to confidence percentage (0 = perfect match, 1 = no match)
        confidence_score = max(0, (1 - best_match_distance) * 100)
    
    return {
        'matches': matches,
        'face_distances': face_distances.tolist(),
        'best_match_index': best_match_index,
        'best_match_distance': best_match_distance,
        'confidence_score': confidence_score
    }


def find_matching_student(
    face_encoding: np.ndarray,
    face_encodings_qs,
    tolerance: float = FACE_MATCH_THRESHOLD,
    min_confidence: Optional[float] = None
) -> FaceMatchResult:
    """
    Find the best matching student from database encodings
    
    Args:
        face_encoding: numpy array (128,) to match
        face_encodings_qs: QuerySet of FaceEncoding objects
        tolerance: float, match threshold
        min_confidence: Optional minimum confidence score (0-100)
    
    Returns:
        FaceMatchResult object
    """
    # Get all active encodings
    known_encodings = []
    student_map = {}
    
    for idx, face_enc_obj in enumerate(face_encodings_qs):
        encoding = face_enc_obj.get_encoding()
        if encoding is not None:
            known_encodings.append(encoding)
            student_map[idx] = face_enc_obj.student
    
    if len(known_encodings) == 0:
        return FaceMatchResult(
            found=False,
            num_compared=0
        )
    
    # Compare faces
    result = compare_faces(known_encodings, face_encoding, tolerance)
    
    if result['best_match_index'] is not None:
        # Check minimum confidence if specified
        if min_confidence is not None and result['confidence_score'] < min_confidence:
            return FaceMatchResult(
                found=False,
                confidence=result['confidence_score'],
                match_distance=result['best_match_distance'],
                num_compared=len(known_encodings)
            )
        
        return FaceMatchResult(
            found=True,
            student=student_map[result['best_match_index']],
            confidence=result['confidence_score'],
            match_distance=result['best_match_distance'],
            num_compared=len(known_encodings)
        )
    
    return FaceMatchResult(
        found=False,
        match_distance=result['face_distances'][0] if result['face_distances'] else None,
        num_compared=len(known_encodings)
    )


def crop_face_from_image(
    image_path: Union[str, Path],
    face_location: Tuple[int, int, int, int],
    output_path: Optional[Union[str, Path]] = None,
    padding: int = 20,
    target_size: Optional[Tuple[int, int]] = None
) -> Optional[Image.Image]:
    """
    Crop face from image using face location
    
    Args:
        image_path: Path to source image
        face_location: tuple (top, right, bottom, left)
        output_path: Optional path to save cropped image
        padding: int, pixels to add around face
        target_size: Optional (width, height) to resize cropped face
    
    Returns:
        PIL Image object or None
    """
    try:
        img = Image.open(image_path)
        top, right, bottom, left = face_location
        
        # Add padding with bounds checking
        width, height = img.size
        top = max(0, top - padding)
        right = min(width, right + padding)
        bottom = min(height, bottom + padding)
        left = max(0, left - padding)
        
        # Crop
        cropped = img.crop((left, top, right, bottom))
        
        # Resize if target size specified
        if target_size:
            cropped = cropped.resize(target_size, Image.Resampling.LANCZOS)
        
        # Save if output path provided
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            cropped.save(output_path, quality=95)
        
        return cropped
        
    except Exception as e:
        logger.error(f"Error cropping face: {str(e)}", exc_info=True)
        return None


def batch_extract_faces(
    image_paths: List[Union[str, Path]],
    model: str = 'hog',
    max_workers: int = 4
) -> List[FaceExtractionResult]:
    """
    Extract faces from multiple images in parallel
    
    Args:
        image_paths: List of image paths
        model: Detection model to use
        max_workers: Number of parallel workers
    
    Returns:
        List of FaceExtractionResult objects
    """
    from concurrent.futures import ThreadPoolExecutor
    
    def process_single(path):
        return extract_face_from_image(path, model=model)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_single, image_paths))
    
    return results


def validate_encoding(encoding: np.ndarray) -> bool:
    """
    Validate that an encoding is properly formatted
    
    Args:
        encoding: Face encoding to validate
    
    Returns:
        bool indicating if valid
    """
    if encoding is None:
        return False
    if not isinstance(encoding, np.ndarray):
        return False
    if encoding.shape != (128,):
        return False
    if np.isnan(encoding).any() or np.isinf(encoding).any():
        return False
    return True
"""
Enhanced utility functions for face recognition operations
Includes improved error handling, caching, and advanced features
"""
import face_recognition
import numpy as np
from PIL import Image
import cv2
import logging
from pathlib import Path
from typing import Union, List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from functools import lru_cache
from enum import Enum
import hashlib
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# Recognition thresholds
class MatchThreshold(Enum):
    """Enumeration for different matching thresholds"""
    STRICT = 0.45
    STANDARD = 0.60
    LENIENT = 0.65
    VERY_LENIENT = 0.70

# Quality thresholds
class QualityThresholds:
    """Centralized quality thresholds"""
    MIN_BRIGHTNESS = 40
    MAX_BRIGHTNESS = 220
    OPTIMAL_BRIGHTNESS_MIN = 80
    OPTIMAL_BRIGHTNESS_MAX = 180
    MIN_SHARPNESS = 75
    OPTIMAL_SHARPNESS = 150
    MIN_CONTRAST = 25
    MIN_FACE_SIZE = 100
    OPTIMAL_FACE_SIZE = 200
    MIN_ASPECT_RATIO = 0.6
    MAX_ASPECT_RATIO = 1.4

# Detection models
class DetectionModel(Enum):
    """Face detection models"""
    HOG = 'hog'  # Faster, CPU-friendly
    CNN = 'cnn'  # More accurate, GPU recommended

@dataclass
class QualityMetrics:
    """Detailed quality metrics for face images"""
    brightness: float
    sharpness: float
    contrast: float
    face_size: int
    aspect_ratio: float
    quality_score: float
    is_good_quality: bool
    quality_issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'brightness': self.brightness,
            'sharpness': self.sharpness,
            'contrast': self.contrast,
            'face_size': self.face_size,
            'aspect_ratio': self.aspect_ratio,
            'quality_score': self.quality_score,
            'is_good_quality': self.is_good_quality,
            'quality_issues': self.quality_issues,
            'recommendations': self.recommendations
        }

@dataclass
class FaceExtractionResult:
    """Enhanced result of face extraction operation"""
    success: bool
    encoding: Optional[np.ndarray] = None
    face_location: Optional[Tuple[int, int, int, int]] = None
    landmarks: Optional[Dict] = None
    error: Optional[str] = None
    num_faces: int = 0
    quality_metrics: Optional[QualityMetrics] = None
    processing_time: Optional[float] = None
    image_hash: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'success': self.success,
            'encoding': self.encoding.tolist() if self.encoding is not None else None,
            'face_location': self.face_location,
            'landmarks': self.landmarks,
            'error': self.error,
            'num_faces': self.num_faces,
            'quality_metrics': self.quality_metrics.to_dict() if self.quality_metrics else None,
            'processing_time': self.processing_time,
            'image_hash': self.image_hash
        }

@dataclass
class FaceMatchResult:
    """Enhanced result of face matching operation"""
    found: bool
    student: Optional[Any] = None
    confidence: Optional[float] = None
    match_distance: Optional[float] = None
    num_compared: int = 0
    alternative_matches: List[Dict] = field(default_factory=list)
    match_quality: Optional[str] = None  # 'excellent', 'good', 'fair', 'poor'
    processing_time: Optional[float] = None
    
    def get_match_quality_label(self) -> str:
        """Get human-readable match quality"""
        if not self.found or self.confidence is None:
            return 'no_match'
        if self.confidence >= 85:
            return 'excellent'
        elif self.confidence >= 75:
            return 'good'
        elif self.confidence >= 65:
            return 'fair'
        else:
            return 'poor'

class ImageHasher:
    """Utility for generating image hashes"""
    
    @staticmethod
    def hash_image(image_input: Union[str, Path, np.ndarray]) -> Optional[str]:
        """Generate hash for image content"""
        try:
            if isinstance(image_input, (str, Path)):
                with open(image_input, 'rb') as f:
                    return hashlib.sha256(f.read()).hexdigest()
            elif isinstance(image_input, np.ndarray):
                return hashlib.sha256(image_input.tobytes()).hexdigest()
            return None
        except Exception as e:
            logger.error(f"Error hashing image: {e}")
            return None

class ImageLoader:
    """Enhanced image loading with validation"""
    
    @staticmethod
    def load_image(image_input: Union[str, Path, Image.Image, np.ndarray]) -> Optional[np.ndarray]:
        """
        Load and validate image from various input types
        
        Args:
            image_input: Path, PIL Image, or numpy array
            
        Returns:
            numpy array or None
        """
        try:
            if isinstance(image_input, (str, Path)):
                path = Path(image_input)
                if not path.exists():
                    logger.error(f"Image file not found: {path}")
                    return None
                if not path.is_file():
                    logger.error(f"Path is not a file: {path}")
                    return None
                # Validate file extension
                valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
                if path.suffix.lower() not in valid_extensions:
                    logger.warning(f"Unusual image extension: {path.suffix}")
                return face_recognition.load_image_file(str(path))
                
            elif isinstance(image_input, Image.Image):
                # Convert RGBA to RGB if necessary
                if image_input.mode == 'RGBA':
                    image_input = image_input.convert('RGB')
                return np.array(image_input)
                
            elif isinstance(image_input, np.ndarray):
                # Validate array shape
                if len(image_input.shape) not in [2, 3]:
                    logger.error(f"Invalid image array shape: {image_input.shape}")
                    return None
                return image_input
                
            else:
                logger.error(f"Unsupported image input type: {type(image_input)}")
                return None
                
        except Exception as e:
            logger.error(f"Error loading image: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def validate_image_array(image: np.ndarray) -> bool:
        """Validate image array properties"""
        if image is None:
            return False
        if not isinstance(image, np.ndarray):
            return False
        if len(image.shape) not in [2, 3]:
            return False
        if image.size == 0:
            return False
        return True

class FaceExtractor:
    """Advanced face extraction with caching and optimization"""
    
    def __init__(self, cache_size: int = 128):
        self.cache_size = cache_size
        
    def extract_face(
        self,
        image_path: Union[str, Path, Image.Image],
        model: DetectionModel = DetectionModel.HOG,
        include_quality: bool = True,
        include_landmarks: bool = True,
        num_jitters: int = 1,
        upsample_times: int = 1
    ) -> FaceExtractionResult:
        """
        Extract face with enhanced features
        
        Args:
            image_path: Path to image or PIL Image
            model: Detection model to use
            include_quality: Calculate quality metrics
            include_landmarks: Extract facial landmarks
            num_jitters: Re-sampling count for encoding accuracy
            upsample_times: How many times to upsample image for detection
            
        Returns:
            FaceExtractionResult object
        """
        start_time = datetime.now()
        
        try:
            # Load image
            image = ImageLoader.load_image(image_path)
            if image is None:
                return FaceExtractionResult(
                    success=False,
                    error='Could not load image'
                )
            
            # Validate image
            if not ImageLoader.validate_image_array(image):
                return FaceExtractionResult(
                    success=False,
                    error='Invalid image array'
                )
            
            # Generate image hash for caching
            image_hash = ImageHasher.hash_image(image_path)
            
            # Detect faces
            face_locations = face_recognition.face_locations(
                image,
                number_of_times_to_upsample=upsample_times,
                model=model.value
            )
            
            if len(face_locations) == 0:
                return FaceExtractionResult(
                    success=False,
                    error='No face detected in the image',
                    num_faces=0,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    image_hash=image_hash
                )
            
            # Handle multiple faces
            if len(face_locations) > 1:
                logger.warning(f"Multiple faces detected ({len(face_locations)}), using largest")
                face_location = self._get_largest_face(face_locations)
            else:
                face_location = face_locations[0]
            
            # Generate encoding with jittering
            face_encodings = face_recognition.face_encodings(
                image,
                [face_location],
                num_jitters=num_jitters
            )
            
            if len(face_encodings) == 0:
                return FaceExtractionResult(
                    success=False,
                    error='Could not generate face encoding',
                    num_faces=len(face_locations),
                    face_location=face_location,
                    processing_time=(datetime.now() - start_time).total_seconds()
                )
            
            # Extract landmarks if requested
            landmarks = None
            if include_landmarks:
                landmarks_list = face_recognition.face_landmarks(image, [face_location])
                if landmarks_list:
                    landmarks = landmarks_list[0]
            
            # Calculate quality metrics
            quality_metrics = None
            if include_quality:
                quality_calculator = QualityCalculator()
                quality_metrics = quality_calculator.calculate_quality(
                    image_path,
                    face_location,
                    landmarks
                )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return FaceExtractionResult(
                success=True,
                encoding=face_encodings[0],
                face_location=face_location,
                landmarks=landmarks,
                num_faces=len(face_locations),
                quality_metrics=quality_metrics,
                processing_time=processing_time,
                image_hash=image_hash
            )
            
        except Exception as e:
            logger.error(f"Error extracting face: {str(e)}", exc_info=True)
            return FaceExtractionResult(
                success=False,
                error=f'Error processing image: {str(e)}',
                processing_time=(datetime.now() - start_time).total_seconds()
            )
    
    @staticmethod
    def _get_largest_face(face_locations: List[Tuple]) -> Tuple:
        """Get the largest face from a list of face locations"""
        return max(
            face_locations,
            key=lambda loc: (loc[2] - loc[0]) * (loc[1] - loc[3])
        )

class QualityCalculator:
    """Advanced quality calculation with detailed feedback"""
    
    def calculate_quality(
        self,
        image_path: Union[str, Path],
        face_location: Optional[Tuple[int, int, int, int]] = None,
        landmarks: Optional[Dict] = None
    ) -> QualityMetrics:
        """
        Calculate comprehensive quality metrics
        
        Args:
            image_path: Path to image
            face_location: Optional face bounding box
            landmarks: Optional facial landmarks
            
        Returns:
            QualityMetrics object
        """
        try:
            # Load image
            img = cv2.imread(str(image_path))
            if img is None:
                return self._create_error_metrics('Could not load image')
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate basic metrics
            brightness = float(np.mean(gray))
            contrast = float(gray.std())
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            
            # Face-specific metrics
            face_size = 0
            aspect_ratio = 1.0
            if face_location:
                top, right, bottom, left = face_location
                face_size = right - left
                face_height = bottom - top
                aspect_ratio = face_size / face_height if face_height > 0 else 1.0
            
            # Analyze quality
            quality_issues = []
            recommendations = []
            
            # Brightness analysis
            if brightness < QualityThresholds.MIN_BRIGHTNESS:
                quality_issues.append('too_dark')
                recommendations.append('Increase lighting or use flash')
            elif brightness > QualityThresholds.MAX_BRIGHTNESS:
                quality_issues.append('too_bright')
                recommendations.append('Reduce lighting or avoid direct light')
            elif brightness < QualityThresholds.OPTIMAL_BRIGHTNESS_MIN:
                recommendations.append('Could benefit from more light')
            elif brightness > QualityThresholds.OPTIMAL_BRIGHTNESS_MAX:
                recommendations.append('Could benefit from less light')
            
            # Sharpness analysis
            if sharpness < QualityThresholds.MIN_SHARPNESS:
                quality_issues.append('blurry')
                recommendations.append('Hold camera steady or increase shutter speed')
            elif sharpness < QualityThresholds.OPTIMAL_SHARPNESS:
                recommendations.append('Image could be sharper')
            
            # Contrast analysis
            if contrast < QualityThresholds.MIN_CONTRAST:
                quality_issues.append('low_contrast')
                recommendations.append('Improve lighting conditions')
            
            # Face size analysis
            if face_size > 0:
                if face_size < QualityThresholds.MIN_FACE_SIZE:
                    quality_issues.append('face_too_small')
                    recommendations.append('Move closer to camera')
                elif face_size < QualityThresholds.OPTIMAL_FACE_SIZE:
                    recommendations.append('Could move slightly closer')
                
                # Aspect ratio
                if aspect_ratio < QualityThresholds.MIN_ASPECT_RATIO or \
                   aspect_ratio > QualityThresholds.MAX_ASPECT_RATIO:
                    quality_issues.append('unusual_aspect_ratio')
                    recommendations.append('Ensure full face is visible')
            
            # Landmark-based analysis
            if landmarks:
                self._analyze_landmarks(landmarks, quality_issues, recommendations)
            
            # Calculate overall score
            quality_score = self._calculate_quality_score(
                brightness, sharpness, contrast, face_size
            )
            
            is_good_quality = len(quality_issues) == 0 and quality_score >= 70
            
            return QualityMetrics(
                brightness=brightness,
                sharpness=sharpness,
                contrast=contrast,
                face_size=face_size,
                aspect_ratio=aspect_ratio,
                quality_score=quality_score,
                is_good_quality=is_good_quality,
                quality_issues=quality_issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error calculating quality: {str(e)}", exc_info=True)
            return self._create_error_metrics(str(e))
    
    @staticmethod
    def _analyze_landmarks(landmarks: Dict, issues: List[str], recommendations: List[str]):
        """Analyze facial landmarks for quality issues"""
        try:
            # Check if face is significantly tilted
            left_eye = landmarks.get('left_eye', [])
            right_eye = landmarks.get('right_eye', [])
            
            if left_eye and right_eye:
                left_eye_center = np.mean(left_eye, axis=0)
                right_eye_center = np.mean(right_eye, axis=0)
                
                # Calculate tilt angle
                dy = right_eye_center[1] - left_eye_center[1]
                dx = right_eye_center[0] - left_eye_center[0]
                angle = abs(np.degrees(np.arctan2(dy, dx)))
                
                if angle > 15:
                    issues.append('face_tilted')
                    recommendations.append('Keep face level with camera')
        except Exception as e:
            logger.warning(f"Error analyzing landmarks: {e}")
    
    @staticmethod
    def _calculate_quality_score(
        brightness: float,
        sharpness: float,
        contrast: float,
        face_size: int
    ) -> float:
        """Calculate weighted quality score (0-100)"""
        # Brightness score (centered around 128)
        brightness_diff = abs(brightness - 128)
        brightness_score = max(0, 100 - brightness_diff * 0.5)
        
        # Sharpness score
        sharpness_score = min(100, (sharpness / 200) * 100)
        
        # Contrast score
        contrast_score = min(100, (contrast / 100) * 100)
        
        # Size score
        if face_size > 0:
            size_score = min(100, (face_size / 200) * 100)
        else:
            size_score = 50
        
        # Weighted average
        weights = [0.25, 0.35, 0.20, 0.20]
        scores = [brightness_score, sharpness_score, contrast_score, size_score]
        
        return sum(w * s for w, s in zip(weights, scores))
    
    @staticmethod
    def _create_error_metrics(error_msg: str) -> QualityMetrics:
        """Create error metrics object"""
        return QualityMetrics(
            brightness=0.0,
            sharpness=0.0,
            contrast=0.0,
            face_size=0,
            aspect_ratio=0.0,
            quality_score=0.0,
            is_good_quality=False,
            quality_issues=['error'],
            recommendations=[error_msg]
        )

class FaceMatcher:
    """Enhanced face matching with confidence analysis"""
    
    def __init__(self, threshold: MatchThreshold = MatchThreshold.STANDARD):
        self.threshold = threshold.value
    
    def compare_faces(
        self,
        known_encodings: List[np.ndarray],
        face_encoding: np.ndarray,
        tolerance: Optional[float] = None
    ) -> Dict:
        """
        Compare face against known encodings with detailed results
        
        Args:
            known_encodings: List of known face encodings
            face_encoding: Encoding to match
            tolerance: Optional custom tolerance
            
        Returns:
            Dictionary with comparison results
        """
        if tolerance is None:
            tolerance = self.threshold
        
        if len(known_encodings) == 0:
            return self._empty_comparison_result()
        
        # Validate input encoding
        if not EncodingValidator.validate_encoding(face_encoding):
            logger.error("Invalid face encoding provided")
            return self._empty_comparison_result()
        
        # Calculate distances
        face_distances = face_recognition.face_distance(known_encodings, face_encoding)
        
        # Determine matches
        matches = list(face_distances <= tolerance)
        
        # Sort by distance to get top matches
        sorted_indices = np.argsort(face_distances)
        
        # Compile results
        best_match_index = None
        best_match_distance = None
        confidence_score = None
        alternative_matches = []
        
        if any(matches):
            best_match_index = int(sorted_indices[0])
            best_match_distance = float(face_distances[best_match_index])
            confidence_score = self._distance_to_confidence(best_match_distance)
            
            # Collect alternative matches (top 5)
            for idx in sorted_indices[1:6]:
                dist = float(face_distances[idx])
                if dist <= tolerance * 1.2:  # Include near-misses
                    alternative_matches.append({
                        'index': int(idx),
                        'distance': dist,
                        'confidence': self._distance_to_confidence(dist),
                        'is_match': dist <= tolerance
                    })
        
        return {
            'matches': matches,
            'face_distances': face_distances.tolist(),
            'best_match_index': best_match_index,
            'best_match_distance': best_match_distance,
            'confidence_score': confidence_score,
            'alternative_matches': alternative_matches,
            'num_compared': len(known_encodings),
            'threshold_used': tolerance
        }
    
    def find_matching_student(
        self,
        face_encoding: np.ndarray,
        face_encodings_qs,
        tolerance: Optional[float] = None,
        min_confidence: Optional[float] = None,
        return_alternatives: bool = True
    ) -> FaceMatchResult:
        """
        Find best matching student with enhanced analysis
        
        Args:
            face_encoding: Encoding to match
            face_encodings_qs: QuerySet of FaceEncoding objects
            tolerance: Optional custom tolerance
            min_confidence: Minimum confidence threshold (0-100)
            return_alternatives: Include alternative matches
            
        Returns:
            FaceMatchResult object
        """
        start_time = datetime.now()
        
        if tolerance is None:
            tolerance = self.threshold
        
        # Build encoding list and student map
        known_encodings = []
        student_map = {}
        
        for idx, face_enc_obj in enumerate(face_encodings_qs):
            encoding = face_enc_obj.get_encoding()
            if encoding is not None and EncodingValidator.validate_encoding(encoding):
                known_encodings.append(encoding)
                student_map[idx] = face_enc_obj.student
        
        if len(known_encodings) == 0:
            return FaceMatchResult(
                found=False,
                num_compared=0,
                processing_time=(datetime.now() - start_time).total_seconds()
            )
        
        # Compare faces
        result = self.compare_faces(known_encodings, face_encoding, tolerance)
        
        # Process results
        if result['best_match_index'] is not None:
            confidence = result['confidence_score']
            
            # Check minimum confidence
            if min_confidence is not None and confidence < min_confidence:
                logger.info(f"Match found but confidence {confidence:.2f} below minimum {min_confidence}")
                return FaceMatchResult(
                    found=False,
                    confidence=confidence,
                    match_distance=result['best_match_distance'],
                    num_compared=len(known_encodings),
                    processing_time=(datetime.now() - start_time).total_seconds()
                )
            
            # Build alternative matches
            alternatives = []
            if return_alternatives:
                for alt in result['alternative_matches']:
                    if alt['index'] in student_map:
                        alternatives.append({
                            'student': student_map[alt['index']],
                            'confidence': alt['confidence'],
                            'distance': alt['distance'],
                            'is_match': alt['is_match']
                        })
            
            match_result = FaceMatchResult(
                found=True,
                student=student_map[result['best_match_index']],
                confidence=confidence,
                match_distance=result['best_match_distance'],
                num_compared=len(known_encodings),
                alternative_matches=alternatives,
                processing_time=(datetime.now() - start_time).total_seconds()
            )
            match_result.match_quality = match_result.get_match_quality_label()
            
            return match_result
        
        return FaceMatchResult(
            found=False,
            match_distance=result['face_distances'][0] if result['face_distances'] else None,
            num_compared=len(known_encodings),
            processing_time=(datetime.now() - start_time).total_seconds()
        )
    
    @staticmethod
    def _distance_to_confidence(distance: float) -> float:
        """Convert distance to confidence percentage"""
        return max(0.0, min(100.0, (1.0 - distance) * 100))
    
    @staticmethod
    def _empty_comparison_result() -> Dict:
        """Return empty comparison result"""
        return {
            'matches': [],
            'face_distances': [],
            'best_match_index': None,
            'best_match_distance': None,
            'confidence_score': None,
            'alternative_matches': [],
            'num_compared': 0
        }

class EncodingValidator:
    """Validate face encodings"""
    
    @staticmethod
    def validate_encoding(encoding: np.ndarray) -> bool:
        """
        Validate face encoding format and content
        
        Args:
            encoding: Face encoding to validate
            
        Returns:
            True if valid, False otherwise
        """
        if encoding is None:
            return False
        
        if not isinstance(encoding, np.ndarray):
            logger.error(f"Encoding is not numpy array: {type(encoding)}")
            return False
        
        if encoding.shape != (128,):
            logger.error(f"Invalid encoding shape: {encoding.shape}")
            return False
        
        if np.isnan(encoding).any():
            logger.error("Encoding contains NaN values")
            return False
        
        if np.isinf(encoding).any():
            logger.error("Encoding contains infinite values")
            return False
        
        # Check if encoding is all zeros (likely invalid)
        if np.all(encoding == 0):
            logger.error("Encoding is all zeros")
            return False
        
        return True
    
    @staticmethod
    def validate_encoding_similarity(enc1: np.ndarray, enc2: np.ndarray) -> bool:
        """Check if two encodings are suspiciously similar (possible duplicate)"""
        if not (EncodingValidator.validate_encoding(enc1) and 
                EncodingValidator.validate_encoding(enc2)):
            return False
        
        distance = face_recognition.face_distance([enc1], enc2)[0]
        # If distance is near zero, encodings are nearly identical
        return distance > 0.001

class FaceImageProcessor:
    """Utility for processing face images"""
    
    @staticmethod
    def crop_face(
        image_path: Union[str, Path],
        face_location: Tuple[int, int, int, int],
        output_path: Optional[Union[str, Path]] = None,
        padding: int = 20,
        target_size: Optional[Tuple[int, int]] = None,
        quality: int = 95
    ) -> Optional[Image.Image]:
        """
        Crop face from image with enhancements
        
        Args:
            image_path: Source image path
            face_location: (top, right, bottom, left)
            output_path: Optional save path
            padding: Pixels around face
            target_size: Optional resize dimensions
            quality: JPEG quality (1-100)
            
        Returns:
            PIL Image or None
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
            
            # Ensure valid crop dimensions
            if right <= left or bottom <= top:
                logger.error("Invalid crop dimensions")
                return None
            
            # Crop
            cropped = img.crop((left, top, right, bottom))
            
            # Resize if specified
            if target_size:
                cropped = cropped.resize(target_size, Image.Resampling.LANCZOS)
            
            # Save if path provided
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Determine format
                save_format = output_path.suffix.lower()
                if save_format in ['.jpg', '.jpeg']:
                    cropped.save(output_path, 'JPEG', quality=quality, optimize=True)
                elif save_format == '.png':
                    cropped.save(output_path, 'PNG', optimize=True)
                else:
                    cropped.save(output_path, quality=quality)
            
            return cropped
            
        except Exception as e:
            logger.error(f"Error cropping face: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def align_face(
        image: np.ndarray,
        landmarks: Dict
    ) -> Optional[np.ndarray]:
        """
        Align face using eye positions for better recognition
        
        Args:
            image: Image array
            landmarks: Facial landmarks dictionary
            
        Returns:
            Aligned image array or None
        """
        try:
            left_eye = landmarks.get('left_eye')
            right_eye = landmarks.get('right_eye')
            
            if not left_eye or not right_eye:
                return image
            
            # Calculate eye centers
            left_eye_center = np.mean(left_eye, axis=0).astype(int)
            right_eye_center = np.mean(right_eye, axis=0).astype(int)
            
            # Calculate angle
            dy = right_eye_center[1] - left_eye_center[1]
            dx = right_eye_center[0] - left_eye_center[0]
            angle = np.degrees(np.arctan2(dy, dx))
            
            # Get rotation matrix
            eyes_center = ((left_eye_center[0] + right_eye_center[0]) // 2,
                          (left_eye_center[1] + right_eye_center[1]) // 2)
            
            rotation_matrix = cv2.getRotationMatrix2D(eyes_center, angle, scale=1.0)
            
            # Apply rotation
            aligned = cv2.warpAffine(
                image,
                rotation_matrix,
                (image.shape[1], image.shape[0]),
                flags=cv2.INTER_CUBIC
            )
            
            return aligned
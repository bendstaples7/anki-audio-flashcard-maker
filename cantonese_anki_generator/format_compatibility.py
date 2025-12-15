"""
Format compatibility and robustness features for the Cantonese Anki Generator.

Provides enhanced format support, quality tolerance mechanisms, and adaptive
processing for various input formats and edge cases.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from urllib.parse import urlparse, parse_qs
import numpy as np

from .audio.loader import AudioLoader, AudioValidationError
from .processors.google_docs_parser import GoogleDocsParser, GoogleDocsParsingError
from .processors.google_sheets_parser import GoogleSheetsParser, GoogleSheetsParsingError
from .models import VocabularyEntry, AudioSegment


logger = logging.getLogger(__name__)


class FormatCompatibilityManager:
    """
    Manages format compatibility and provides adaptive processing capabilities.
    
    Handles various audio formats, document formats, and provides quality
    tolerance mechanisms for robust processing.
    """
    
    # Extended format support
    AUDIO_FORMATS = {
        '.wav': {'priority': 1, 'quality': 'excellent'},
        '.flac': {'priority': 2, 'quality': 'excellent'},
        '.mp3': {'priority': 3, 'quality': 'good'},
        '.m4a': {'priority': 4, 'quality': 'good'},
        '.aac': {'priority': 5, 'quality': 'good'},
        '.ogg': {'priority': 6, 'quality': 'fair'},
        '.wma': {'priority': 7, 'quality': 'fair'},
        '.aiff': {'priority': 8, 'quality': 'good'},
        '.au': {'priority': 9, 'quality': 'fair'}
    }
    
    DOCUMENT_FORMATS = {
        'google_docs': {'pattern': r'docs\.google\.com/document', 'parser': 'GoogleDocsParser'},
        'google_sheets': {'pattern': r'docs\.google\.com/spreadsheets', 'parser': 'GoogleSheetsParser'},
        'google_forms': {'pattern': r'docs\.google\.com/forms', 'parser': 'GoogleSheetsParser'}
    }
    
    def __init__(self):
        """Initialize the format compatibility manager."""
        self.audio_loader = AudioLoader()
        self.quality_tolerance = QualityToleranceManager()
        self.format_adapter = FormatAdapter()
    
    def detect_audio_format(self, file_path: str) -> Dict[str, Any]:
        """
        Detect and analyze audio file format with compatibility assessment.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Dictionary with format information and compatibility details
        """
        path = Path(file_path)
        
        if not path.exists():
            return {
                'format': 'unknown',
                'supported': False,
                'error': 'File not found',
                'suggestions': ['Check file path', 'Ensure file exists']
            }
        
        file_extension = path.suffix.lower()
        
        # Check if format is directly supported
        if file_extension in self.AUDIO_FORMATS:
            format_info = self.AUDIO_FORMATS[file_extension]
            
            try:
                # Get detailed audio information
                audio_info = self.audio_loader.get_audio_info(str(path))
                
                return {
                    'format': file_extension,
                    'supported': True,
                    'quality': format_info['quality'],
                    'priority': format_info['priority'],
                    'audio_info': audio_info,
                    'recommendations': self._get_audio_recommendations(audio_info, format_info)
                }
                
            except AudioValidationError as e:
                return {
                    'format': file_extension,
                    'supported': False,
                    'error': str(e),
                    'suggestions': self._get_audio_error_suggestions(str(e))
                }
        
        # Handle unsupported formats
        return {
            'format': file_extension,
            'supported': False,
            'error': f'Unsupported audio format: {file_extension}',
            'suggestions': self._get_format_conversion_suggestions(file_extension)
        }
    
    def detect_document_format(self, doc_url: str) -> Dict[str, Any]:
        """
        Detect and analyze document format with parser selection.
        
        Args:
            doc_url: Document URL
            
        Returns:
            Dictionary with format information and parser details
        """
        try:
            parsed_url = urlparse(doc_url)
            
            # Check each supported document format
            for format_name, format_info in self.DOCUMENT_FORMATS.items():
                if re.search(format_info['pattern'], doc_url):
                    return {
                        'format': format_name,
                        'supported': True,
                        'parser': format_info['parser'],
                        'url_info': {
                            'domain': parsed_url.netloc,
                            'path': parsed_url.path,
                            'query': dict(parse_qs(parsed_url.query))
                        },
                        'recommendations': self._get_document_recommendations(format_name)
                    }
            
            # Unsupported document format
            return {
                'format': 'unknown',
                'supported': False,
                'error': 'Unsupported document format',
                'suggestions': [
                    'Use Google Docs or Google Sheets',
                    'Ensure the URL is publicly accessible or shared with your account',
                    'Check that the URL is complete and correct'
                ]
            }
            
        except Exception as e:
            return {
                'format': 'invalid',
                'supported': False,
                'error': f'Invalid URL format: {e}',
                'suggestions': [
                    'Check URL syntax',
                    'Ensure URL starts with https://',
                    'Copy URL directly from browser'
                ]
            }
    
    def adapt_audio_processing(self, file_path: str, target_quality: str = 'good') -> Dict[str, Any]:
        """
        Adapt audio processing parameters based on file format and quality.
        
        Args:
            file_path: Path to audio file
            target_quality: Target quality level ('excellent', 'good', 'fair')
            
        Returns:
            Dictionary with adapted processing parameters
        """
        format_info = self.detect_audio_format(file_path)
        
        if not format_info['supported']:
            return {
                'success': False,
                'error': format_info['error'],
                'suggestions': format_info['suggestions']
            }
        
        # Get base processing parameters
        processing_params = self._get_base_processing_params()
        
        # Adapt based on format quality
        format_quality = format_info['quality']
        audio_info = format_info.get('audio_info', {})
        
        # Adjust parameters based on format and quality
        adapted_params = self.quality_tolerance.adapt_processing_params(
            processing_params, format_quality, target_quality, audio_info
        )
        
        return {
            'success': True,
            'format_info': format_info,
            'processing_params': adapted_params,
            'quality_adaptations': self._describe_quality_adaptations(adapted_params, processing_params)
        }
    
    def adapt_document_processing(self, doc_url: str) -> Dict[str, Any]:
        """
        Adapt document processing based on format and structure.
        
        Args:
            doc_url: Document URL
            
        Returns:
            Dictionary with adapted processing configuration
        """
        format_info = self.detect_document_format(doc_url)
        
        if not format_info['supported']:
            return {
                'success': False,
                'error': format_info['error'],
                'suggestions': format_info['suggestions']
            }
        
        # Select appropriate parser
        parser_class = format_info['parser']
        
        # Get format-specific processing parameters
        processing_config = self._get_document_processing_config(format_info['format'])
        
        return {
            'success': True,
            'format_info': format_info,
            'parser_class': parser_class,
            'processing_config': processing_config
        }
    
    def _get_audio_recommendations(self, audio_info: Dict[str, Any], format_info: Dict[str, Any]) -> List[str]:
        """Generate recommendations for audio processing."""
        recommendations = []
        
        # Duration recommendations
        duration = audio_info.get('duration', 0)
        if duration < 10:
            recommendations.append("Audio is very short - ensure it contains all vocabulary words")
        elif duration > 300:  # 5 minutes
            recommendations.append("Audio is long - consider splitting into smaller segments")
        
        # Sample rate recommendations
        sample_rate = audio_info.get('sample_rate', 0)
        if sample_rate < 16000:
            recommendations.append("Low sample rate detected - audio quality may be reduced")
        elif sample_rate > 48000:
            recommendations.append("High sample rate - processing may be slower but quality excellent")
        
        # Format-specific recommendations
        if format_info['quality'] == 'fair':
            recommendations.append("Consider converting to WAV or FLAC for better quality")
        
        return recommendations
    
    def _get_audio_error_suggestions(self, error_message: str) -> List[str]:
        """Generate suggestions based on audio error."""
        error_lower = error_message.lower()
        
        if 'format' in error_lower or 'codec' in error_lower:
            return [
                "Convert audio to WAV format",
                "Use audio conversion software like Audacity",
                "Check if file is corrupted"
            ]
        elif 'duration' in error_lower or 'short' in error_lower:
            return [
                "Ensure audio contains speech content",
                "Check that file is not truncated",
                "Record audio with longer duration"
            ]
        elif 'silent' in error_lower or 'amplitude' in error_lower:
            return [
                "Increase recording volume",
                "Check microphone settings",
                "Ensure audio contains audible speech"
            ]
        else:
            return [
                "Check file integrity",
                "Try a different audio file",
                "Convert to a standard format (WAV, MP3)"
            ]
    
    def _get_format_conversion_suggestions(self, file_extension: str) -> List[str]:
        """Generate format conversion suggestions."""
        return [
            f"Convert {file_extension} to WAV format",
            "Use audio conversion software (Audacity, FFmpeg, online converters)",
            "Supported formats: WAV, MP3, M4A, FLAC, OGG",
            "WAV format provides best compatibility and quality"
        ]
    
    def _get_document_recommendations(self, format_name: str) -> List[str]:
        """Generate recommendations for document processing."""
        if format_name == 'google_docs':
            return [
                "Ensure document contains a clear table structure",
                "Use simple table formatting without merged cells",
                "Place English in first column, Cantonese in second column"
            ]
        elif format_name == 'google_sheets':
            return [
                "Use first sheet for vocabulary data",
                "Place headers in first row (English, Cantonese)",
                "Avoid empty rows between vocabulary entries"
            ]
        else:
            return [
                "Ensure document is publicly accessible or shared",
                "Use clear table structure with vocabulary pairs"
            ]
    
    def _get_base_processing_params(self) -> Dict[str, Any]:
        """Get base audio processing parameters."""
        return {
            'sample_rate': 22050,
            'hop_length': 512,
            'n_fft': 2048,
            'win_length': 2048,
            'window': 'hann',
            'center': True,
            'pad_mode': 'reflect',
            'power': 2.0,
            'n_mels': 128,
            'fmin': 0.0,
            'fmax': None,
            'htk': False,
            'norm': 'slaney',
            'dtype': np.float32
        }
    
    def _describe_quality_adaptations(self, adapted_params: Dict[str, Any], 
                                    base_params: Dict[str, Any]) -> List[str]:
        """Describe what quality adaptations were made."""
        adaptations = []
        
        for key, adapted_value in adapted_params.items():
            base_value = base_params.get(key)
            if base_value != adapted_value:
                adaptations.append(f"Adjusted {key}: {base_value} → {adapted_value}")
        
        return adaptations
    
    def _get_document_processing_config(self, format_name: str) -> Dict[str, Any]:
        """Get format-specific document processing configuration."""
        base_config = {
            'max_retries': 3,
            'timeout': 30,
            'min_confidence': 0.5,
            'skip_empty_rows': True,
            'normalize_text': True
        }
        
        if format_name == 'google_sheets':
            base_config.update({
                'sheet_index': 0,
                'header_row': 0,
                'data_start_row': 1,
                'auto_detect_columns': True
            })
        elif format_name == 'google_docs':
            base_config.update({
                'table_detection_threshold': 0.3,
                'merge_adjacent_cells': True,
                'handle_formatting_variations': True
            })
        
        return base_config
    
    def validate_format_compatibility(self, audio_path: str, doc_url: str) -> Dict[str, Any]:
        """
        Validate format compatibility between audio and document.
        
        Args:
            audio_path: Path to audio file
            doc_url: Document URL
            
        Returns:
            Dictionary with compatibility assessment
        """
        compatibility = {
            'audio_compatible': False,
            'document_compatible': False,
            'overall_compatible': False,
            'issues': [],
            'warnings': []
        }
        
        # Check audio compatibility
        try:
            audio_format = self.detect_audio_format(audio_path)
            
            if audio_format['supported']:
                compatibility['audio_compatible'] = True
                if audio_format['quality'] == 'fair':
                    compatibility['warnings'].append("Audio quality is fair - results may vary")
            else:
                compatibility['issues'].append(f"Audio format issue: {audio_format['error']}")
                
        except Exception as e:
            compatibility['issues'].append(f"Audio validation failed: {e}")
        
        # Check document compatibility
        try:
            doc_format = self.detect_document_format(doc_url)
            
            if doc_format['supported']:
                compatibility['document_compatible'] = True
            else:
                compatibility['issues'].append(f"Document format issue: {doc_format['error']}")
                
        except Exception as e:
            compatibility['issues'].append(f"Document validation failed: {e}")
        
        # Overall compatibility
        compatibility['overall_compatible'] = (
            compatibility['audio_compatible'] and 
            compatibility['document_compatible']
        )
        
        return compatibility


class QualityToleranceManager:
    """
    Manages quality tolerance and adaptation mechanisms for robust processing.
    """
    
    def __init__(self):
        """Initialize quality tolerance manager."""
        self.quality_thresholds = {
            'excellent': {'min_sample_rate': 44100, 'min_duration': 5, 'max_noise_ratio': 0.1},
            'good': {'min_sample_rate': 22050, 'min_duration': 2, 'max_noise_ratio': 0.2},
            'fair': {'min_sample_rate': 16000, 'min_duration': 1, 'max_noise_ratio': 0.3}
        }
    
    def adapt_processing_params(self, base_params: Dict[str, Any], 
                              source_quality: str, target_quality: str,
                              audio_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt processing parameters based on quality levels.
        
        Args:
            base_params: Base processing parameters
            source_quality: Source audio quality level
            target_quality: Target quality level
            audio_info: Audio file information
            
        Returns:
            Adapted processing parameters
        """
        adapted_params = base_params.copy()
        
        # Adjust sample rate based on source quality
        source_sample_rate = audio_info.get('sample_rate', 22050)
        
        if source_quality == 'fair' or source_sample_rate < 22050:
            # Use lower processing sample rate for fair quality sources
            adapted_params['sample_rate'] = min(16000, source_sample_rate)
            adapted_params['hop_length'] = 256
            adapted_params['n_fft'] = 1024
            adapted_params['win_length'] = 1024
        elif source_quality == 'excellent' and target_quality == 'excellent':
            # Use higher quality parameters for excellent sources
            adapted_params['sample_rate'] = min(44100, source_sample_rate)
            adapted_params['hop_length'] = 1024
            adapted_params['n_fft'] = 4096
            adapted_params['win_length'] = 4096
        
        # Adjust spectral parameters based on duration
        duration = audio_info.get('duration', 0)
        if duration < 30:  # Short audio
            adapted_params['n_mels'] = 64  # Reduce spectral resolution
        elif duration > 300:  # Long audio
            adapted_params['n_mels'] = 256  # Increase spectral resolution
        
        return adapted_params
    
    def assess_audio_quality(self, audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """
        Assess audio quality and provide quality metrics.
        
        Args:
            audio_data: Audio data array
            sample_rate: Sample rate
            
        Returns:
            Dictionary with quality assessment
        """
        duration = len(audio_data) / sample_rate
        
        # Calculate basic quality metrics
        rms_energy = np.sqrt(np.mean(audio_data ** 2))
        peak_amplitude = np.max(np.abs(audio_data))
        dynamic_range = 20 * np.log10(peak_amplitude / (rms_energy + 1e-10))
        
        # Estimate noise level (using quiet segments)
        sorted_audio = np.sort(np.abs(audio_data))
        noise_floor = np.mean(sorted_audio[:len(sorted_audio)//10])  # Bottom 10%
        snr_estimate = 20 * np.log10(rms_energy / (noise_floor + 1e-10))
        
        # Determine quality level
        quality_score = 0
        if sample_rate >= 44100:
            quality_score += 3
        elif sample_rate >= 22050:
            quality_score += 2
        elif sample_rate >= 16000:
            quality_score += 1
        
        if duration >= 5:
            quality_score += 2
        elif duration >= 2:
            quality_score += 1
        
        if snr_estimate >= 20:
            quality_score += 3
        elif snr_estimate >= 10:
            quality_score += 2
        elif snr_estimate >= 5:
            quality_score += 1
        
        # Map score to quality level
        if quality_score >= 7:
            quality_level = 'excellent'
        elif quality_score >= 4:
            quality_level = 'good'
        else:
            quality_level = 'fair'
        
        return {
            'quality_level': quality_level,
            'quality_score': quality_score,
            'duration': duration,
            'sample_rate': sample_rate,
            'rms_energy': rms_energy,
            'peak_amplitude': peak_amplitude,
            'dynamic_range': dynamic_range,
            'snr_estimate': snr_estimate,
            'recommendations': self._get_quality_recommendations(quality_level, {
                'duration': duration,
                'sample_rate': sample_rate,
                'snr_estimate': snr_estimate
            })
        }
    
    def _get_quality_recommendations(self, quality_level: str, metrics: Dict[str, Any]) -> List[str]:
        """Generate quality improvement recommendations."""
        recommendations = []
        
        if quality_level == 'fair':
            if metrics['sample_rate'] < 22050:
                recommendations.append("Consider re-recording at higher sample rate (44.1kHz)")
            if metrics['duration'] < 5:
                recommendations.append("Ensure adequate recording duration")
            if metrics['snr_estimate'] < 10:
                recommendations.append("Reduce background noise during recording")
        
        elif quality_level == 'good':
            recommendations.append("Audio quality is good for processing")
            if metrics['snr_estimate'] < 15:
                recommendations.append("Could benefit from noise reduction")
        
        else:  # excellent
            recommendations.append("Excellent audio quality detected")
        
        return recommendations


class FormatAdapter:
    """
    Provides format adaptation and conversion utilities.
    """
    
    def __init__(self):
        """Initialize format adapter."""
        pass
    
    def suggest_format_improvements(self, audio_path: str, doc_url: str) -> Dict[str, Any]:
        """
        Suggest format improvements for better processing results.
        
        Args:
            audio_path: Path to audio file
            doc_url: Document URL
            
        Returns:
            Dictionary with improvement suggestions
        """
        suggestions = {
            'audio': [],
            'document': [],
            'general': []
        }
        
        # Analyze audio format
        try:
            audio_loader = AudioLoader()
            audio_info = audio_loader.get_audio_info(audio_path)
            
            if audio_info['sample_rate'] < 22050:
                suggestions['audio'].append("Increase sample rate to 44.1kHz for better quality")
            
            if audio_info['duration'] < 10:
                suggestions['audio'].append("Ensure audio contains all vocabulary words clearly")
            
            if Path(audio_path).suffix.lower() not in ['.wav', '.flac']:
                suggestions['audio'].append("Consider using WAV format for best compatibility")
                
        except Exception as e:
            suggestions['audio'].append(f"Audio analysis failed: {e}")
        
        # Analyze document format
        if 'docs.google.com/document' in doc_url:
            suggestions['document'].extend([
                "Google Docs format detected - ensure table structure is clear",
                "Avoid merged cells and complex formatting",
                "Use simple two-column layout (English | Cantonese)"
            ])
        elif 'docs.google.com/spreadsheets' in doc_url:
            suggestions['document'].extend([
                "Google Sheets format detected - optimal for vocabulary data",
                "Use first row for headers (English, Cantonese)",
                "Keep vocabulary data in first sheet"
            ])
        
        # General suggestions
        suggestions['general'].extend([
            "Ensure document is shared with appropriate permissions",
            "Test with a small vocabulary set first",
            "Keep audio and document content synchronized"
        ])
        
        return suggestions
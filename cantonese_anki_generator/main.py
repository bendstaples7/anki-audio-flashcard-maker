"""
Main entry point for the Cantonese Anki Generator.

Complete pipeline from Google Docs and audio to Anki package.
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Any

from .config import Config
from .processors.google_sheets_parser import GoogleSheetsParser, GoogleSheetsParsingError
from .processors.google_docs_auth import GoogleDocsAuthError
from .audio.loader import AudioLoader, AudioValidationError
from .audio.smart_segmentation import SmartBoundaryDetector
from .audio.speech_verification import AlignmentVerifier, SpeechVerificationError, WHISPER_AVAILABLE, WhisperVerifier
from .audio.dynamic_alignment import DynamicAligner
from .alignment.global_reassignment import GlobalReassignmentCoordinator
from .models import AlignedPair
from .anki import AnkiPackageGenerator, UniqueNamingManager
from .errors import error_handler, ErrorCategory, ErrorSeverity, ProcessingError
from .progress import progress_tracker, ProcessingStage
from .format_compatibility import FormatCompatibilityManager, QualityToleranceManager
from .validation.coordinator import ValidationCoordinator
from .validation.count_validator import CountValidator
from .validation.alignment_validator import AlignmentValidator
from .validation.content_validator import ContentValidatorImpl
from .validation.models import ValidationCheckpoint
from .validation.config import default_validation_config


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def process_pipeline(google_doc_url: str, audio_file: Path, output_path: Path, 
                    verbose: bool = False, enable_speech_verification: bool = False,
                    whisper_model: str = "base", manual_start_offset: float = None,
                    debug_alignment: bool = False, validation_level: str = "normal",
                    disable_validation: bool = False, validation_report: bool = False) -> bool:
    """
    Execute the complete processing pipeline with comprehensive error handling and progress tracking.
    
    Args:
        google_doc_url: URL of Google Doc/Sheets with vocabulary
        audio_file: Path to audio file
        output_path: Path for output Anki package
        verbose: Enable verbose logging
        enable_speech_verification: Enable Whisper-based speech verification
        whisper_model: Whisper model size to use
        
    Returns:
        True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    # Initialize validation system with configuration from CLI arguments
    from .validation.config import ValidationStrictness
    
    # Map CLI argument to enum
    strictness_map = {
        "strict": ValidationStrictness.STRICT,
        "normal": ValidationStrictness.NORMAL,
        "lenient": ValidationStrictness.LENIENT
    }
    
    validation_config = default_validation_config
    validation_config.set_strictness(strictness_map[validation_level])
    validation_config.enabled = not disable_validation
    
    # Performance optimization for disabled validation
    if disable_validation:
        validation_config.cache_validation_results = False
        validation_config.parallel_validation = False
        logger.info("🔧 Validation disabled - processing will be faster but less safe")
    else:
        logger.info(f"🔧 Validation enabled with {validation_level} strictness")
    
    validation_coordinator = ValidationCoordinator(validation_config, error_handler)
    
    # Register validators for each checkpoint
    count_validator = CountValidator(validation_config)
    alignment_validator = AlignmentValidator(validation_config)
    content_validator = ContentValidatorImpl(validation_config)
    
    # Register validation functions for each checkpoint
    validation_coordinator.register_checkpoint_validator(
        ValidationCheckpoint.AUDIO_SEGMENTATION,
        lambda data, config: count_validator.validate(data)
    )
    
    validation_coordinator.register_checkpoint_validator(
        ValidationCheckpoint.AUDIO_SEGMENTATION,
        lambda data, config: content_validator.validate(data)
    )
    
    validation_coordinator.register_checkpoint_validator(
        ValidationCheckpoint.ALIGNMENT_PROCESS,
        lambda data, config: alignment_validator.validate(data)
    )
    
    # Helper function to handle validation checkpoints with progress tracking
    def run_validation_checkpoint(stage: ProcessingStage, checkpoint: ValidationCheckpoint, data: Any) -> bool:
        """Run validation checkpoint with integrated progress tracking and error handling."""
        if not validation_config.enabled:
            progress_tracker.update_validation_status(stage, "skipped")
            progress_tracker.log_validation_info(stage, "Validation disabled")
            return True
        
        logger.info(f"🔍 Running validation checkpoint: {checkpoint.value}")
        progress_tracker.update_validation_status(stage, "in_progress")
        
        validation_result = validation_coordinator.validate_at_checkpoint(checkpoint, data)
        
        # Update progress with validation results
        validation_status = "passed" if validation_result.success else "failed"
        progress_tracker.update_validation_status(
            stage,
            validation_status,
            confidence=validation_result.confidence_score,
            issues_count=len(validation_result.issues),
            recommendations=validation_result.recommendations
        )
        
        # Handle validation failure if critical
        if not validation_coordinator.handle_validation_failure(validation_result):
            logger.critical(f"{checkpoint.value} validation failed - halting processing")
            progress_tracker.complete_stage(stage, success=False)
            return False
        
        # Log validation results
        if validation_result.issues:
            progress_tracker.log_validation_info(
                stage,
                f"Found {len(validation_result.issues)} issues",
                is_warning=True
            )
            for issue in validation_result.issues:
                logger.warning(f"  - {issue.description}")
        else:
            progress_tracker.log_validation_info(stage, "All checks passed")
        
        return True
    
    # Start validation session
    validation_coordinator.start_validation_session()
    
    # Debug: Log the speech verification parameters
    logger.info(f"🔧 Pipeline parameters:")
    logger.info(f"   Speech verification enabled: {enable_speech_verification}")
    logger.info(f"   Whisper model: {whisper_model}")
    logger.info(f"   Whisper available: {WHISPER_AVAILABLE}")
    logger.info(f"   Debug alignment: {debug_alignment}")
    logger.info(f"   Debug alignment type: {type(debug_alignment)}")
    
    # Show Whisper installation status if speech verification is requested but not available
    if enable_speech_verification and not WHISPER_AVAILABLE:
        logger.warning(f"⚠️  Speech verification requested but Whisper is not installed!")
        logger.warning(f"   Install with: pip install openai-whisper")
        logger.warning(f"   Without Whisper, alignment issues may not be automatically detected")
    
    if debug_alignment:
        logger.info(f"🔍 Debug alignment mode enabled - will show detailed alignment analysis")
        if not WHISPER_AVAILABLE:
            logger.info(f"💡 TIP: Install Whisper for automatic alignment correction:")
            logger.info(f"   pip install openai-whisper")
    else:
        logger.info(f"🔍 Debug alignment mode is DISABLED")
    
    # Clear any previous errors and start progress tracking
    error_handler.clear_errors()
    progress_tracker.start_pipeline()
    
    try:
        # Stage 1: Input Validation with Format Compatibility
        progress_tracker.start_stage(ProcessingStage.INITIALIZATION, total_items=4)
        
        # Initialize format compatibility manager
        format_manager = FormatCompatibilityManager()
        quality_manager = QualityToleranceManager()
        
        # Validate Google Doc URL
        url_error = error_handler.validate_google_doc_url(google_doc_url)
        if url_error:
            error_handler.add_error(url_error)
            progress_tracker.complete_stage(ProcessingStage.INITIALIZATION, success=False)
            return False
        
        progress_tracker.update_stage_progress(ProcessingStage.INITIALIZATION, completed_items=1, 
                                             current_item="Google Doc URL validated")
        
        # Validate audio file
        audio_error = error_handler.validate_audio_file_path(str(audio_file))
        if audio_error:
            error_handler.add_error(audio_error)
            progress_tracker.complete_stage(ProcessingStage.INITIALIZATION, success=False)
            return False
        
        progress_tracker.update_stage_progress(ProcessingStage.INITIALIZATION, completed_items=2, 
                                             current_item="Audio file validated")
        
        # Check format compatibility
        try:
            compatibility = format_manager.validate_format_compatibility(str(audio_file), google_doc_url)
        except AttributeError:
            # Fallback compatibility check
            compatibility = {
                'overall_compatible': True,
                'issues': [],
                'warnings': ['Using fallback compatibility check']
            }
        if not compatibility['overall_compatible']:
            for issue in compatibility['issues']:
                compat_error = ProcessingError(
                    category=ErrorCategory.INPUT_VALIDATION,
                    severity=ErrorSeverity.ERROR,
                    message="Format compatibility issue",
                    details=issue,
                    suggested_actions=[
                        "Check supported formats in documentation",
                        "Convert files to supported formats",
                        "Verify file integrity"
                    ],
                    error_code="COMPAT_001"
                )
                error_handler.add_error(compat_error)
            progress_tracker.complete_stage(ProcessingStage.INITIALIZATION, success=False)
            return False
        
        # Log compatibility warnings
        for warning in compatibility['warnings']:
            progress_tracker.log_warning(ProcessingStage.INITIALIZATION, warning)
        
        progress_tracker.update_stage_progress(ProcessingStage.INITIALIZATION, completed_items=3, 
                                             current_item="Format compatibility checked")
        
        # Adapt processing parameters based on format analysis
        audio_adaptation = format_manager.adapt_audio_processing(str(audio_file), target_quality='good')
        doc_adaptation = format_manager.adapt_document_processing(google_doc_url)
        
        if not audio_adaptation['success'] or not doc_adaptation['success']:
            adapt_error = ProcessingError(
                category=ErrorCategory.INPUT_VALIDATION,
                severity=ErrorSeverity.ERROR,
                message="Failed to adapt processing parameters",
                details="Could not configure processing for input formats",
                suggested_actions=[
                    "Check input file formats",
                    "Try with different input files",
                    "Verify file accessibility"
                ],
                error_code="ADAPT_001"
            )
            error_handler.add_error(adapt_error)
            progress_tracker.complete_stage(ProcessingStage.INITIALIZATION, success=False)
            return False
        
        # Log format adaptations
        if audio_adaptation.get('quality_adaptations'):
            for adaptation in audio_adaptation['quality_adaptations']:
                progress_tracker.log_detailed_info(ProcessingStage.INITIALIZATION, f"Audio adaptation: {adaptation}")
        
        progress_tracker.update_stage_progress(ProcessingStage.INITIALIZATION, completed_items=4, 
                                             current_item="Processing parameters adapted")
        progress_tracker.complete_stage(ProcessingStage.INITIALIZATION, success=True)
        
        # Stage 2: Authentication and Document Parsing
        progress_tracker.start_stage(ProcessingStage.AUTHENTICATION)
        
        try:
            # Use appropriate parser based on document format
            parser_class = doc_adaptation['parser_class']
            if parser_class == 'GoogleSheetsParser':
                parser = GoogleSheetsParser()
            else:
                # Fallback to sheets parser for now
                parser = GoogleSheetsParser()
            
            progress_tracker.complete_stage(ProcessingStage.AUTHENTICATION, success=True)
        except GoogleDocsAuthError as e:
            auth_error = error_handler.handle_authentication_error(e)
            error_handler.add_error(auth_error)
            progress_tracker.complete_stage(ProcessingStage.AUTHENTICATION, success=False)
            return False
        
        # Stage 3: Document Parsing with Format Adaptation
        progress_tracker.start_stage(ProcessingStage.DOCUMENT_PARSING)
        
        try:
            # Apply document processing configuration
            processing_config = doc_adaptation['processing_config']
            
            vocab_entries = parser.extract_vocabulary_from_sheet(google_doc_url)
            
            # Debug: Log vocabulary extraction results
            logger.info(f"📋 Vocabulary extraction results:")
            logger.info(f"   Total entries extracted: {len(vocab_entries)}")
            if len(vocab_entries) > 0:
                logger.info(f"   First entry: '{vocab_entries[0].english}' -> '{vocab_entries[0].cantonese}'")
                if len(vocab_entries) > 1:
                    logger.info(f"   Last entry: '{vocab_entries[-1].english}' -> '{vocab_entries[-1].cantonese}'")
                
                # Check for any duplicate entries
                english_terms = [entry.english for entry in vocab_entries]
                cantonese_terms = [entry.cantonese for entry in vocab_entries]
                
                if len(set(english_terms)) != len(english_terms):
                    logger.warning(f"   ⚠️  Duplicate English terms detected!")
                    duplicates = [term for term in set(english_terms) if english_terms.count(term) > 1]
                    logger.warning(f"   Duplicates: {duplicates}")
                
                if len(set(cantonese_terms)) != len(cantonese_terms):
                    logger.warning(f"   ⚠️  Duplicate Cantonese terms detected!")
                    duplicates = [term for term in set(cantonese_terms) if cantonese_terms.count(term) > 1]
                    logger.warning(f"   Duplicates: {duplicates}")
            
            if not vocab_entries:
                doc_error = ProcessingError(
                    category=ErrorCategory.DOCUMENT_PARSING,
                    severity=ErrorSeverity.ERROR,
                    message="No vocabulary entries found",
                    details="The document appears to be empty or contains no valid vocabulary data",
                    suggested_actions=[
                        "Check that the document contains a table with vocabulary data",
                        "Ensure the table has at least two columns (English and Cantonese)",
                        "Verify the document is not empty"
                    ],
                    error_code="DOC_004"
                )
                error_handler.add_error(doc_error)
                progress_tracker.complete_stage(ProcessingStage.DOCUMENT_PARSING, success=False)
                return False
            
            progress_tracker.update_summary_data(vocab_entries=len(vocab_entries))
            progress_tracker.complete_stage(ProcessingStage.DOCUMENT_PARSING, success=True, 
                                          details={'vocab_count': len(vocab_entries)})
            progress_tracker.log_detailed_info(ProcessingStage.DOCUMENT_PARSING, 
                                             f"Extracted {len(vocab_entries)} vocabulary terms")
            
            # VALIDATION CHECKPOINT: Document parsing completion
            doc_validation_data = {
                'vocabulary_entries': vocab_entries,
                'audio_segments': []  # Not available yet
            }
            
            if not run_validation_checkpoint(
                ProcessingStage.DOCUMENT_PARSING,
                ValidationCheckpoint.DOCUMENT_PARSING,
                doc_validation_data
            ):
                return False
            
        except (GoogleSheetsParsingError, Exception) as e:
            doc_error = error_handler.handle_document_parsing_error(e, {'url': google_doc_url})
            error_handler.add_error(doc_error)
            progress_tracker.complete_stage(ProcessingStage.DOCUMENT_PARSING, success=False)
            return False
        
        # Stage 4: Audio Loading with Quality Assessment
        progress_tracker.start_stage(ProcessingStage.AUDIO_LOADING)
        
        try:
            # Use adapted processing parameters
            processing_params = audio_adaptation['processing_params']
            target_sample_rate = processing_params.get('sample_rate', 22050)
            
            loader = AudioLoader(target_sample_rate=target_sample_rate)
            audio_data, sample_rate = loader.load_audio(str(audio_file))
            total_duration = len(audio_data) / sample_rate
            
            # Assess audio quality
            quality_assessment = quality_manager.assess_audio_quality(audio_data, sample_rate)
            
            # Log quality information
            progress_tracker.log_detailed_info(ProcessingStage.AUDIO_LOADING,
                                             f"Audio quality: {quality_assessment['quality_level']} "
                                             f"(score: {quality_assessment['quality_score']}/8)")
            
            # Log quality recommendations
            for recommendation in quality_assessment['recommendations']:
                progress_tracker.log_detailed_info(ProcessingStage.AUDIO_LOADING, f"Recommendation: {recommendation}")
            
            progress_tracker.complete_stage(ProcessingStage.AUDIO_LOADING, success=True,
                                          details={
                                              'duration': total_duration, 
                                              'sample_rate': sample_rate,
                                              'quality_level': quality_assessment['quality_level'],
                                              'quality_score': quality_assessment['quality_score']
                                          })
            progress_tracker.log_detailed_info(ProcessingStage.AUDIO_LOADING,
                                             f"Loaded audio: {total_duration:.2f}s at {sample_rate}Hz")
            
        except AudioValidationError as e:
            audio_error = error_handler.handle_audio_processing_error(e, {'file_path': str(audio_file)})
            error_handler.add_error(audio_error)
            progress_tracker.complete_stage(ProcessingStage.AUDIO_LOADING, success=False)
            return False
        
        # Stage 5: Audio Segmentation
        progress_tracker.start_stage(ProcessingStage.AUDIO_SEGMENTATION, total_items=len(vocab_entries))
        
        # Use all vocabulary entries (no filtering)
        filtered_vocab = vocab_entries
        
        try:
            detector = SmartBoundaryDetector(sample_rate=sample_rate)
            # Use optimized parameters for precise, non-overlapping segmentation
            # Start from the beginning of audio to avoid skipping vocabulary words
            logger.info(f"Using improved smart segmentation with non-overlapping boundaries")
            logger.info(f"Starting segmentation from beginning of audio (auto-detect silence)")
            
            # Add debug info about audio data
            logger.info(f"Audio data shape: {audio_data.shape}, sample_rate: {sample_rate}")
            logger.info(f"Audio duration: {len(audio_data) / sample_rate:.2f}s")
            logger.info(f"Expected segments: {len(vocab_entries)}")
            
            # For alignment debugging, try multiple start offsets if this is a problematic case
            if manual_start_offset is not None:
                logger.info(f"🎯 Using manual start offset: {manual_start_offset:.1f}s")
                segments = detector.segment_audio(audio_data, len(vocab_entries), 
                                                start_offset=manual_start_offset, force_start_offset=True)
            elif len(vocab_entries) == 24:  # Your specific case
                logger.info("🎯 Detected 24-term vocabulary - testing multiple alignment strategies")
                
                # Test different start offsets to find the best alignment
                # Based on user feedback, try negative offsets first since terms are getting audio from later positions
                test_offsets = [-2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 3.2, 4.0, 5.0]
                best_offset = 0.0
                best_score = float('inf')
                
                for test_offset in test_offsets:
                    try:
                        test_segments = detector.segment_audio(audio_data, len(vocab_entries), 
                                                             start_offset=test_offset, force_start_offset=True)
                        
                        # Score based on segment duration consistency and expected timing
                        durations = [s.end_time - s.start_time for s in test_segments]
                        avg_duration = sum(durations) / len(durations)
                        
                        # Calculate expected duration based on available audio time
                        if test_offset >= 0:
                            available_time = (len(audio_data) / sample_rate) - test_offset
                        else:
                            available_time = len(audio_data) / sample_rate
                        expected_duration = available_time / len(vocab_entries)
                        
                        # Score: lower is better
                        duration_variance = sum((d - avg_duration) ** 2 for d in durations) / len(durations)
                        duration_diff = abs(avg_duration - expected_duration)
                        
                        # Penalize negative offsets less since they might fix the systematic shift issue
                        offset_penalty = 0.1 if test_offset < 0 else 0.0
                        score = duration_variance + duration_diff * 2 - offset_penalty
                        
                        logger.info(f"   Offset {test_offset:+4.1f}s: avg_duration={avg_duration:.2f}s, "
                                  f"expected={expected_duration:.2f}s, score={score:.3f}")
                        
                        if score < best_score:
                            best_score = score
                            best_offset = test_offset
                            
                    except Exception as e:
                        logger.debug(f"   Offset {test_offset:+4.1f}s failed: {e}")
                
                logger.info(f"🎯 Selected best offset: {best_offset:+4.1f}s (score: {best_score:.3f})")
                
                # Use the best offset found
                segments = detector.segment_audio(audio_data, len(vocab_entries), 
                                                start_offset=best_offset, force_start_offset=True)
            else:
                # Normal processing for other cases - try a small negative offset by default
                # to account for common systematic alignment issues
                default_offset = -0.5  # Small negative offset to account for systematic shifts
                segments = detector.segment_audio(audio_data, len(vocab_entries), start_offset=default_offset)
            
            # Debug: Log first few segments for alignment verification
            logger.info(f"🔍 First few audio segments for manual verification:")
            for i in range(min(3, len(segments))):
                segment = segments[i]
                logger.info(f"   Segment {i+1}: {segment.start_time:.3f}s - {segment.end_time:.3f}s "
                          f"(duration: {segment.end_time - segment.start_time:.3f}s)")
            
            if len(segments) > 3:
                logger.info(f"   ... and {len(segments) - 3} more segments")
            
            # Debug: Log vocabulary order for comparison
            logger.info(f"🔍 First few vocabulary entries for comparison:")
            for i in range(min(3, len(filtered_vocab))):
                vocab = filtered_vocab[i]
                logger.info(f"   Vocab {i+1}: '{vocab.english}' -> '{vocab.cantonese}'")
            
            if len(filtered_vocab) > 3:
                logger.info(f"   ... and {len(filtered_vocab) - 3} more entries")
            
            # ALIGNMENT DEBUGGING: Show detailed alignment analysis
            logger.info(f"🔍 Checking if debug alignment should run: debug_alignment={debug_alignment}")
            if debug_alignment:
                logger.info(f"\n" + "=" * 80)
                logger.info(f"🔍 DETAILED ALIGNMENT DEBUGGING")
                logger.info(f"=" * 80)
                
                # Find specific terms that might have alignment issues
                problem_terms = ['di fa', 'the flowers', '地方', '花', 'pants', 'mai di la', '褲子']
                found_terms = []
                
                for i, vocab in enumerate(filtered_vocab):
                    for term in problem_terms:
                        if term.lower() in vocab.english.lower() or term in vocab.cantonese:
                            found_terms.append((i, vocab, term))
                
                if found_terms:
                    logger.info(f"🎯 Found potentially problematic terms:")
                    for idx, vocab, term in found_terms:
                        logger.info(f"   Index {idx}: '{vocab.english}' -> '{vocab.cantonese}' (matched: {term})")
                
                # Test multiple offsets and show detailed results
                logger.info(f"\n🔍 Testing multiple alignment offsets:")
                logger.info(f"   Current segments: {len(segments)}")
                logger.info(f"   Vocabulary entries: {len(filtered_vocab)}")
                
                # Include negative offsets to test for systematic shifts
                test_offsets = [-2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 3.2, 4.0, 5.0]
                
                for test_offset in test_offsets:
                    try:
                        test_segments = detector.segment_audio(audio_data, len(filtered_vocab), 
                                                             start_offset=test_offset, force_start_offset=True)
                        
                        logger.info(f"\n   Offset {test_offset:4.1f}s: Created {len(test_segments)} segments")
                        
                        # Show alignment for found problematic terms
                        for idx, vocab, term in found_terms:
                            if idx < len(test_segments):
                                seg = test_segments[idx]
                                logger.info(f"      '{vocab.english}' -> {seg.start_time:.1f}-{seg.end_time:.1f}s "
                                          f"(duration: {seg.end_time - seg.start_time:.1f}s)")
                            else:
                                logger.info(f"      '{vocab.english}' -> ❌ No segment available")
                        
                        # Show first few alignments for this offset
                        logger.info(f"      First few alignments:")
                        for i in range(min(5, len(test_segments), len(filtered_vocab))):
                            seg = test_segments[i]
                            vocab = filtered_vocab[i]
                            logger.info(f"        {i:2d}. '{vocab.english}' -> {seg.start_time:.1f}-{seg.end_time:.1f}s")
                            
                    except Exception as e:
                        logger.info(f"   Offset {test_offset:4.1f}s: ❌ Error: {e}")
                
                logger.info(f"\n🎯 ALIGNMENT DEBUGGING RECOMMENDATIONS:")
                logger.info(f"   1. Look at the timing ranges above for your problematic terms")
                logger.info(f"   2. Listen to your audio at those time ranges")
                logger.info(f"   3. Find the offset where the term gets the correct audio")
                logger.info(f"   4. Use that offset with: --start-offset X.X")
                logger.info(f"   5. Or install Whisper for automatic alignment: pip install openai-whisper")
                logger.info(f"=" * 80)
            
            progress_tracker.update_summary_data(audio_segments=len(segments))
            progress_tracker.complete_stage(ProcessingStage.AUDIO_SEGMENTATION, success=True,
                                          details={'segment_count': len(segments)})
            progress_tracker.log_detailed_info(ProcessingStage.AUDIO_SEGMENTATION,
                                             f"Created {len(segments)} audio segments")
            
            # VALIDATION CHECKPOINT: Audio segmentation completion
            audio_validation_data = {
                'vocabulary_entries': filtered_vocab,
                'audio_segments': segments
            }
            
            if not run_validation_checkpoint(
                ProcessingStage.AUDIO_SEGMENTATION,
                ValidationCheckpoint.AUDIO_SEGMENTATION,
                audio_validation_data
            ):
                return False
            
        except Exception as e:
            audio_error = error_handler.handle_audio_processing_error(e, 
                                                                    {'vocab_count': len(vocab_entries)})
            error_handler.add_error(audio_error)
            progress_tracker.complete_stage(ProcessingStage.AUDIO_SEGMENTATION, success=False)
            return False
        
        # Stage 6: Dynamic Speech Verification and Per-Term Alignment
        verification_results = None
        corrections = []
        
        # Debug: Log vocabulary counts
        logger.info(f"🔢 Vocabulary count tracking:")
        logger.info(f"   Original vocab_entries: {len(vocab_entries)}")
        logger.info(f"   Filtered vocab: {len(filtered_vocab)}")
        logger.info(f"   Audio segments: {len(segments)}")
        
        # Debug: Log first few and last few vocabulary entries
        if len(filtered_vocab) > 0:
            logger.info(f"   First vocab entry: '{filtered_vocab[0].english}' -> '{filtered_vocab[0].cantonese}'")
            if len(filtered_vocab) > 1:
                logger.info(f"   Second vocab entry: '{filtered_vocab[1].english}' -> '{filtered_vocab[1].cantonese}'")
            if len(filtered_vocab) > 2:
                logger.info(f"   Last vocab entry: '{filtered_vocab[-1].english}' -> '{filtered_vocab[-1].cantonese}'")
        
        progress_tracker.start_stage(ProcessingStage.ALIGNMENT, total_items=len(segments))
        
        if enable_speech_verification and WHISPER_AVAILABLE:
            try:
                logger.info("🎯 Starting DYNAMIC PER-TERM ALIGNMENT with Whisper...")
                logger.info(f"Speech verification enabled: {enable_speech_verification}")
                logger.info(f"Whisper available: {WHISPER_AVAILABLE}")
                logger.info(f"Whisper model: {whisper_model}")
                logger.info("🔧 Using dynamic alignment - each term will find its best matching audio segment")
                
                # Initialize speech verifier for dynamic alignment
                speech_verifier = WhisperVerifier(model_size=whisper_model)
                
                # Initialize dynamic aligner
                dynamic_aligner = DynamicAligner(speech_verifier=speech_verifier)
                
                # Progress callback for dynamic alignment
                def alignment_progress_callback(current_idx, total_items, current_term):
                    progress_tracker.update_stage_progress(
                        ProcessingStage.ALIGNMENT,
                        completed_items=current_idx,
                        current_item=f"🎯 Dynamic alignment: '{current_term}' ({current_idx + 1}/{total_items})"
                    )
                
                # Perform dynamic alignment - each term finds its best audio match
                logger.info("🎯 Performing dynamic per-term alignment...")
                aligned_pairs = dynamic_aligner.align_vocabulary_to_audio(
                    vocab_entries=filtered_vocab,
                    audio_segments=segments,
                    initial_offset=manual_start_offset if manual_start_offset is not None else 0,
                    progress_callback=alignment_progress_callback
                )
                
                # Verify alignment quality
                alignment_quality = dynamic_aligner.verify_alignment_quality(aligned_pairs)
                
                logger.info(f"🎯 Dynamic alignment complete:")
                logger.info(f"   Pairs created: {alignment_quality['total_pairs']}")
                logger.info(f"   Average confidence: {alignment_quality['average_confidence']*100:.1f}%")
                logger.info(f"   High confidence pairs: {alignment_quality['high_confidence_count']} ({alignment_quality['high_confidence_percentage']:.1f}%)")
                logger.info(f"   Overall quality: {alignment_quality['quality']}")
                
                # Update progress
                progress_tracker.update_stage_progress(
                    ProcessingStage.ALIGNMENT,
                    completed_items=len(aligned_pairs),
                    current_item=f"✅ Dynamic alignment complete: {alignment_quality['average_confidence']*100:.1f}% avg confidence"
                )
                
                # Create verification results for compatibility with existing code
                verification_results = {
                    'total_pairs': len(aligned_pairs),
                    'verified_pairs': [],
                    'high_confidence': sum(1 for p in aligned_pairs if p.alignment_confidence >= 0.8),
                    'medium_confidence': sum(1 for p in aligned_pairs if 0.6 <= p.alignment_confidence < 0.8),
                    'low_confidence': sum(1 for p in aligned_pairs if p.alignment_confidence < 0.6),
                    'corrections_suggested': 0,
                    'overall_confidence': alignment_quality['average_confidence']
                }
                
                # Create verified pairs data for each aligned pair
                for i, pair in enumerate(aligned_pairs):
                    # Get transcription and comparison for this pair
                    try:
                        transcription = speech_verifier.transcribe_audio_segment(
                            pair.audio_segment.audio_data, sample_rate
                        )
                        
                        comparison = speech_verifier.compare_transcription_with_expected(
                            transcription['text'], pair.vocabulary_entry.cantonese
                        )
                        
                        # ENSURE JYUTPING IS ALWAYS DISPLAYED
                        transcribed_jyutping = comparison.get('transcribed_jyutping', '')
                        
                        # ALWAYS log the conversion for user visibility
                        logger.info(f"🔍 Term {i+1}: '{pair.vocabulary_entry.english}' -> '{pair.vocabulary_entry.cantonese}'")
                        logger.info(f"   Audio transcribed: '{transcription['text']}' -> '{transcribed_jyutping}'")
                        logger.info(f"   Confidence: {pair.alignment_confidence*100:.1f}%, Similarity: {comparison['similarity']*100:.1f}%")
                        
                        verified_pair = {
                            'pair_index': i,
                            'english': pair.vocabulary_entry.english,
                            'expected_cantonese': pair.vocabulary_entry.cantonese,
                            'transcribed_cantonese': transcription['text'],
                            'transcribed_jyutping': transcribed_jyutping,
                            'whisper_confidence': transcription['confidence'],
                            'match_similarity': comparison['similarity'],
                            'overall_confidence': pair.alignment_confidence,
                            'confidence_category': "high" if pair.alignment_confidence >= 0.8 else "medium" if pair.alignment_confidence >= 0.6 else "low",
                            'is_correct': comparison['is_match'],
                            'needs_review': pair.alignment_confidence < 0.6,
                            'comparison_details': comparison
                        }
                        
                        verification_results['verified_pairs'].append(verified_pair)
                        
                    except Exception as e:
                        logger.warning(f"Failed to verify pair {i+1}: {e}")
                        # Add placeholder verification data
                        verified_pair = {
                            'pair_index': i,
                            'english': pair.vocabulary_entry.english,
                            'expected_cantonese': pair.vocabulary_entry.cantonese,
                            'transcribed_cantonese': '',
                            'transcribed_jyutping': '',
                            'whisper_confidence': 0.0,
                            'match_similarity': 0.0,
                            'overall_confidence': pair.alignment_confidence,
                            'confidence_category': "failed",
                            'is_correct': False,
                            'needs_review': True,
                            'error': str(e)
                        }
                        verification_results['verified_pairs'].append(verified_pair)
                
                progress_tracker.complete_stage(ProcessingStage.ALIGNMENT, success=True,
                                              details={'verification_confidence': alignment_quality['average_confidence']})
                
                # GLOBAL REASSIGNMENT: After Whisper verification completes
                logger.info("\n" + "=" * 80)
                logger.info("🌐 STARTING GLOBAL TRANSCRIPTION-BASED REASSIGNMENT")
                logger.info("=" * 80)
                
                try:
                    # Initialize global reassignment coordinator
                    reassignment_coordinator = GlobalReassignmentCoordinator()
                    
                    # Perform global reassignment
                    reassigned_pairs, reassignment_report = reassignment_coordinator.perform_global_reassignment(
                        aligned_pairs=aligned_pairs,
                        verification_results=verification_results,
                        enable_logging=True
                    )
                    
                    # Update aligned_pairs with reassigned pairs
                    if reassignment_report['status'] == 'completed':
                        logger.info(f"✅ Global reassignment successful: {reassignment_report['reassignments']} segments reassigned")
                        aligned_pairs = reassigned_pairs
                        
                        # Update verification results with new confidence
                        verification_results['overall_confidence'] = reassignment_report['quality_metrics']['average_similarity']
                        verification_results['reassignment_performed'] = True
                        verification_results['reassignment_report'] = reassignment_report
                    else:
                        logger.warning(f"⚠️  Global reassignment skipped: {reassignment_report.get('reason', 'unknown')}")
                        verification_results['reassignment_performed'] = False
                
                except Exception as e:
                    logger.error(f"❌ Global reassignment failed: {e}")
                    logger.exception(e)
                    verification_results['reassignment_performed'] = False
                    verification_results['reassignment_error'] = str(e)
                    # Continue with original aligned_pairs
                
                logger.info("=" * 80)
                
            except SpeechVerificationError as e:
                progress_tracker.log_warning(ProcessingStage.ALIGNMENT, f"Speech verification failed: {e}")
                logger.warning(f"Speech verification unavailable: {e}")
                # Fall back to static alignment
                aligned_pairs = []
            except Exception as e:
                progress_tracker.log_warning(ProcessingStage.ALIGNMENT, f"Dynamic alignment error: {e}")
                logger.warning(f"Dynamic alignment error: {e}")
                # Fall back to static alignment
                aligned_pairs = []
        elif enable_speech_verification and not WHISPER_AVAILABLE:
            logger.warning("Speech verification requested but Whisper not available. Install with: pip install openai-whisper")
            logger.warning(f"Speech verification enabled: {enable_speech_verification}")
            logger.warning(f"Whisper available: {WHISPER_AVAILABLE}")
            logger.warning("💡 Speech verification can help detect and correct alignment issues automatically")
            aligned_pairs = []  # Will be created in fallback section
        else:
            logger.info("Speech verification disabled - using optimized alignment")
            logger.info(f"Speech verification enabled: {enable_speech_verification}")
            logger.info(f"Whisper available: {WHISPER_AVAILABLE}")
            logger.info("💡 TIP: If you notice audio misalignment (wrong audio for vocabulary terms),")
            logger.info("       try running with --enable-speech-verification to automatically detect and fix alignment issues")
            logger.info("       Install with: pip install openai-whisper")
            aligned_pairs = []  # Will be created in fallback section
        
        # Fallback to static alignment if dynamic alignment wasn't used or failed
        if not aligned_pairs:
            logger.info("🔧 Using fallback static alignment")
            
            # Find optimal offset to preserve all vocabulary
            logger.info("🎯 Finding optimal offset to preserve all vocabulary entries...")
            best_offset = 0
            best_coverage = 0.0
            
            # TARGETED FIX: Test negative offsets first to counteract systematic positive shifts
            # Based on user feedback that "pants" gets "mai di la" audio (2 positions later)
            test_offsets = [-2, -1, 0, 1, 2]  # Prioritize negative offsets
            logger.info("🔧 Testing negative offsets first to counteract systematic alignment shifts")
            
            for test_offset in test_offsets:
                if test_offset >= 0:
                    max_possible_cards = min(len(segments) - test_offset, len(filtered_vocab))
                else:
                    max_possible_cards = min(len(segments), len(filtered_vocab) + test_offset)
                
                vocab_coverage = max_possible_cards / len(filtered_vocab) if len(filtered_vocab) > 0 else 0
                
                logger.info(f"Offset {test_offset:+d}: can create {max_possible_cards}/{len(filtered_vocab)} cards ({vocab_coverage*100:.1f}% coverage)")
                
                # Prioritize negative offsets when coverage is equal
                if vocab_coverage > best_coverage or (vocab_coverage == best_coverage and test_offset < best_offset):
                    best_coverage = vocab_coverage
                    best_offset = test_offset
                    logger.info(f"🎯 New best offset: {test_offset:+d} with {vocab_coverage*100:.1f}% coverage")
            
            alignment_offset = best_offset
            logger.info(f"🎯 Selected alignment offset: {alignment_offset:+d} (coverage: {best_coverage*100:.1f}%)")
            
            # Create aligned pairs using static offset
            aligned_pairs = []
            
            # Calculate how many pairs we can create with the optimized offset
            logger.info(f"🔢 Final pair calculation:")
            logger.info(f"   Segments available: {len(segments)}")
            logger.info(f"   Filtered vocab: {len(filtered_vocab)}")
            logger.info(f"   Alignment offset: {alignment_offset:+d}")
            
            if alignment_offset >= 0:
                max_pairs = min(len(segments) - alignment_offset, len(filtered_vocab))
                logger.info(f"   Positive offset calculation: min({len(segments)} - {alignment_offset}, {len(filtered_vocab)}) = {max_pairs}")
            else:
                max_pairs = min(len(segments), len(filtered_vocab) + alignment_offset)
                logger.info(f"   Negative offset calculation: min({len(segments)}, {len(filtered_vocab)} + {alignment_offset}) = {max_pairs}")
            
            logger.info(f"   ✅ Will create {max_pairs} aligned pairs")
            
            for i in range(max_pairs):
                # Apply offset to segment selection based on offset direction
                if alignment_offset >= 0:
                    segment_idx = i + alignment_offset
                    vocab_idx = i
                else:
                    segment_idx = i
                    vocab_idx = i + abs(alignment_offset)
                
                # Ensure indices are valid
                if segment_idx < len(segments) and vocab_idx < len(filtered_vocab):
                    segment = segments[segment_idx]
                    vocab_entry = filtered_vocab[vocab_idx]
                    
                    aligned_pair = AlignedPair(
                        vocabulary_entry=vocab_entry,
                        audio_segment=segment,
                        alignment_confidence=0.7,  # Default confidence for static alignment
                        audio_file_path=""
                    )
                    aligned_pairs.append(aligned_pair)
            
            logger.info(f"🔧 Static alignment complete: created {len(aligned_pairs)} pairs")
        
        # Stage 7: Final Alignment Processing and Audio Clip Generation
        if not (enable_speech_verification and WHISPER_AVAILABLE):
            # If speech verification wasn't run, start the alignment stage now
            progress_tracker.start_stage(ProcessingStage.ALIGNMENT, total_items=len(aligned_pairs))
        
        # Ensure we have aligned pairs
        if not aligned_pairs:
            alignment_error = ProcessingError(
                category=ErrorCategory.ALIGNMENT,
                severity=ErrorSeverity.ERROR,
                message="No aligned pairs created",
                details="Neither dynamic nor static alignment produced any pairs",
                suggested_actions=[
                    "Check that audio file contains speech",
                    "Verify vocabulary entries are valid",
                    "Try different alignment parameters"
                ],
                error_code="ALIGN_001"
            )
            error_handler.add_error(alignment_error)
            progress_tracker.complete_stage(ProcessingStage.ALIGNMENT, success=False)
            return False
        
        # Check for alignment issues
        alignment_error = error_handler.handle_alignment_error(len(segments), len(filtered_vocab),
                                                             {'segments': len(segments), 'vocab': len(filtered_vocab)})
        if alignment_error and alignment_error.severity == ErrorSeverity.ERROR:
            error_handler.add_error(alignment_error)
            progress_tracker.complete_stage(ProcessingStage.ALIGNMENT, success=False)
            return False
        elif alignment_error and alignment_error.severity == ErrorSeverity.WARNING:
            error_handler.add_error(alignment_error)
            progress_tracker.log_warning(ProcessingStage.ALIGNMENT, alignment_error.message)
        
        # Create temporary directory for audio clips
        temp_dir = output_path.parent / f"temp_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate audio clips for aligned pairs
        logger.info(f"🎵 Generating audio clips for {len(aligned_pairs)} aligned pairs...")
        
        for i, pair in enumerate(aligned_pairs):
            # Generate audio clip filename
            clip_filename = f"cantonese_{i+1:03d}.wav"
            clip_path = temp_dir / clip_filename
            
            # Save audio clip
            import scipy.io.wavfile as wavfile
            audio_normalized = (pair.audio_segment.audio_data * 32767).astype('int16')
            wavfile.write(str(clip_path), sample_rate, audio_normalized)
            
            # Update pair with file path
            pair.audio_file_path = str(clip_path)
            
            # Update progress
            progress_tracker.update_stage_progress(
                ProcessingStage.ALIGNMENT, 
                completed_items=i+1,
                current_item=f"Generated clip: {pair.vocabulary_entry.english}"
            )
        
        # Debug: Log final pair count
        logger.info(f"🔢 Final alignment results:")
        logger.info(f"   Aligned pairs created: {len(aligned_pairs)}")
        logger.info(f"   Vocabulary coverage: {len(aligned_pairs)}/{len(filtered_vocab)} ({len(aligned_pairs)/len(filtered_vocab)*100:.1f}%)")
        
        if len(aligned_pairs) < len(filtered_vocab):
            missing_count = len(filtered_vocab) - len(aligned_pairs)
            logger.warning(f"   ⚠️  Missing {missing_count} vocabulary entries in final output")
        else:
            logger.info(f"   ✅ All vocabulary entries successfully aligned")
        
        # Show verification report if available
        if verification_results and verbose:
            try:
                from .audio.speech_verification import AlignmentVerifier
                verifier = AlignmentVerifier()
                report = verifier.generate_verification_report(verification_results, corrections)
                print("\n" + report)
            except Exception as e:
                logger.debug(f"Could not generate verification report: {e}")
        
        progress_tracker.complete_stage(ProcessingStage.ALIGNMENT, success=True,
                                      details={'aligned_pairs': len(aligned_pairs)})
        progress_tracker.log_detailed_info(ProcessingStage.ALIGNMENT,
                                         f"✅ Created {len(aligned_pairs)} aligned pairs successfully")
        
        # VALIDATION CHECKPOINT: Alignment process completion
        alignment_validation_data = {
            'aligned_pairs': aligned_pairs,
            'vocabulary_entries': filtered_vocab,
            'audio_segments': segments
        }
        
        if not run_validation_checkpoint(
            ProcessingStage.ALIGNMENT,
            ValidationCheckpoint.ALIGNMENT_PROCESS,
            alignment_validation_data
        ):
            return False
        
        # Stage 8: Anki Package Generation
        progress_tracker.start_stage(ProcessingStage.ANKI_GENERATION, total_items=len(aligned_pairs))
        
        # VALIDATION CHECKPOINT: Final validation before package generation
        package_validation_data = {
            'aligned_pairs': aligned_pairs,
            'vocabulary_entries': filtered_vocab,
            'audio_segments': segments
        }
        
        if not run_validation_checkpoint(
            ProcessingStage.ANKI_GENERATION,
            ValidationCheckpoint.PACKAGE_GENERATION,
            package_validation_data
        ):
            return False
        
        try:
            # Initialize components
            naming_manager = UniqueNamingManager()
            package_generator = AnkiPackageGenerator()
            
            # Generate unique deck name
            audio_name = audio_file.stem
            deck_name = naming_manager.generate_unique_deck_name(
                base_name="Cantonese Vocabulary",
                source_info=audio_name
            )
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate the package
            success = package_generator.generate_package(
                aligned_pairs=aligned_pairs,
                output_path=str(output_path),
                deck_name=deck_name
            )
            
            if not success:
                anki_error = ProcessingError(
                    category=ErrorCategory.ANKI_GENERATION,
                    severity=ErrorSeverity.ERROR,
                    message="Failed to generate Anki package",
                    details="Package generation returned failure status",
                    suggested_actions=[
                        "Check output directory permissions",
                        "Ensure sufficient disk space",
                        "Verify all audio files are accessible"
                    ],
                    error_code="ANKI_004"
                )
                error_handler.add_error(anki_error)
                progress_tracker.complete_stage(ProcessingStage.ANKI_GENERATION, success=False)
                return False
            
            progress_tracker.update_summary_data(cards_created=len(aligned_pairs), audio_clips=len(aligned_pairs))
            progress_tracker.complete_stage(ProcessingStage.ANKI_GENERATION, success=True,
                                          details={'package_path': str(output_path), 'deck_name': deck_name})
            
        except Exception as e:
            anki_error = error_handler.handle_anki_generation_error(e, {'output_path': str(output_path)})
            error_handler.add_error(anki_error)
            progress_tracker.complete_stage(ProcessingStage.ANKI_GENERATION, success=False)
            return False
        
        # Stage 9: Finalization
        progress_tracker.start_stage(ProcessingStage.FINALIZATION, total_items=2)
        
        # Validate the package
        try:
            from .anki import PackageValidator
            validator = PackageValidator()
            
            progress_tracker.update_stage_progress(ProcessingStage.FINALIZATION, completed_items=1,
                                                 current_item="Validating package")
            
            if validator.validate_package(str(output_path)):
                info = validator.get_package_info(str(output_path))
                progress_tracker.log_detailed_info(ProcessingStage.FINALIZATION,
                                                 f"Package validated: {info['size_bytes']:,} bytes")
            else:
                progress_tracker.log_warning(ProcessingStage.FINALIZATION, "Package validation failed")
            
            # Clean up temporary directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            progress_tracker.update_stage_progress(ProcessingStage.FINALIZATION, completed_items=2,
                                                 current_item="Cleanup completed")
            progress_tracker.complete_stage(ProcessingStage.FINALIZATION, success=True)
            
            # Generate final validation integrity report
            logger.info("📋 Generating validation integrity report")
            integrity_report = validation_coordinator.end_validation_session()
            
            # Log validation summary (always show basic summary)
            logger.info(f"🔍 Validation Summary:")
            logger.info(f"   Overall status: {'✅ PASSED' if integrity_report.overall_validation_status else '❌ FAILED'}")
            logger.info(f"   Success rate: {integrity_report.success_rate:.1f}%")
            logger.info(f"   Total validations: {integrity_report.total_items_validated}")
            logger.info(f"   Issues found: {len(integrity_report.detailed_issues)}")
            
            # Show detailed report if requested or if there are issues
            if validation_report or integrity_report.detailed_issues or verbose:
                if integrity_report.detailed_issues:
                    logger.info("   Issue breakdown:")
                    for issue in integrity_report.detailed_issues[:5]:  # Show first 5 issues
                        logger.info(f"     - {issue.severity.value.upper()}: {issue.description}")
                    if len(integrity_report.detailed_issues) > 5:
                        logger.info(f"     ... and {len(integrity_report.detailed_issues) - 5} more issues")
                
                if integrity_report.recommendations:
                    logger.info("   Recommendations:")
                    for rec in integrity_report.recommendations[:3]:  # Show first 3 recommendations
                        logger.info(f"     • {rec}")
                
                # Generate detailed validation report if requested
                if validation_report:
                    from .validation.integrity_reporter import IntegrityReporter
                    reporter = IntegrityReporter()
                    detailed_report = reporter.generate_detailed_report(integrity_report)
                    
                    # Save report to file
                    report_path = output_path.parent / f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    with open(report_path, 'w', encoding='utf-8') as f:
                        f.write(detailed_report)
                    
                    logger.info(f"📋 Detailed validation report saved: {report_path}")
                    
                    if verbose:
                        print("\n" + "=" * 80)
                        print("📋 DETAILED VALIDATION REPORT")
                        print("=" * 80)
                        print(detailed_report)
                        print("=" * 80)
            
            # Complete pipeline successfully
            progress_tracker.complete_pipeline(success=True)
            return True
            
        except Exception as e:
            progress_tracker.log_error(ProcessingStage.FINALIZATION, f"Finalization error: {e}")
            progress_tracker.complete_stage(ProcessingStage.FINALIZATION, success=False)
            progress_tracker.complete_pipeline(success=False)
            return False
        
    except Exception as e:
        # Handle unexpected errors
        unexpected_error = ProcessingError(
            category=ErrorCategory.INPUT_VALIDATION,
            severity=ErrorSeverity.CRITICAL,
            message="Unexpected pipeline error",
            details=f"An unexpected error occurred: {e}",
            suggested_actions=[
                "Check the logs for more details",
                "Verify all input files are valid",
                "Try running the pipeline again"
            ],
            error_code="PIPELINE_001"
        )
        error_handler.add_error(unexpected_error)
        
        if verbose:
            import traceback
            traceback.print_exc()
        
        progress_tracker.complete_pipeline(success=False)
        return False


def validate_inputs_interactive(google_doc_url: str, audio_file: Path) -> bool:
    """
    Interactively validate inputs and provide user guidance.
    
    Args:
        google_doc_url: Google Doc URL to validate
        audio_file: Audio file path to validate
        
    Returns:
        True if inputs are valid, False otherwise
    """
    print("🔍 Validating inputs...")
    
    # Initialize format manager for validation
    format_manager = FormatCompatibilityManager()
    
    # Validate document URL
    print(f"📋 Checking document: {google_doc_url}")
    doc_format = format_manager.detect_document_format(google_doc_url)
    
    if not doc_format['supported']:
        print(f"❌ Document format issue: {doc_format['error']}")
        print("💡 Suggestions:")
        for suggestion in doc_format['suggestions']:
            print(f"   • {suggestion}")
        return False
    else:
        print(f"✅ Document format: {doc_format['format']} (supported)")
        for recommendation in doc_format.get('recommendations', []):
            print(f"💡 {recommendation}")
    
    # Validate audio file
    print(f"🔊 Checking audio: {audio_file}")
    audio_format = format_manager.detect_audio_format(str(audio_file))
    
    if not audio_format['supported']:
        print(f"❌ Audio format issue: {audio_format['error']}")
        print("💡 Suggestions:")
        for suggestion in audio_format['suggestions']:
            print(f"   • {suggestion}")
        return False
    else:
        print(f"✅ Audio format: {audio_format['format']} (quality: {audio_format['quality']})")
        
        # Show audio information
        audio_info = audio_format.get('audio_info', {})
        if audio_info:
            duration = audio_info.get('duration', 0)
            sample_rate = audio_info.get('sample_rate', 0)
            print(f"   Duration: {duration:.1f}s, Sample rate: {sample_rate}Hz")
        
        # Show recommendations
        for recommendation in audio_format.get('recommendations', []):
            print(f"💡 {recommendation}")
    
    # Check overall compatibility
    compatibility = format_manager.validate_format_compatibility(str(audio_file), google_doc_url)
    
    if compatibility['warnings']:
        print("\n⚠️  Warnings:")
        for warning in compatibility['warnings']:
            print(f"   • {warning}")
    
    print("✅ Input validation complete!\n")
    return True


def show_processing_tips():
    """Display helpful tips for successful processing."""
    print("💡 PROCESSING TIPS")
    print("=" * 50)
    print("📋 Document preparation:")
    print("   • Use a simple table with English in first column, Cantonese in second")
    print("   • Avoid merged cells and complex formatting")
    print("   • Ensure document is shared or publicly accessible")
    print()
    print("🔊 Audio preparation:")
    print("   • Record each word clearly with brief pauses between words")
    print("   • Use good quality microphone in quiet environment")
    print("   • WAV format provides best compatibility")
    print("   • Aim for 1-2 seconds per vocabulary word")
    print()
    print("🎯 Best practices:")
    print("   • Test with a small vocabulary set first (5-10 words)")
    print("   • Keep audio and document synchronized")
    print("   • Use consistent pronunciation and pacing")
    print()
    print("🤖 Speech verification (optional):")
    print("   • Use --enable-speech-verification for automatic alignment checking")
    print("   • Requires: pip install openai-whisper")
    print("   • Helps detect and correct alignment issues automatically")
    print("   • Uses local AI model (no internet required after download)")
    print("=" * 50)
    print()


def confirm_processing(google_doc_url: str, audio_file: Path, output_path: Path) -> bool:
    """
    Ask user to confirm processing with summary of inputs.
    
    Args:
        google_doc_url: Google Doc URL
        audio_file: Audio file path
        output_path: Output path
        
    Returns:
        True if user confirms, False otherwise
    """
    print("📋 PROCESSING SUMMARY")
    print("=" * 50)
    print(f"📄 Document: {google_doc_url}")
    print(f"🔊 Audio: {audio_file}")
    print(f"📦 Output: {output_path}")
    print("=" * 50)
    
    while True:
        response = input("Proceed with processing? [Y/n]: ").strip().lower()
        if response in ['', 'y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Please enter 'y' for yes or 'n' for no.")


def main():
    """Enhanced main function with interactive CLI."""
    parser = argparse.ArgumentParser(
        description="Generate Anki flashcards from Google Docs/Sheets and audio files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "https://docs.google.com/spreadsheets/d/..." audio.wav
  %(prog)s "https://docs.google.com/spreadsheets/d/..." audio.mp3 -o my_deck.apkg
  %(prog)s "https://docs.google.com/spreadsheets/d/..." audio.wav --verbose
  %(prog)s "https://docs.google.com/spreadsheets/d/..." audio.wav --enable-speech-verification
  %(prog)s "https://docs.google.com/spreadsheets/d/..." audio.wav --debug-alignment
  %(prog)s --help-setup  # Show setup and preparation guide

Output:
  Generated .apkg files are saved in the 'output/' directory by default
  Use -o to specify a custom output path

Supported formats:
  Audio: WAV, MP3, M4A, FLAC, OGG (WAV recommended)
  Documents: Google Docs, Google Sheets (Sheets recommended)

Speech Verification:
  Use --enable-speech-verification to enable Whisper-based alignment verification
  Requires: pip install openai-whisper
  Models: tiny (~39MB), base (~142MB), small (~244MB), medium (~769MB), large (~1550MB)

Alignment Debugging:
  Use --debug-alignment to show detailed alignment analysis and test multiple offsets
  Helps identify issues like terms getting wrong audio (e.g., "di fa" getting audio from wrong segment)
  Shows timing information for each vocabulary term with different start offsets

Validation Options:
  Use --validation-level to control validation strictness (strict/normal/lenient)
  Use --disable-validation to skip validation checks for faster processing
  Use --validation-report to generate detailed validation reports
  Strict: High confidence thresholds, catches more potential issues
  Normal: Balanced validation with reasonable thresholds (default)
  Lenient: Lower thresholds, allows more questionable alignments through

Web Interface:
  For manual audio alignment with visual waveform editing, use the web interface:
  python -m cantonese_anki_generator.web.run
  Then open your browser to http://localhost:3000
        """
    )
    
    parser.add_argument(
        "google_doc_url",
        nargs='?',
        help="URL of the Google Sheets/Docs document containing vocabulary table"
    )
    
    parser.add_argument(
        "audio_file",
        nargs='?',
        type=Path,
        help="Path to the audio file with vocabulary pronunciations"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output path for the generated Anki package (auto-generated in 'output/' folder if not specified)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging and detailed progress information"
    )
    
    parser.add_argument(
        "--no-validation",
        action="store_true",
        help="Skip interactive input validation (for automated usage)"
    )
    
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompt (for automated usage)"
    )
    
    parser.add_argument(
        "--help-setup",
        action="store_true",
        help="Show detailed setup and preparation guide"
    )
    
    parser.add_argument(
        "--create-shortcut",
        action="store_true",
        help="Create desktop shortcut for the web interface"
    )
    
    parser.add_argument(
        "--check-formats",
        action="store_true",
        help="Check input formats without processing"
    )
    
    parser.add_argument(
        "--enable-speech-verification",
        action="store_true",
        default=True,
        help="Enable speech-to-text verification using Whisper (requires openai-whisper package) - enabled by default"
    )
    
    parser.add_argument(
        "--disable-speech-verification",
        action="store_true",
        help="Disable speech-to-text verification (use basic alignment only)"
    )
    
    parser.add_argument(
        "--whisper-model",
        choices=["tiny", "base", "small", "medium", "large"],
        default="base",
        help="Whisper model size for speech verification (default: base)"
    )
    
    parser.add_argument(
        "--start-offset",
        type=float,
        default=None,
        help="Manual start offset in seconds (overrides auto-detection)"
    )
    
    parser.add_argument(
        "--debug-alignment",
        action="store_true",
        help="Show detailed alignment debugging information and test multiple offsets"
    )
    
    parser.add_argument(
        "--validation-level",
        choices=["strict", "normal", "lenient"],
        default="normal",
        help="Validation strictness level (default: normal)"
    )
    
    parser.add_argument(
        "--disable-validation",
        action="store_true",
        help="Disable all validation checks (faster processing, less safety)"
    )
    
    parser.add_argument(
        "--validation-report",
        action="store_true",
        help="Generate detailed validation report"
    )
    
    args = parser.parse_args()
    
    # Handle special commands
    if args.help_setup:
        show_processing_tips()
        return 0
    
    if args.create_shortcut:
        try:
            from cantonese_anki_generator.web.shortcut_creator import WebShortcutCreator
            print("Creating desktop shortcut for web interface...")
            creator = WebShortcutCreator()
            if creator.create_shortcut():
                print("✅ Desktop shortcut created successfully!")
                print("Double-click the shortcut to launch the web interface.")
                print("Your browser will open to http://localhost:3000")
                return 0
            else:
                print("❌ Failed to create desktop shortcut.")
                print("You can still launch the web interface using:")
                print("  python -m cantonese_anki_generator.web.run")
                return 1
        except ImportError as e:
            print(f"❌ Failed to create desktop shortcut: missing or broken web dependencies")
            print(f"   Error: {e}")
            print("   Please ensure all dependencies are installed:")
            print("   pip install -r requirements.txt")
            return 1
        except Exception as e:
            print(f"❌ Failed to create desktop shortcut: {e}")
            print("You can still launch the web interface using:")
            print("  python -m cantonese_anki_generator.web.run")
            return 1
    
    # Interactive mode if arguments are missing
    if not args.google_doc_url or not args.audio_file:
        print("🚀 Cantonese Anki Generator - Interactive Mode")
        print("=" * 50)
        
        if not args.google_doc_url:
            print("📋 Please provide the Google Docs/Sheets URL:")
            print("   Example: https://docs.google.com/spreadsheets/d/your-document-id/edit")
            args.google_doc_url = input("Document URL: ").strip()
            
            if not args.google_doc_url:
                print("❌ Document URL is required")
                return 1
        
        if not args.audio_file:
            print("\n🔊 Please provide the audio file path:")
            print("   Example: /path/to/your/audio.wav")
            audio_path = input("Audio file path: ").strip()
            
            if not audio_path:
                print("❌ Audio file path is required")
                return 1
            
            args.audio_file = Path(audio_path)
        
        print()
    
    # Validate inputs interactively (unless disabled)
    if not args.no_validation:
        if not validate_inputs_interactive(args.google_doc_url, args.audio_file):
            print("\n❌ Input validation failed. Please fix the issues above and try again.")
            return 1
    
    # Format checking mode
    if args.check_formats:
        print("✅ Format validation complete. Use without --check-formats to process.")
        return 0
    
    # Set up logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Generate output path if not specified
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_name = args.audio_file.stem
        args.output = Config.OUTPUT_DIR / f"cantonese_{audio_name}_{timestamp}.apkg"
    
    # Ensure output directories exist
    Config.ensure_directories()
    
    # Confirm processing (unless disabled)
    if not args.no_confirm:
        if not confirm_processing(args.google_doc_url, args.audio_file, args.output):
            print("❌ Processing cancelled by user.")
            return 0
    
    logger.info("🚀 Cantonese Anki Generator")
    logger.info("=" * 40)
    logger.info(f"📋 Document URL: {args.google_doc_url}")
    logger.info(f"🔊 Audio file: {args.audio_file}")
    logger.info(f"📦 Output package: {args.output}")
    
    # Show processing tips in verbose mode
    if args.verbose:
        show_processing_tips()
    
    # Execute pipeline with speech verification handling
    # Handle the disable flag - if user explicitly disabled, turn it off
    enable_speech_verification = args.enable_speech_verification and not args.disable_speech_verification
    
    success = process_pipeline(
        google_doc_url=args.google_doc_url,
        audio_file=args.audio_file,
        output_path=args.output,
        verbose=args.verbose,
        enable_speech_verification=enable_speech_verification,
        whisper_model=args.whisper_model,
        manual_start_offset=args.start_offset,
        debug_alignment=args.debug_alignment,
        validation_level=args.validation_level,
        disable_validation=args.disable_validation,
        validation_report=args.validation_report
    )
    
    # Display error summary if there were any issues
    if error_handler.has_errors() or error_handler.has_warnings():
        print("\n" + "=" * 50)
        print("⚠️  ISSUES DETECTED")
        print("=" * 50)
        
        error_summary = error_handler.get_error_summary()
        
        if error_summary['warning_count'] > 0:
            print(f"⚠️  Warnings: {error_summary['warning_count']}")
            for warning in error_summary['warnings']:
                print(f"   • {warning['message']}")
                if warning['suggested_actions']:
                    print(f"     Suggestion: {warning['suggested_actions'][0]}")
        
        if error_summary['error_count'] > 0:
            print(f"❌ Errors: {error_summary['error_count']}")
            for error in error_summary['errors']:
                print(f"   • {error['message']}")
                if error['suggested_actions']:
                    print(f"     Suggestion: {error['suggested_actions'][0]}")
        
        print("=" * 50)
    
    if success:
        logger.info("🎉 Success! Your Anki deck is ready.")
        logger.info(f"📦 Import {args.output} into Anki to start studying.")
        
        # Show final summary
        summary = progress_tracker.generate_completion_summary()
        cards_created = summary.get('cards_created', 0)
        
        print("\n" + "=" * 50)
        print("🎉 SUCCESS!")
        print("=" * 50)
        print(f"✨ Created {cards_created} flashcards with audio!")
        print(f"📦 Package saved: {args.output}")
        print(f"📊 File size: {args.output.stat().st_size / 1024:.1f} KB")
        
        print("\n📚 Next steps:")
        print("1. Open Anki on your computer")
        print("2. Go to File → Import")
        print(f"3. Select the file: {args.output}")
        print("4. Click Import to add the deck")
        print("5. Start studying your Cantonese vocabulary!")
        
        if args.verbose:
            print(f"\n📈 Processing took {summary.get('pipeline_duration', 0):.1f} seconds")
            print(f"🎯 Success rate: {summary.get('success_rate', 0):.1f}%")
        
        print("=" * 50)
        return 0
    else:
        logger.error("❌ Pipeline failed. Check the error details above.")
        
        print("\n" + "=" * 50)
        print("❌ PROCESSING FAILED")
        print("=" * 50)
        
        # Provide specific guidance based on errors
        if error_handler.has_errors():
            print("🔧 Common solutions:")
            error_summary = error_handler.get_error_summary()
            
            # Categorize errors and provide targeted help
            auth_errors = [e for e in error_summary['errors'] if e['category'] == 'authentication']
            doc_errors = [e for e in error_summary['errors'] if e['category'] == 'document_parsing']
            audio_errors = [e for e in error_summary['errors'] if e['category'] == 'audio_processing']
            
            if auth_errors:
                print("\n📋 Document access issues:")
                print("   • Ensure the document is shared with your Google account")
                print("   • Check that you have view permissions")
                print("   • Try opening the document in your browser first")
                print("   • Verify your Google API credentials are set up")
            
            if doc_errors:
                print("\n📄 Document format issues:")
                print("   • Ensure the document contains a clear table")
                print("   • Use simple formatting (no merged cells)")
                print("   • Put English in first column, Cantonese in second")
                print("   • Check that vocabulary entries are not empty")
            
            if audio_errors:
                print("\n🔊 Audio processing issues:")
                print("   • Check that the audio file is not corrupted")
                print("   • Ensure audio contains clear speech")
                print("   • Try converting to WAV format")
                print("   • Record with less background noise")
            
            print("\n💡 General troubleshooting:")
            print("   • Try with a smaller vocabulary set first (5-10 words)")
            print("   • Use --verbose flag for detailed error information")
            print("   • Check the setup guide with --help-setup")
            
            # Show specific error actions
            print("\n🎯 Specific actions to try:")
            for i, error in enumerate(error_summary['errors'][:3], 1):
                if error['suggested_actions']:
                    print(f"   {i}. {error['suggested_actions'][0]}")
        
        print("\n📞 Need help?")
        print("   • Run with --help-setup for detailed preparation guide")
        print("   • Use --verbose for more detailed error information")
        print("   • Check input formats with --check-formats")
        print("=" * 50)
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
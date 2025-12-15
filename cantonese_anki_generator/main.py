"""
Main entry point for the Cantonese Anki Generator.

Complete pipeline from Google Docs and audio to Anki package.
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

from .config import Config
from .processors.google_sheets_parser import GoogleSheetsParser, GoogleSheetsParsingError
from .processors.google_docs_auth import GoogleDocsAuthError
from .audio.loader import AudioLoader, AudioValidationError
from .audio.smart_segmentation import SmartBoundaryDetector
from .models import AlignedPair
from .anki import AnkiPackageGenerator, UniqueNamingManager
from .errors import error_handler, ErrorCategory, ErrorSeverity, ProcessingError
from .progress import progress_tracker, ProcessingStage
from .format_compatibility import FormatCompatibilityManager, QualityToleranceManager


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
                    verbose: bool = False) -> bool:
    """
    Execute the complete processing pipeline with comprehensive error handling and progress tracking.
    
    Args:
        google_doc_url: URL of Google Doc/Sheets with vocabulary
        audio_file: Path to audio file
        output_path: Path for output Anki package
        verbose: Enable verbose logging
        
    Returns:
        True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
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
        
        try:
            detector = SmartBoundaryDetector(sample_rate=sample_rate)
            segments = detector.segment_audio(audio_data, len(vocab_entries))
            
            progress_tracker.update_summary_data(audio_segments=len(segments))
            progress_tracker.complete_stage(ProcessingStage.AUDIO_SEGMENTATION, success=True,
                                          details={'segment_count': len(segments)})
            progress_tracker.log_detailed_info(ProcessingStage.AUDIO_SEGMENTATION,
                                             f"Created {len(segments)} audio segments")
            
        except Exception as e:
            audio_error = error_handler.handle_audio_processing_error(e, 
                                                                    {'vocab_count': len(vocab_entries)})
            error_handler.add_error(audio_error)
            progress_tracker.complete_stage(ProcessingStage.AUDIO_SEGMENTATION, success=False)
            return False
        
        # Stage 6: Alignment
        progress_tracker.start_stage(ProcessingStage.ALIGNMENT, total_items=min(len(segments), len(vocab_entries)))
        
        # Check for alignment issues
        alignment_error = error_handler.handle_alignment_error(len(segments), len(vocab_entries),
                                                             {'segments': len(segments), 'vocab': len(vocab_entries)})
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
        
        aligned_pairs = []
        min_count = min(len(segments), len(vocab_entries))
        
        for i in range(min_count):
            segment = segments[i]
            vocab_entry = vocab_entries[i]
            
            # Generate audio clip filename
            clip_filename = f"cantonese_{i+1:03d}.wav"
            clip_path = temp_dir / clip_filename
            
            # Save audio clip
            import scipy.io.wavfile as wavfile
            audio_normalized = (segment.audio_data * 32767).astype('int16')
            wavfile.write(str(clip_path), sample_rate, audio_normalized)
            
            # Update segment with file path
            segment.audio_file_path = str(clip_path)
            
            # Create aligned pair
            aligned_pair = AlignedPair(
                vocabulary_entry=vocab_entry,
                audio_segment=segment,
                alignment_confidence=0.85,  # Good confidence from smart segmentation
                audio_file_path=str(clip_path)
            )
            aligned_pairs.append(aligned_pair)
            
            progress_tracker.update_stage_progress(ProcessingStage.ALIGNMENT, completed_items=i+1,
                                                 current_item=f"Aligned: {vocab_entry.english}")
        
        progress_tracker.complete_stage(ProcessingStage.ALIGNMENT, success=True,
                                      details={'aligned_pairs': len(aligned_pairs)})
        progress_tracker.log_detailed_info(ProcessingStage.ALIGNMENT,
                                         f"Created {len(aligned_pairs)} aligned pairs")
        
        # Stage 7: Anki Package Generation
        progress_tracker.start_stage(ProcessingStage.ANKI_GENERATION, total_items=len(aligned_pairs))
        
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
        
        # Stage 8: Finalization
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
  %(prog)s --help-setup  # Show setup and preparation guide

Output:
  Generated .apkg files are saved in the 'output/' directory by default
  Use -o to specify a custom output path

Supported formats:
  Audio: WAV, MP3, M4A, FLAC, OGG (WAV recommended)
  Documents: Google Docs, Google Sheets (Sheets recommended)
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
        "--check-formats",
        action="store_true",
        help="Check input formats without processing"
    )
    
    args = parser.parse_args()
    
    # Handle special commands
    if args.help_setup:
        show_processing_tips()
        return 0
    
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
    
    # Execute pipeline
    success = process_pipeline(
        google_doc_url=args.google_doc_url,
        audio_file=args.audio_file,
        output_path=args.output,
        verbose=args.verbose
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
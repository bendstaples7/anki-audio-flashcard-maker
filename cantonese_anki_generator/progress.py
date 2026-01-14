"""
Progress tracking and user feedback system.

Provides progress indicators, completion summaries, and detailed logging
for all major processing steps in the Cantonese Anki Generator.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


class ProcessingStage(Enum):
    """Major processing stages for progress tracking."""
    INITIALIZATION = "initialization"
    AUTHENTICATION = "authentication"
    DOCUMENT_PARSING = "document_parsing"
    AUDIO_LOADING = "audio_loading"
    AUDIO_SEGMENTATION = "audio_segmentation"
    ALIGNMENT = "alignment"
    ANKI_GENERATION = "anki_generation"
    FINALIZATION = "finalization"


@dataclass
class StageProgress:
    """Progress information for a processing stage."""
    stage: ProcessingStage
    status: str = "pending"  # pending, in_progress, completed, failed
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    progress_percentage: float = 0.0
    current_item: str = ""
    total_items: int = 0
    completed_items: int = 0
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Validation status tracking
    validation_status: Optional[str] = None  # passed, failed, skipped, in_progress
    validation_confidence: Optional[float] = None
    validation_issues_count: int = 0
    validation_recommendations: List[str] = field(default_factory=list)
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get the duration of this stage."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return datetime.now() - self.start_time
        return None
    
    @property
    def is_active(self) -> bool:
        """Check if this stage is currently active."""
        return self.status == "in_progress"
    
    @property
    def is_completed(self) -> bool:
        """Check if this stage is completed."""
        return self.status in ["completed", "failed"]


class ProgressTracker:
    """
    Tracks progress across all processing stages and provides user feedback.
    
    Manages progress indicators, timing information, and completion summaries
    for the entire pipeline.
    """
    
    def __init__(self, enable_console_output: bool = True):
        """
        Initialize the progress tracker.
        
        Args:
            enable_console_output: Whether to print progress to console
        """
        self.logger = logging.getLogger(__name__)
        self.enable_console_output = enable_console_output
        
        # Initialize all stages
        self.stages: Dict[ProcessingStage, StageProgress] = {
            stage: StageProgress(stage=stage) for stage in ProcessingStage
        }
        
        # Overall tracking
        self.pipeline_start_time: Optional[datetime] = None
        self.pipeline_end_time: Optional[datetime] = None
        self.current_stage: Optional[ProcessingStage] = None
        
        # Progress callbacks
        self.progress_callbacks: List[Callable[[StageProgress], None]] = []
        
        # Summary data
        self.summary_data: Dict[str, Any] = {}
    
    def add_progress_callback(self, callback: Callable[[StageProgress], None]) -> None:
        """Add a callback function to be called on progress updates."""
        self.progress_callbacks.append(callback)
    
    def start_pipeline(self) -> None:
        """Start tracking the overall pipeline."""
        self.pipeline_start_time = datetime.now()
        self.logger.info("🚀 Starting Cantonese Anki Generator pipeline")
        if self.enable_console_output:
            print("🚀 Starting Cantonese Anki Generator pipeline")
            print("=" * 50)
    
    def start_stage(self, stage: ProcessingStage, total_items: int = 0, details: Dict[str, Any] = None) -> None:
        """
        Start a processing stage.
        
        Args:
            stage: The processing stage to start
            total_items: Total number of items to process in this stage
            details: Additional details about the stage
        """
        stage_progress = self.stages[stage]
        stage_progress.status = "in_progress"
        stage_progress.start_time = datetime.now()
        stage_progress.total_items = total_items
        stage_progress.completed_items = 0
        stage_progress.progress_percentage = 0.0
        stage_progress.details = details or {}
        
        self.current_stage = stage
        
        # Log and display
        stage_name = stage.value.replace('_', ' ').title()
        self.logger.info(f"Starting stage: {stage_name}")
        
        if self.enable_console_output:
            print(f"\n📋 {stage_name}")
            if total_items > 0:
                print(f"   Processing {total_items} items...")
        
        # Notify callbacks
        for callback in self.progress_callbacks:
            callback(stage_progress)
    
    def update_stage_progress(self, stage: ProcessingStage, completed_items: int = None, 
                            current_item: str = "", details: Dict[str, Any] = None) -> None:
        """
        Update progress for a stage.
        
        Args:
            stage: The processing stage to update
            completed_items: Number of completed items
            current_item: Description of current item being processed
            details: Additional details to update
        """
        stage_progress = self.stages[stage]
        
        if completed_items is not None:
            stage_progress.completed_items = completed_items
            if stage_progress.total_items > 0:
                stage_progress.progress_percentage = (completed_items / stage_progress.total_items) * 100
        
        if current_item:
            stage_progress.current_item = current_item
        
        if details:
            stage_progress.details.update(details)
        
        # Log progress
        if stage_progress.total_items > 0:
            self.logger.debug(
                f"{stage.value}: {stage_progress.completed_items}/{stage_progress.total_items} "
                f"({stage_progress.progress_percentage:.1f}%)"
            )
        
        # Console output for significant progress
        if self.enable_console_output and stage_progress.total_items > 0:
            if completed_items is not None and completed_items % max(1, stage_progress.total_items // 10) == 0:
                print(f"   Progress: {stage_progress.completed_items}/{stage_progress.total_items} "
                      f"({stage_progress.progress_percentage:.1f}%)")
        
        # Notify callbacks
        for callback in self.progress_callbacks:
            callback(stage_progress)
    
    def complete_stage(self, stage: ProcessingStage, success: bool = True, 
                      details: Dict[str, Any] = None) -> None:
        """
        Mark a stage as completed.
        
        Args:
            stage: The processing stage to complete
            success: Whether the stage completed successfully
            details: Additional completion details
        """
        stage_progress = self.stages[stage]
        stage_progress.status = "completed" if success else "failed"
        stage_progress.end_time = datetime.now()
        stage_progress.progress_percentage = 100.0 if success else stage_progress.progress_percentage
        
        if details:
            stage_progress.details.update(details)
        
        # Log completion
        stage_name = stage.value.replace('_', ' ').title()
        duration = stage_progress.duration
        duration_str = f" ({duration.total_seconds():.1f}s)" if duration else ""
        
        if success:
            self.logger.info(f"✅ Completed stage: {stage_name}{duration_str}")
            if self.enable_console_output:
                print(f"   ✅ Completed{duration_str}")
        else:
            self.logger.error(f"❌ Failed stage: {stage_name}{duration_str}")
            if self.enable_console_output:
                print(f"   ❌ Failed{duration_str}")
        
        # Clear current stage if this was it
        if self.current_stage == stage:
            self.current_stage = None
        
        # Notify callbacks
        for callback in self.progress_callbacks:
            callback(stage_progress)
    
    def complete_pipeline(self, success: bool = True) -> None:
        """
        Complete the overall pipeline tracking.
        
        Args:
            success: Whether the pipeline completed successfully
        """
        self.pipeline_end_time = datetime.now()
        
        # Generate completion summary
        summary = self.generate_completion_summary()
        
        # Log and display summary
        if success:
            self.logger.info("🎉 Pipeline completed successfully")
            if self.enable_console_output:
                print("\n🎉 Pipeline completed successfully!")
                self._print_completion_summary(summary)
        else:
            self.logger.error("❌ Pipeline failed")
            if self.enable_console_output:
                print("\n❌ Pipeline failed")
                self._print_completion_summary(summary)
    
    def generate_completion_summary(self) -> Dict[str, Any]:
        """
        Generate a comprehensive completion summary.
        
        Returns:
            Dictionary containing completion statistics and details
        """
        total_duration = None
        if self.pipeline_start_time and self.pipeline_end_time:
            total_duration = self.pipeline_end_time - self.pipeline_start_time
        
        # Count stage statuses
        completed_stages = sum(1 for s in self.stages.values() if s.status == "completed")
        failed_stages = sum(1 for s in self.stages.values() if s.status == "failed")
        total_stages = len(self.stages)
        
        # Collect stage details with validation information
        stage_summaries = {}
        for stage, progress in self.stages.items():
            stage_summary = {
                'status': progress.status,
                'duration': progress.duration.total_seconds() if progress.duration else None,
                'items_processed': progress.completed_items,
                'total_items': progress.total_items,
                'details': progress.details
            }
            
            # Add validation information if available
            if progress.validation_status:
                stage_summary['validation'] = {
                    'status': progress.validation_status,
                    'confidence': progress.validation_confidence,
                    'issues_count': progress.validation_issues_count,
                    'recommendations': progress.validation_recommendations
                }
            
            stage_summaries[stage.value] = stage_summary
        
        # Calculate totals from summary data
        total_vocab_entries = self.summary_data.get('vocab_entries', 0)
        total_audio_segments = self.summary_data.get('audio_segments', 0)
        total_cards_created = self.summary_data.get('cards_created', 0)
        total_audio_clips = self.summary_data.get('audio_clips', 0)
        
        summary = {
            'pipeline_duration': total_duration.total_seconds() if total_duration else None,
            'stages_completed': completed_stages,
            'stages_failed': failed_stages,
            'total_stages': total_stages,
            'success_rate': (completed_stages / total_stages) * 100 if total_stages > 0 else 0,
            'vocabulary_entries': total_vocab_entries,
            'audio_segments': total_audio_segments,
            'cards_created': total_cards_created,
            'audio_clips': total_audio_clips,
            'stage_details': stage_summaries,
            'timestamp': datetime.now().isoformat()
        }
        
        return summary
    
    def _print_completion_summary(self, summary: Dict[str, Any]) -> None:
        """Print a formatted completion summary to console."""
        print("\n" + "=" * 50)
        print("📊 PROCESSING SUMMARY")
        print("=" * 50)
        
        # Overall stats
        duration = summary.get('pipeline_duration')
        if duration:
            print(f"⏱️  Total Duration: {duration:.1f} seconds")
        
        print(f"📈 Success Rate: {summary.get('success_rate', 0):.1f}%")
        print(f"✅ Stages Completed: {summary.get('stages_completed', 0)}/{summary.get('total_stages', 0)}")
        
        if summary.get('stages_failed', 0) > 0:
            print(f"❌ Stages Failed: {summary.get('stages_failed', 0)}")
        
        # Content stats
        print("\n📋 CONTENT PROCESSED:")
        print(f"   📝 Vocabulary Entries: {summary.get('vocabulary_entries', 0)}")
        print(f"   🔊 Audio Segments: {summary.get('audio_segments', 0)}")
        print(f"   🎴 Cards Created: {summary.get('cards_created', 0)}")
        print(f"   🎵 Audio Clips: {summary.get('audio_clips', 0)}")
        
        # Stage breakdown with validation information
        print("\n📋 STAGE BREAKDOWN:")
        for stage_name, details in summary.get('stage_details', {}).items():
            status_icon = "✅" if details['status'] == 'completed' else "❌" if details['status'] == 'failed' else "⏸️"
            stage_display = stage_name.replace('_', ' ').title()
            
            duration_str = ""
            if details.get('duration'):
                duration_str = f" ({details['duration']:.1f}s)"
            
            items_str = ""
            if details.get('total_items', 0) > 0:
                items_str = f" - {details['items_processed']}/{details['total_items']} items"
            
            # Add validation status if available
            validation_str = ""
            if 'validation' in details:
                val_info = details['validation']
                if val_info['status'] == 'passed':
                    confidence_str = f" {val_info['confidence']:.0%}" if val_info['confidence'] else ""
                    validation_str = f" 🔍✅{confidence_str}"
                elif val_info['status'] == 'failed':
                    validation_str = f" 🔍❌({val_info['issues_count']})"
                elif val_info['status'] == 'skipped':
                    validation_str = " 🔍⏭️"
            
            print(f"   {status_icon} {stage_display}{duration_str}{items_str}{validation_str}")
        
        print("=" * 50)
    
    def update_validation_status(self, stage: ProcessingStage, validation_status: str,
                               confidence: float = None, issues_count: int = 0,
                               recommendations: List[str] = None) -> None:
        """
        Update validation status for a stage.
        
        Args:
            stage: The processing stage to update
            validation_status: Status of validation (passed, failed, skipped, in_progress)
            confidence: Validation confidence score (0.0 to 1.0)
            issues_count: Number of validation issues found
            recommendations: List of validation recommendations
        """
        stage_progress = self.stages[stage]
        stage_progress.validation_status = validation_status
        stage_progress.validation_confidence = confidence
        stage_progress.validation_issues_count = issues_count
        stage_progress.validation_recommendations = recommendations or []
        
        # Log validation status
        if validation_status == "passed":
            confidence_str = f" (confidence: {confidence:.1%})" if confidence is not None else ""
            self.logger.info(f"✅ Validation passed for {stage.value}{confidence_str}")
        elif validation_status == "failed":
            self.logger.warning(f"❌ Validation failed for {stage.value} ({issues_count} issues)")
        elif validation_status == "skipped":
            self.logger.debug(f"⏭️ Validation skipped for {stage.value}")
        
        # Console output for validation status
        if self.enable_console_output and validation_status in ["passed", "failed"]:
            if validation_status == "passed":
                confidence_str = f" ({confidence:.0%} confidence)" if confidence is not None else ""
                print(f"   🔍 Validation: ✅ Passed{confidence_str}")
            else:
                print(f"   🔍 Validation: ❌ Failed ({issues_count} issues)")
        
        # Notify callbacks
        for callback in self.progress_callbacks:
            callback(stage_progress)
    
    def log_validation_info(self, stage: ProcessingStage, message: str, 
                          is_warning: bool = False) -> None:
        """
        Log validation-specific information.
        
        Args:
            stage: The processing stage this validation info relates to
            message: The validation message
            is_warning: Whether this is a warning message
        """
        stage_name = stage.value.replace('_', ' ').title()
        
        if is_warning:
            self.logger.warning(f"[{stage_name} Validation] ⚠️ {message}")
            if self.enable_console_output:
                print(f"   🔍 Validation Warning: {message}")
        else:
            self.logger.info(f"[{stage_name} Validation] {message}")
            if self.enable_console_output:
                print(f"   🔍 Validation: {message}")
    
    def update_summary_data(self, **kwargs) -> None:
        """Update summary data with key metrics."""
        self.summary_data.update(kwargs)
    
    def get_current_progress(self) -> Dict[str, Any]:
        """
        Get current progress information.
        
        Returns:
            Dictionary with current progress details
        """
        current_stage_info = None
        if self.current_stage:
            stage_progress = self.stages[self.current_stage]
            current_stage_info = {
                'stage': self.current_stage.value,
                'status': stage_progress.status,
                'progress_percentage': stage_progress.progress_percentage,
                'current_item': stage_progress.current_item,
                'completed_items': stage_progress.completed_items,
                'total_items': stage_progress.total_items
            }
        
        return {
            'pipeline_running': self.pipeline_start_time is not None and self.pipeline_end_time is None,
            'current_stage': current_stage_info,
            'completed_stages': [s.stage.value for s in self.stages.values() if s.status == "completed"],
            'failed_stages': [s.stage.value for s in self.stages.values() if s.status == "failed"]
        }
    
    def log_detailed_info(self, stage: ProcessingStage, message: str, details: Dict[str, Any] = None) -> None:
        """
        Log detailed information for troubleshooting.
        
        Args:
            stage: The processing stage this info relates to
            message: The log message
            details: Additional details to log
        """
        stage_name = stage.value.replace('_', ' ').title()
        self.logger.info(f"[{stage_name}] {message}")
        
        if details:
            for key, value in details.items():
                self.logger.debug(f"[{stage_name}] {key}: {value}")
    
    def log_warning(self, stage: ProcessingStage, message: str, details: Dict[str, Any] = None) -> None:
        """
        Log a warning message.
        
        Args:
            stage: The processing stage this warning relates to
            message: The warning message
            details: Additional details to log
        """
        stage_name = stage.value.replace('_', ' ').title()
        self.logger.warning(f"[{stage_name}] ⚠️ {message}")
        
        if self.enable_console_output:
            print(f"   ⚠️ Warning: {message}")
        
        if details:
            for key, value in details.items():
                self.logger.debug(f"[{stage_name}] {key}: {value}")
    
    def log_error(self, stage: ProcessingStage, message: str, details: Dict[str, Any] = None) -> None:
        """
        Log an error message.
        
        Args:
            stage: The processing stage this error relates to
            message: The error message
            details: Additional details to log
        """
        stage_name = stage.value.replace('_', ' ').title()
        self.logger.error(f"[{stage_name}] ❌ {message}")
        
        if self.enable_console_output:
            print(f"   ❌ Error: {message}")
        
        if details:
            for key, value in details.items():
                self.logger.debug(f"[{stage_name}] {key}: {value}")


class ProgressReporter:
    """
    Provides formatted progress reports for different output formats.
    """
    
    @staticmethod
    def generate_text_report(tracker: ProgressTracker) -> str:
        """Generate a text-based progress report."""
        lines = []
        lines.append("Cantonese Anki Generator - Progress Report")
        lines.append("=" * 50)
        
        # Current status
        progress = tracker.get_current_progress()
        if progress['pipeline_running']:
            lines.append("Status: RUNNING")
            if progress['current_stage']:
                stage_info = progress['current_stage']
                lines.append(f"Current Stage: {stage_info['stage'].replace('_', ' ').title()}")
                if stage_info['total_items'] > 0:
                    lines.append(f"Progress: {stage_info['completed_items']}/{stage_info['total_items']} "
                                f"({stage_info['progress_percentage']:.1f}%)")
        else:
            lines.append("Status: COMPLETED")
        
        # Stage summary
        lines.append("\nStage Summary:")
        for stage, stage_progress in tracker.stages.items():
            status_icon = {
                'pending': '⏸️',
                'in_progress': '🔄',
                'completed': '✅',
                'failed': '❌'
            }.get(stage_progress.status, '❓')
            
            stage_name = stage.value.replace('_', ' ').title()
            lines.append(f"  {status_icon} {stage_name}")
        
        return '\n'.join(lines)
    
    @staticmethod
    def generate_json_report(tracker: ProgressTracker) -> Dict[str, Any]:
        """Generate a JSON-compatible progress report."""
        return {
            'current_progress': tracker.get_current_progress(),
            'completion_summary': tracker.generate_completion_summary(),
            'timestamp': datetime.now().isoformat()
        }


# Global progress tracker instance
progress_tracker = ProgressTracker()
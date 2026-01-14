#!/usr/bin/env python3
"""
Demonstration of the Robust Validation System.

This script shows how to use the validation system to validate
vocabulary and audio data in the Cantonese Anki Generator.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from cantonese_anki_generator.models import VocabularyEntry, AudioSegment
from cantonese_anki_generator.validation import (
    ValidationCoordinator, ValidationConfig, ValidationStrictness,
    ValidationCheckpoint, ValidationResult, IssueType, IssueSeverity,
    IntegrityReporter
)
from cantonese_anki_generator.validation.models import ValidationIssue
import numpy as np


def create_sample_data():
    """Create sample vocabulary and audio data for demonstration."""
    # Sample vocabulary entries
    vocab_entries = [
        VocabularyEntry(english="hello", cantonese="你好", row_index=0, confidence=1.0),
        VocabularyEntry(english="goodbye", cantonese="再見", row_index=1, confidence=0.9),
        VocabularyEntry(english="thank you", cantonese="多謝", row_index=2, confidence=0.95),
        VocabularyEntry(english="water", cantonese="水", row_index=3, confidence=1.0),
        VocabularyEntry(english="food", cantonese="食物", row_index=4, confidence=0.8)
    ]
    
    # Sample audio segments (simulated)
    audio_segments = []
    for i in range(5):
        # Generate simple sine wave audio data
        sample_rate = 22050
        duration = 1.0
        audio_length = int(sample_rate * duration)
        t = np.linspace(0, duration, audio_length)
        frequency = 440 + (i * 100)
        audio_data = np.sin(2 * np.pi * frequency * t) * 0.5
        
        segment = AudioSegment(
            start_time=i * duration,
            end_time=(i + 1) * duration,
            audio_data=audio_data,
            confidence=0.9,
            segment_id=f"segment_{i}",
            audio_file_path=f"audio_{i}.wav"
        )
        audio_segments.append(segment)
    
    return vocab_entries, audio_segments


def create_count_validator():
    """Create a validator that checks vocabulary and audio counts."""
    def count_validator(data, config):
        vocab_entries, audio_segments = data
        
        issues = []
        vocab_count = len(vocab_entries)
        audio_count = len(audio_segments)
        
        if vocab_count != audio_count:
            issues.append(ValidationIssue(
                issue_type=IssueType.COUNT_MISMATCH,
                severity=IssueSeverity.ERROR,
                affected_items=['vocabulary', 'audio'],
                description=f"Count mismatch: {vocab_count} vocabulary entries vs {audio_count} audio segments",
                suggested_fix="Ensure vocabulary and audio have matching counts",
                confidence=0.95
            ))
        
        return ValidationResult(
            checkpoint=ValidationCheckpoint.ALIGNMENT_PROCESS,
            success=len(issues) == 0,
            confidence_score=0.95 if len(issues) == 0 else 0.5,
            issues=issues,
            recommendations=["Verify data consistency between vocabulary and audio"],
            validation_methods_used=['count_comparison']
        )
    
    return count_validator


def create_content_validator():
    """Create a validator that checks content quality."""
    def content_validator(data, config):
        vocab_entries, audio_segments = data
        
        issues = []
        
        # Check vocabulary entries
        for entry in vocab_entries:
            if not entry.english.strip() or not entry.cantonese.strip():
                issues.append(ValidationIssue(
                    issue_type=IssueType.EMPTY_ENTRY,
                    severity=IssueSeverity.ERROR,
                    affected_items=[f"row_{entry.row_index}"],
                    description=f"Empty vocabulary entry at row {entry.row_index}",
                    suggested_fix="Fill in missing vocabulary data",
                    confidence=1.0
                ))
            
            if entry.confidence < config.thresholds.alignment_confidence_min:
                issues.append(ValidationIssue(
                    issue_type=IssueType.ALIGNMENT_CONFIDENCE,
                    severity=IssueSeverity.WARNING,
                    affected_items=[f"row_{entry.row_index}"],
                    description=f"Low confidence ({entry.confidence}) for entry at row {entry.row_index}",
                    suggested_fix="Review entry accuracy",
                    confidence=0.8
                ))
        
        # Check audio segments
        for segment in audio_segments:
            max_amplitude = np.max(np.abs(segment.audio_data))
            if max_amplitude < 0.01:
                issues.append(ValidationIssue(
                    issue_type=IssueType.SILENT_AUDIO,
                    severity=IssueSeverity.WARNING,
                    affected_items=[segment.segment_id],
                    description=f"Audio segment {segment.segment_id} appears to be silent",
                    suggested_fix="Check audio recording quality",
                    confidence=0.9
                ))
        
        return ValidationResult(
            checkpoint=ValidationCheckpoint.DOCUMENT_PARSING,
            success=len(issues) == 0,
            confidence_score=1.0 if len(issues) == 0 else 0.7,
            issues=issues,
            recommendations=["Review data quality and completeness"],
            validation_methods_used=['content_validation']
        )
    
    return content_validator


def demonstrate_validation():
    """Demonstrate the validation system functionality."""
    print("=== Robust Validation System Demo ===\n")
    
    # Create sample data
    vocab_entries, audio_segments = create_sample_data()
    print(f"Created sample data:")
    print(f"  - {len(vocab_entries)} vocabulary entries")
    print(f"  - {len(audio_segments)} audio segments\n")
    
    # Create validation configuration
    config = ValidationConfig(
        strictness=ValidationStrictness.NORMAL,
        enabled=True,
        halt_on_critical=True
    )
    print(f"Validation configuration:")
    print(f"  - Strictness: {config.strictness.value}")
    print(f"  - Alignment confidence threshold: {config.thresholds.alignment_confidence_min}")
    print(f"  - Count mismatch tolerance: {config.thresholds.count_mismatch_tolerance}\n")
    
    # Create validation coordinator
    coordinator = ValidationCoordinator(config)
    
    # Register validators
    coordinator.register_checkpoint_validator(
        ValidationCheckpoint.ALIGNMENT_PROCESS,
        create_count_validator()
    )
    coordinator.register_checkpoint_validator(
        ValidationCheckpoint.DOCUMENT_PARSING,
        create_content_validator()
    )
    
    print("Registered validators for checkpoints:")
    print("  - Document parsing (content validation)")
    print("  - Alignment process (count validation)\n")
    
    # Start validation session
    coordinator.start_validation_session()
    print("Started validation session\n")
    
    # Test 1: Validate with matching data (should pass)
    print("=== Test 1: Valid Data ===")
    result1 = coordinator.validate_at_checkpoint(
        ValidationCheckpoint.DOCUMENT_PARSING,
        (vocab_entries, audio_segments)
    )
    
    result2 = coordinator.validate_at_checkpoint(
        ValidationCheckpoint.ALIGNMENT_PROCESS,
        (vocab_entries, audio_segments)
    )
    
    print(f"Document parsing validation: {'PASS' if result1.success else 'FAIL'}")
    print(f"  - Confidence: {result1.confidence_score:.2f}")
    print(f"  - Issues: {len(result1.issues)}")
    
    print(f"Alignment validation: {'PASS' if result2.success else 'FAIL'}")
    print(f"  - Confidence: {result2.confidence_score:.2f}")
    print(f"  - Issues: {len(result2.issues)}\n")
    
    # Test 2: Validate with mismatched counts (should fail)
    print("=== Test 2: Count Mismatch ===")
    result3 = coordinator.validate_at_checkpoint(
        ValidationCheckpoint.ALIGNMENT_PROCESS,
        (vocab_entries[:3], audio_segments)  # 3 vocab vs 5 audio
    )
    
    print(f"Count validation: {'PASS' if result3.success else 'FAIL'}")
    print(f"  - Confidence: {result3.confidence_score:.2f}")
    print(f"  - Issues: {len(result3.issues)}")
    
    if result3.issues:
        for issue in result3.issues:
            print(f"    * {issue.description}")
            print(f"      Fix: {issue.suggested_fix}")
    print()
    
    # Test 3: Validate with problematic content
    print("=== Test 3: Content Issues ===")
    bad_vocab = [
        VocabularyEntry(english="", cantonese="", row_index=0, confidence=0.0),
        VocabularyEntry(english="test", cantonese="測試", row_index=1, confidence=0.3)
    ]
    
    result4 = coordinator.validate_at_checkpoint(
        ValidationCheckpoint.DOCUMENT_PARSING,
        (bad_vocab, audio_segments[:2])
    )
    
    print(f"Content validation: {'PASS' if result4.success else 'FAIL'}")
    print(f"  - Confidence: {result4.confidence_score:.2f}")
    print(f"  - Issues: {len(result4.issues)}")
    
    if result4.issues:
        for issue in result4.issues:
            print(f"    * {issue.description}")
            print(f"      Fix: {issue.suggested_fix}")
    print()
    
    # Generate final report
    print("=== Final Validation Report ===")
    report = coordinator.end_validation_session()
    
    print(f"Overall status: {'PASS' if report.overall_validation_status else 'FAIL'}")
    print(f"Total validations: {report.total_items_validated}")
    print(f"Successful: {report.successful_validations}")
    print(f"Failed: {report.failed_validations}")
    print(f"Success rate: {report.success_rate:.1f}%")
    
    print(f"\nConfidence distribution:")
    for level, count in report.confidence_distribution.items():
        print(f"  - {level.capitalize()}: {count}")
    
    if report.detailed_issues:
        print(f"\nAll issues detected:")
        for issue in report.detailed_issues:
            print(f"  - {issue.issue_type.value}: {issue.description}")
    
    print(f"\nRecommendations:")
    for rec in report.recommendations:
        print(f"  - {rec}")


    # Demonstrate IntegrityReporter
    print("\n" + "=" * 60)
    print("=== IntegrityReporter Demonstration ===")
    print("=" * 60)
    
    # Create IntegrityReporter
    reporter = IntegrityReporter(config)
    
    # Get all validation results from the session
    all_results = [result1, result2, result3, result4]
    
    # Compile results
    compiled_results = reporter.compile_validation_results(all_results)
    
    # Generate console output
    print("\n--- Console Output Format ---")
    console_output = reporter.format_console_output(compiled_results)
    print(console_output)
    
    # Generate detailed report
    print("\n--- Detailed Report Format ---")
    detailed_report = reporter.format_detailed_report(compiled_results)
    print(detailed_report)
    
    # Generate success/failure listing
    print("\n--- Success/Failure Analysis ---")
    success_failure = reporter.generate_success_failure_listing(all_results)
    print(f"Successful validations: {success_failure['summary']['total_successful']}")
    print(f"Failed validations: {success_failure['summary']['total_failed']}")
    print(f"Success rate: {success_failure['summary']['success_rate']:.1f}%")
    
    # Show issue-specific recommendations
    all_issues = []
    for result in all_results:
        all_issues.extend(result.issues)
    
    if all_issues:
        print(f"\n--- Issue-Specific Recommendations ---")
        issue_recommendations = reporter.generate_issue_specific_recommendations(all_issues)
        for issue_type, recommendations in issue_recommendations.items():
            print(f"\n{issue_type.replace('_', ' ').title()}:")
            for i, rec in enumerate(recommendations[:3], 1):  # Show first 3
                print(f"  {i}. {rec}")
    
    # Generate structured data (for API/JSON output)
    structured_data = reporter.format_structured_data(compiled_results)
    print(f"\n--- Structured Data Summary ---")
    print(f"Overall status: {structured_data['validation_summary']['overall_status']}")
    print(f"Total issues: {structured_data['issue_analysis']['total_issues']}")
    print(f"Validation methods used: {structured_data['validation_methods']['total_methods_used']}")
    
    print(f"\nIssue breakdown by type:")
    for issue_type, count in structured_data['issue_analysis']['by_type'].items():
        print(f"  - {issue_type.replace('_', ' ').title()}: {count}")
    
    print("\nIntegrityReporter demonstration complete!")
    print("The reporter provides multiple output formats for different use cases:")
    print("  - Console output: Quick status for command-line users")
    print("  - Detailed report: Comprehensive analysis for review")
    print("  - Structured data: JSON-compatible format for APIs")
    print("  - Issue-specific recommendations: Targeted guidance for fixes")


if __name__ == "__main__":
    demonstrate_validation()
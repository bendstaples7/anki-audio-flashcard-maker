"""
Demonstration of the Content Validation System.

This script shows how to use the ContentValidator to detect various
content quality issues in audio and vocabulary data.
"""

import numpy as np
from cantonese_anki_generator.validation.content_validator import ContentValidatorImpl
from cantonese_anki_generator.validation.config import ValidationConfig, ValidationStrictness
from cantonese_anki_generator.models import VocabularyEntry, AudioSegment, AlignedPair


def create_sample_data():
    """Create sample data with various quality issues."""
    
    # Vocabulary entries with various issues
    vocab_entries = [
        VocabularyEntry('hello', '你好', 0, confidence=0.9),
        VocabularyEntry('world', '世界', 1, confidence=0.8),
        VocabularyEntry('', '', 2),  # Empty entry
        VocabularyEntry('hello', '你好', 3),  # Duplicate
        VocabularyEntry('test�', '測試', 4),  # Encoding issue
        VocabularyEntry('good morning', '早晨', 5),
    ]
    
    # Audio segments with various characteristics
    sample_rate = 22050
    
    # Normal audio (1 second)
    normal_audio = np.random.randn(sample_rate) * 0.1
    
    # Silent audio (1 second)
    silent_audio = np.zeros(sample_rate)
    
    # Very short audio (0.1 seconds)
    short_audio = np.random.randn(int(sample_rate * 0.1)) * 0.1
    
    # Very long audio (5 seconds)
    long_audio = np.random.randn(sample_rate * 5) * 0.1
    
    # Noisy audio (1 second)
    noisy_audio = np.random.randn(sample_rate) * 0.5
    
    audio_segments = [
        AudioSegment(0.0, 1.0, normal_audio, 0.9, 'seg1'),
        AudioSegment(1.0, 2.0, silent_audio, 0.5, 'seg2'),
        AudioSegment(2.0, 2.1, short_audio, 0.7, 'seg3'),
        AudioSegment(2.1, 7.1, long_audio, 0.6, 'seg4'),
        AudioSegment(7.1, 8.1, noisy_audio, 0.4, 'seg5'),
    ]
    
    # Create aligned pairs with varying confidence
    aligned_pairs = [
        AlignedPair(vocab_entries[0], audio_segments[0], 0.9, 'path1'),
        AlignedPair(vocab_entries[1], audio_segments[1], 0.2, 'path2'),  # Low confidence
        AlignedPair(vocab_entries[5], audio_segments[2], 0.3, 'path3'),  # Low confidence
    ]
    
    return vocab_entries, audio_segments, aligned_pairs


def demonstrate_content_validation():
    """Demonstrate content validation capabilities."""
    
    print("=" * 70)
    print("Content Validation System Demonstration")
    print("=" * 70)
    
    # Create sample data
    vocab_entries, audio_segments, aligned_pairs = create_sample_data()
    
    # Test with different strictness levels
    for strictness in [ValidationStrictness.LENIENT, ValidationStrictness.NORMAL, ValidationStrictness.STRICT]:
        print(f"\n{'=' * 70}")
        print(f"Testing with {strictness.value.upper()} strictness")
        print(f"{'=' * 70}")
        
        # Create validator with specific strictness
        config = ValidationConfig()
        config.set_strictness(strictness)
        validator = ContentValidatorImpl(config)
        
        # Perform comprehensive validation
        data = {
            'audio_segments': audio_segments,
            'vocabulary_entries': vocab_entries
        }
        
        result = validator.validate(data)
        
        print(f"\nValidation Result:")
        print(f"  Success: {result.success}")
        print(f"  Confidence Score: {result.confidence_score:.3f}")
        print(f"  Total Issues: {len(result.issues)}")
        print(f"  Validation Methods Used: {', '.join(result.validation_methods_used)}")
        
        # Display issues by severity
        if result.issues:
            print(f"\nIssues Detected:")
            for issue in result.issues:
                print(f"  [{issue.severity.value.upper()}] {issue.issue_type.value}:")
                print(f"    {issue.description}")
                print(f"    Affected: {len(issue.affected_items)} items")
                print(f"    Confidence: {issue.confidence:.2f}")
        
        # Display recommendations
        if result.recommendations:
            print(f"\nRecommendations:")
            for i, rec in enumerate(result.recommendations, 1):
                print(f"  {i}. {rec}")
    
    # Demonstrate individual validation methods
    print(f"\n{'=' * 70}")
    print("Individual Validation Methods")
    print(f"{'=' * 70}")
    
    config = ValidationConfig()
    validator = ContentValidatorImpl(config)
    
    # Test silence detection
    print("\n1. Silence Detection:")
    silence_issues = validator.detect_silence(audio_segments)
    print(f"   Found {len(silence_issues)} silence-related issues")
    
    # Test duplicate detection
    print("\n2. Duplicate Detection:")
    duplicate_issues = validator.detect_duplicates(vocab_entries)
    print(f"   Found {len(duplicate_issues)} duplicate/empty entry issues")
    
    # Test duration validation
    print("\n3. Duration Validation:")
    duration_issues = validator.validate_duration(audio_segments)
    print(f"   Found {len(duration_issues)} duration anomaly issues")
    
    # Test misalignment detection
    print("\n4. Misalignment Detection:")
    misalignment_issues = validator.detect_misaligned_audio(aligned_pairs)
    print(f"   Found {len(misalignment_issues)} misalignment issues")
    
    # Test comprehensive corruption analysis
    print("\n5. Comprehensive Corruption Analysis:")
    full_data = {
        'aligned_pairs': aligned_pairs,
        'audio_segments': audio_segments,
        'vocabulary_entries': vocab_entries
    }
    analysis = validator.analyze_comprehensive_corruption(full_data)
    print(f"   Corruption types analyzed: {list(analysis['corruption_types'].keys())}")
    print(f"   Correction categories: {len(analysis['suggested_corrections'])}")
    
    if analysis['corruption_types'].get('misalignment'):
        misalign = analysis['corruption_types']['misalignment']
        print(f"   Misalignment analysis:")
        print(f"     - Total pairs: {misalign['total_pairs']}")
        print(f"     - Low confidence: {misalign['low_confidence_count']}")
        if misalign.get('confidence_distribution'):
            dist = misalign['confidence_distribution']
            print(f"     - Mean confidence: {dist['mean']:.3f}")
    
    print(f"\n{'=' * 70}")
    print("Demonstration Complete")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    demonstrate_content_validation()

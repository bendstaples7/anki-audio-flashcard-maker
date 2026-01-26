"""
Alignment module for matching audio segments to vocabulary terms.
"""

from .forced_aligner import ForcedAligner, AlignmentResult
from .aligner import AudioVocabularyAligner
from .refinement import AlignmentRefinement
from .global_reassignment import (
    GlobalReassignmentCoordinator,
    SimilarityMatrixBuilder,
    HungarianAssigner,
    SegmentReassigner,
    ReassignmentLogger
)

__all__ = [
    'ForcedAligner',
    'AlignmentResult',
    'AudioVocabularyAligner',
    'AlignmentRefinement',
    'GlobalReassignmentCoordinator',
    'SimilarityMatrixBuilder',
    'HungarianAssigner',
    'SegmentReassigner',
    'ReassignmentLogger'
]
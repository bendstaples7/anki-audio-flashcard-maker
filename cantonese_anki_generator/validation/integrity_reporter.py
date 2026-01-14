"""
Integrity reporter for comprehensive validation reporting.

Provides detailed validation result aggregation, issue identification,
confidence scoring, and actionable recommendation generation for the
validation system.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict, Counter

from .base import IntegrityReporter as BaseIntegrityReporter
from .models import (
    ValidationResult,
    ValidationIssue,
    IntegrityReport,
    IssueType,
    IssueSeverity,
    ValidationCheckpoint,
)
from .config import ValidationConfig


class IntegrityReporter(BaseIntegrityReporter):
    """
    Comprehensive integrity reporter that aggregates validation results
    and generates detailed reports with actionable recommendations.
    """

    def __init__(self, config: ValidationConfig):
        """Initialize the integrity reporter with configuration."""
        super().__init__(config)
        self.logger = logging.getLogger(__name__)

    def compile_validation_results(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """
        Compile validation results into a structured format for reporting.

        Args:
            results: List of validation results from different checkpoints

        Returns:
            Dict containing compiled validation data with statistics and analysis
        """
        if not results:
            return self._create_empty_compilation()

        # Basic statistics
        total_validations = len(results)
        successful_validations = sum(1 for result in results if result.success)
        failed_validations = total_validations - successful_validations

        # Aggregate all issues
        all_issues = []
        for result in results:
            all_issues.extend(result.issues)

        # Aggregate all recommendations
        all_recommendations = []
        for result in results:
            all_recommendations.extend(result.recommendations)

        # Calculate confidence statistics
        confidence_scores = [result.confidence_score for result in results]
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        min_confidence = min(confidence_scores) if confidence_scores else 0.0
        max_confidence = max(confidence_scores) if confidence_scores else 0.0

        # Group results by checkpoint
        results_by_checkpoint = {}
        for result in results:
            checkpoint_name = result.checkpoint.value
            results_by_checkpoint[checkpoint_name] = result

        # Analyze issue patterns
        issue_analysis = self._analyze_issue_patterns(all_issues)

        # Calculate validation method coverage
        method_coverage = self._calculate_method_coverage(results)

        # Generate confidence distribution
        confidence_distribution = self._generate_confidence_distribution(confidence_scores)

        compilation = {
            "statistics": {
                "total_validations": total_validations,
                "successful_validations": successful_validations,
                "failed_validations": failed_validations,
                "success_rate": (successful_validations / total_validations * 100) if total_validations > 0 else 0.0,
                "average_confidence": avg_confidence,
                "min_confidence": min_confidence,
                "max_confidence": max_confidence,
            },
            "results_by_checkpoint": results_by_checkpoint,
            "all_issues": all_issues,
            "unique_recommendations": list(set(all_recommendations)),
            "issue_analysis": issue_analysis,
            "method_coverage": method_coverage,
            "confidence_distribution": confidence_distribution,
            "compilation_timestamp": datetime.now(),
        }

        self.logger.debug(f"Compiled {total_validations} validation results with {len(all_issues)} total issues")
        return compilation

    def generate_recommendations(self, issues: List[ValidationIssue]) -> List[str]:
        """
        Generate actionable recommendations based on detected validation issues.

        Args:
            issues: List of validation issues to analyze

        Returns:
            List of specific, actionable recommendations for resolving issues
        """
        if not issues:
            return ["All validations passed successfully. No action required."]

        recommendations = []
        
        # Group issues by type for targeted recommendations
        issues_by_type = defaultdict(list)
        for issue in issues:
            issues_by_type[issue.issue_type].append(issue)

        # Generate type-specific recommendations
        for issue_type, type_issues in issues_by_type.items():
            type_recommendations = self._generate_type_specific_recommendations(issue_type, type_issues)
            recommendations.extend(type_recommendations)

        # Generate severity-based recommendations
        critical_issues = [issue for issue in issues if issue.severity == IssueSeverity.CRITICAL]
        if critical_issues:
            recommendations.insert(0, 
                f"CRITICAL: {len(critical_issues)} critical issues detected. "
                "Processing should be halted until these are resolved."
            )

        # Generate confidence-based recommendations
        low_confidence_issues = [issue for issue in issues if issue.confidence < 0.5]
        if low_confidence_issues:
            recommendations.append(
                f"Review {len(low_confidence_issues)} low-confidence issue detections. "
                "Manual verification may be needed."
            )

        # Add general recommendations based on issue patterns
        pattern_recommendations = self._generate_pattern_recommendations(issues)
        recommendations.extend(pattern_recommendations)

        # Remove duplicates while preserving order
        unique_recommendations = []
        seen = set()
        for rec in recommendations:
            if rec not in seen:
                unique_recommendations.append(rec)
                seen.add(rec)

        self.logger.debug(f"Generated {len(unique_recommendations)} unique recommendations from {len(issues)} issues")
        return unique_recommendations

    def format_detailed_report(self, compiled_results: Dict[str, Any]) -> str:
        """
        Format compiled results into a detailed, human-readable report.

        Args:
            compiled_results: Compiled validation data from compile_validation_results

        Returns:
            Formatted string report suitable for console output or logging
        """
        if not compiled_results or compiled_results.get("statistics", {}).get("total_validations", 0) == 0:
            return self._format_empty_report()

        stats = compiled_results["statistics"]
        issues = compiled_results["all_issues"]
        recommendations = compiled_results["unique_recommendations"]
        
        # Build report sections
        report_lines = []
        
        # Header
        report_lines.append("=" * 80)
        report_lines.append("VALIDATION INTEGRITY REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {compiled_results['compilation_timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")

        # Executive Summary
        report_lines.append("EXECUTIVE SUMMARY")
        report_lines.append("-" * 40)
        status = "PASSED" if stats["failed_validations"] == 0 else "FAILED"
        report_lines.append(f"Overall Status: {status}")
        report_lines.append(f"Success Rate: {stats['success_rate']:.1f}% ({stats['successful_validations']}/{stats['total_validations']})")
        report_lines.append(f"Average Confidence: {stats['average_confidence']:.2f}")
        report_lines.append(f"Total Issues: {len(issues)}")
        report_lines.append("")

        # Checkpoint Results
        report_lines.append("CHECKPOINT VALIDATION RESULTS")
        report_lines.append("-" * 40)
        for checkpoint_name, result in compiled_results["results_by_checkpoint"].items():
            status_icon = "✓" if result.success else "✗"
            report_lines.append(f"{status_icon} {checkpoint_name.replace('_', ' ').title()}")
            report_lines.append(f"  Confidence: {result.confidence_score:.2f}")
            report_lines.append(f"  Issues: {len(result.issues)}")
            report_lines.append(f"  Methods: {', '.join(result.validation_methods_used)}")
            report_lines.append("")

        # Issue Analysis
        if issues:
            report_lines.append("ISSUE ANALYSIS")
            report_lines.append("-" * 40)
            
            # Issues by severity
            severity_counts = Counter(issue.severity for issue in issues)
            for severity in [IssueSeverity.CRITICAL, IssueSeverity.ERROR, IssueSeverity.WARNING, IssueSeverity.INFO]:
                count = severity_counts.get(severity, 0)
                if count > 0:
                    report_lines.append(f"{severity.value.upper()}: {count} issues")
            
            report_lines.append("")
            
            # Top issues by type
            type_counts = Counter(issue.issue_type for issue in issues)
            report_lines.append("Most Common Issues:")
            for issue_type, count in type_counts.most_common(5):
                report_lines.append(f"  • {issue_type.value.replace('_', ' ').title()}: {count}")
            report_lines.append("")

        # Confidence Distribution
        conf_dist = compiled_results["confidence_distribution"]
        report_lines.append("CONFIDENCE DISTRIBUTION")
        report_lines.append("-" * 40)
        report_lines.append(f"High (≥0.8): {conf_dist['high']} validations")
        report_lines.append(f"Medium (0.5-0.8): {conf_dist['medium']} validations")
        report_lines.append(f"Low (<0.5): {conf_dist['low']} validations")
        report_lines.append("")

        # Recommendations
        if recommendations:
            report_lines.append("RECOMMENDATIONS")
            report_lines.append("-" * 40)
            for i, rec in enumerate(recommendations, 1):
                report_lines.append(f"{i}. {rec}")
            report_lines.append("")

        # Method Coverage
        method_coverage = compiled_results["method_coverage"]
        if method_coverage:
            report_lines.append("VALIDATION METHOD COVERAGE")
            report_lines.append("-" * 40)
            for method, count in sorted(method_coverage.items()):
                report_lines.append(f"  • {method}: {count} uses")
            report_lines.append("")

        # Footer
        report_lines.append("=" * 80)
        
        formatted_report = "\n".join(report_lines)
        self.logger.debug(f"Formatted detailed report with {len(report_lines)} lines")
        return formatted_report

    def generate_success_failure_listing(self, results: List[ValidationResult]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate detailed success/failure listing with validation method information.

        Args:
            results: List of validation results to analyze

        Returns:
            Dict containing separate lists of successful and failed validations with details
        """
        successful_validations = []
        failed_validations = []

        for result in results:
            validation_info = {
                "checkpoint": result.checkpoint.value,
                "timestamp": result.timestamp.isoformat(),
                "confidence_score": result.confidence_score,
                "validation_methods": result.validation_methods_used,
                "issue_count": len(result.issues),
                "recommendations_count": len(result.recommendations),
                "context": result.context,
            }

            if result.success:
                successful_validations.append(validation_info)
            else:
                # Add failure-specific information
                validation_info.update({
                    "issues": [
                        {
                            "type": issue.issue_type.value,
                            "severity": issue.severity.value,
                            "description": issue.description,
                            "affected_items": issue.affected_items,
                            "confidence": issue.confidence,
                        }
                        for issue in result.issues
                    ],
                    "recommendations": result.recommendations,
                })
                failed_validations.append(validation_info)

        return {
            "successful": successful_validations,
            "failed": failed_validations,
            "summary": {
                "total_successful": len(successful_validations),
                "total_failed": len(failed_validations),
                "success_rate": (len(successful_validations) / len(results) * 100) if results else 0.0,
            }
        }

    def generate_issue_specific_recommendations(self, issues: List[ValidationIssue]) -> Dict[str, List[str]]:
        """
        Generate specific recommendations for resolving each type of detected issue.

        Args:
            issues: List of validation issues to generate recommendations for

        Returns:
            Dict mapping issue types to specific resolution recommendations
        """
        recommendations_by_type = {}

        # Group issues by type
        issues_by_type = defaultdict(list)
        for issue in issues:
            issues_by_type[issue.issue_type].append(issue)

        for issue_type, type_issues in issues_by_type.items():
            type_name = issue_type.value
            recommendations = []

            if issue_type == IssueType.COUNT_MISMATCH:
                recommendations.extend([
                    "1. Verify source document format and structure",
                    "2. Check for hidden or merged cells in spreadsheets",
                    "3. Ensure audio file contains expected number of segments",
                    "4. Review vocabulary extraction parameters",
                    "5. Validate audio segmentation boundaries",
                ])

            elif issue_type == IssueType.ALIGNMENT_CONFIDENCE:
                low_conf_count = sum(1 for issue in type_issues if issue.confidence < 0.5)
                recommendations.extend([
                    f"1. Manual review required for {low_conf_count} low-confidence alignments",
                    "2. Adjust alignment confidence thresholds if appropriate",
                    "3. Improve audio quality or reduce background noise",
                    "4. Verify vocabulary terms match audio pronunciation",
                    "5. Consider re-recording problematic audio segments",
                ])

            elif issue_type == IssueType.SILENT_AUDIO:
                recommendations.extend([
                    "1. Adjust voice activity detection (VAD) sensitivity",
                    "2. Check audio file for corruption or encoding issues",
                    "3. Verify audio segmentation boundaries are correct",
                    "4. Increase minimum segment duration threshold",
                    "5. Re-record audio with clearer pronunciation",
                ])

            elif issue_type == IssueType.DUPLICATE_ENTRY:
                affected_items = set()
                for issue in type_issues:
                    affected_items.update(issue.affected_items)
                recommendations.extend([
                    f"1. Remove {len(affected_items)} duplicate entries from source document",
                    "2. Check for copy-paste errors in vocabulary list",
                    "3. Verify unique identifiers for each vocabulary term",
                    "4. Use data validation tools to prevent duplicates",
                    "5. Review document editing history for accidental duplications",
                ])

            elif issue_type == IssueType.EMPTY_ENTRY:
                recommendations.extend([
                    "1. Fill in missing vocabulary terms in source document",
                    "2. Remove empty rows or cells from vocabulary list",
                    "3. Check for formatting issues causing empty entries",
                    "4. Validate required fields are properly populated",
                    "5. Use data validation to prevent empty submissions",
                ])

            elif issue_type == IssueType.DURATION_ANOMALY:
                short_segments = sum(1 for issue in type_issues if "short" in issue.description.lower())
                long_segments = len(type_issues) - short_segments
                recommendations.extend([
                    f"1. Review {short_segments} unusually short audio segments",
                    f"2. Review {long_segments} unusually long audio segments",
                    "3. Adjust segmentation parameters for better boundary detection",
                    "4. Check for pauses or silence within vocabulary pronunciations",
                    "5. Consider manual segmentation for problematic sections",
                ])

            elif issue_type == IssueType.MISALIGNMENT:
                recommendations.extend([
                    "1. Manually verify term-audio pairings for accuracy",
                    "2. Re-run alignment with different parameters",
                    "3. Check vocabulary order matches audio sequence",
                    "4. Verify audio timing and pronunciation clarity",
                    "5. Consider forced alignment with phonetic transcription",
                ])

            elif issue_type == IssueType.CORRUPTION:
                recommendations.extend([
                    "1. CRITICAL: Check source files for data corruption",
                    "2. Re-download or re-create corrupted source files",
                    "3. Verify file integrity using checksums if available",
                    "4. Check storage media for errors or failures",
                    "5. Restore from backup if corruption is confirmed",
                ])

            # Add confidence-based recommendations
            avg_confidence = sum(issue.confidence for issue in type_issues) / len(type_issues)
            if avg_confidence < 0.3:
                recommendations.append(
                    f"6. Low detection confidence ({avg_confidence:.2f}) - consider manual verification"
                )

            recommendations_by_type[type_name] = recommendations

        return recommendations_by_type

    def format_console_output(self, compiled_results: Dict[str, Any]) -> str:
        """
        Format validation results for console output with color coding and clear structure.

        Args:
            compiled_results: Compiled validation data

        Returns:
            Console-formatted string with clear visual hierarchy
        """
        if not compiled_results or compiled_results.get("statistics", {}).get("total_validations", 0) == 0:
            return "No validation results available."

        stats = compiled_results["statistics"]
        lines = []

        # Header with status
        status = "PASSED" if stats["failed_validations"] == 0 else "FAILED"
        status_symbol = "✓" if status == "PASSED" else "✗"
        
        lines.extend([
            "",
            f"Validation Status: {status_symbol} {status}",
            f"Success Rate: {stats['success_rate']:.1f}% ({stats['successful_validations']}/{stats['total_validations']})",
            f"Average Confidence: {stats['average_confidence']:.2f}",
            "",
        ])

        # Quick checkpoint summary
        lines.append("Checkpoint Results:")
        for checkpoint_name, result in compiled_results["results_by_checkpoint"].items():
            symbol = "✓" if result.success else "✗"
            name = checkpoint_name.replace('_', ' ').title()
            lines.append(f"  {symbol} {name} (confidence: {result.confidence_score:.2f})")

        # Issue summary if any
        issues = compiled_results["all_issues"]
        if issues:
            lines.extend(["", "Issues Summary:"])
            severity_counts = Counter(issue.severity for issue in issues)
            for severity in [IssueSeverity.CRITICAL, IssueSeverity.ERROR, IssueSeverity.WARNING]:
                count = severity_counts.get(severity, 0)
                if count > 0:
                    lines.append(f"  • {severity.value.upper()}: {count}")

        # Top recommendations
        recommendations = compiled_results["unique_recommendations"]
        if recommendations:
            lines.extend(["", "Key Recommendations:"])
            for i, rec in enumerate(recommendations[:3], 1):  # Show top 3
                lines.append(f"  {i}. {rec}")
            if len(recommendations) > 3:
                lines.append(f"  ... and {len(recommendations) - 3} more")

        lines.append("")
        return "\n".join(lines)

    def format_structured_data(self, compiled_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format validation results as structured data for programmatic consumption.

        Args:
            compiled_results: Compiled validation data

        Returns:
            Structured data format suitable for JSON serialization or API responses
        """
        if not compiled_results:
            return {"status": "no_data", "message": "No validation results available"}

        stats = compiled_results["statistics"]
        
        # Convert ValidationResult objects to serializable format
        serializable_checkpoints = {}
        for checkpoint_name, result in compiled_results["results_by_checkpoint"].items():
            serializable_checkpoints[checkpoint_name] = {
                "success": result.success,
                "confidence_score": result.confidence_score,
                "timestamp": result.timestamp.isoformat(),
                "validation_methods": result.validation_methods_used,
                "issue_count": len(result.issues),
                "issues": [
                    {
                        "type": issue.issue_type.value,
                        "severity": issue.severity.value,
                        "description": issue.description,
                        "affected_items": issue.affected_items,
                        "suggested_fix": issue.suggested_fix,
                        "confidence": issue.confidence,
                    }
                    for issue in result.issues
                ],
                "recommendations": result.recommendations,
                "context": result.context,
            }

        structured_data = {
            "validation_summary": {
                "overall_status": "passed" if stats["failed_validations"] == 0 else "failed",
                "total_validations": stats["total_validations"],
                "successful_validations": stats["successful_validations"],
                "failed_validations": stats["failed_validations"],
                "success_rate": stats["success_rate"],
                "confidence_metrics": {
                    "average": stats["average_confidence"],
                    "minimum": stats["min_confidence"],
                    "maximum": stats["max_confidence"],
                    "distribution": compiled_results["confidence_distribution"],
                },
            },
            "checkpoint_results": serializable_checkpoints,
            "issue_analysis": {
                "total_issues": len(compiled_results["all_issues"]),
                "by_type": compiled_results["issue_analysis"].get("type_distribution", {}),
                "by_severity": compiled_results["issue_analysis"].get("severity_distribution", {}),
                "most_affected_items": compiled_results["issue_analysis"].get("most_affected_items", []),
            },
            "recommendations": {
                "general": compiled_results["unique_recommendations"],
                "by_issue_type": self.generate_issue_specific_recommendations(compiled_results["all_issues"]),
            },
            "validation_methods": {
                "coverage": compiled_results["method_coverage"],
                "total_methods_used": len(compiled_results["method_coverage"]),
            },
            "metadata": {
                "generation_timestamp": compiled_results["compilation_timestamp"].isoformat(),
                "report_version": "1.0",
                "validation_config": {
                    "enabled": self.config.enabled,
                    "strictness": self.config.strictness.value if hasattr(self.config, 'strictness') else "unknown",
                },
            },
        }

        return structured_data

    def _create_empty_compilation(self) -> Dict[str, Any]:
        """Create empty compilation structure."""
        return {
            "statistics": {
                "total_validations": 0,
                "successful_validations": 0,
                "failed_validations": 0,
                "success_rate": 0.0,
                "average_confidence": 0.0,
                "min_confidence": 0.0,
                "max_confidence": 0.0,
            },
            "results_by_checkpoint": {},
            "all_issues": [],
            "unique_recommendations": [],
            "issue_analysis": {},
            "method_coverage": {},
            "confidence_distribution": {"high": 0, "medium": 0, "low": 0},
            "compilation_timestamp": datetime.now(),
        }

    def _analyze_issue_patterns(self, issues: List[ValidationIssue]) -> Dict[str, Any]:
        """Analyze patterns in validation issues."""
        if not issues:
            return {}

        # Count by type and severity
        type_counts = Counter(issue.issue_type for issue in issues)
        severity_counts = Counter(issue.severity for issue in issues)
        
        # Find most affected items
        affected_items = []
        for issue in issues:
            affected_items.extend(issue.affected_items)
        most_affected = Counter(affected_items).most_common(5)

        # Calculate average confidence by issue type
        confidence_by_type = defaultdict(list)
        for issue in issues:
            confidence_by_type[issue.issue_type].append(issue.confidence)
        
        avg_confidence_by_type = {}
        for issue_type, confidences in confidence_by_type.items():
            avg_confidence_by_type[issue_type.value] = sum(confidences) / len(confidences)

        return {
            "type_distribution": {t.value: count for t, count in type_counts.items()},
            "severity_distribution": {s.value: count for s, count in severity_counts.items()},
            "most_affected_items": most_affected,
            "average_confidence_by_type": avg_confidence_by_type,
        }

    def _calculate_method_coverage(self, results: List[ValidationResult]) -> Dict[str, int]:
        """Calculate how many times each validation method was used."""
        method_counts = Counter()
        for result in results:
            for method in result.validation_methods_used:
                method_counts[method] += 1
        return dict(method_counts)

    def _generate_confidence_distribution(self, confidence_scores: List[float]) -> Dict[str, int]:
        """Generate confidence score distribution."""
        distribution = {"high": 0, "medium": 0, "low": 0}
        
        for score in confidence_scores:
            if score >= 0.8:
                distribution["high"] += 1
            elif score >= 0.5:
                distribution["medium"] += 1
            else:
                distribution["low"] += 1
                
        return distribution

    def _generate_type_specific_recommendations(self, issue_type: IssueType, issues: List[ValidationIssue]) -> List[str]:
        """Generate recommendations specific to an issue type."""
        recommendations = []
        count = len(issues)
        
        if issue_type == IssueType.COUNT_MISMATCH:
            recommendations.append(
                f"Count Mismatch ({count} issues): Verify that vocabulary extraction and "
                "audio segmentation are producing matching numbers of items. "
                "Check for missing or extra entries in source documents."
            )
        
        elif issue_type == IssueType.ALIGNMENT_CONFIDENCE:
            avg_confidence = sum(issue.confidence for issue in issues) / count
            recommendations.append(
                f"Low Alignment Confidence ({count} issues, avg: {avg_confidence:.2f}): "
                "Review term-audio pairings with confidence below threshold. "
                "Consider manual verification or improved alignment parameters."
            )
        
        elif issue_type == IssueType.SILENT_AUDIO:
            recommendations.append(
                f"Silent Audio ({count} issues): Check audio segmentation boundaries. "
                "Segments may be too short or contain only silence. "
                "Adjust voice activity detection sensitivity."
            )
        
        elif issue_type == IssueType.DUPLICATE_ENTRY:
            recommendations.append(
                f"Duplicate Entries ({count} issues): Remove duplicate vocabulary terms "
                "from source document. Check for copy-paste errors or formatting issues."
            )
        
        elif issue_type == IssueType.EMPTY_ENTRY:
            recommendations.append(
                f"Empty Entries ({count} issues): Fill in missing vocabulary terms "
                "or remove empty rows from source document."
            )
        
        elif issue_type == IssueType.DURATION_ANOMALY:
            recommendations.append(
                f"Duration Anomalies ({count} issues): Review audio segments with "
                "unusual durations. May indicate segmentation errors or audio quality issues."
            )
        
        elif issue_type == IssueType.MISALIGNMENT:
            recommendations.append(
                f"Misalignment ({count} issues): Audio clips may be paired with wrong "
                "vocabulary terms. Review alignment process and consider manual correction."
            )
        
        elif issue_type == IssueType.CORRUPTION:
            recommendations.append(
                f"Data Corruption ({count} issues): Serious data integrity problems detected. "
                "Check source files for corruption and re-process if necessary."
            )
        
        return recommendations

    def _generate_pattern_recommendations(self, issues: List[ValidationIssue]) -> List[str]:
        """Generate recommendations based on issue patterns."""
        recommendations = []
        
        # Check for widespread issues
        total_issues = len(issues)
        if total_issues > 10:
            recommendations.append(
                f"High issue count ({total_issues} total): Consider reviewing "
                "source data quality and processing parameters."
            )
        
        # Check for low confidence patterns
        low_confidence_count = sum(1 for issue in issues if issue.confidence < 0.3)
        if low_confidence_count > total_issues * 0.3:  # More than 30% low confidence
            recommendations.append(
                "Many low-confidence detections suggest validation thresholds "
                "may need adjustment or manual review is required."
            )
        
        # Check for critical issue concentration
        critical_count = sum(1 for issue in issues if issue.severity == IssueSeverity.CRITICAL)
        if critical_count > 0:
            recommendations.append(
                f"{critical_count} critical issues require immediate attention "
                "before processing can continue safely."
            )
        
        return recommendations

    def _format_empty_report(self) -> str:
        """Format report for empty validation results."""
        return """
================================================================================
VALIDATION INTEGRITY REPORT
================================================================================
Generated: {timestamp}

No validation results to report.
Either no validations were performed or validation was bypassed.

Status: NO DATA
================================================================================
        """.format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')).strip()
"""
Unique naming and conflict prevention for Anki packages.

This module ensures unique deck and package identifiers to prevent
naming conflicts during import.
"""

import logging
import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Set, Optional


logger = logging.getLogger(__name__)


class UniqueNamingManager:
    """
    Manages unique naming for Anki decks and packages to prevent conflicts.
    """
    
    def __init__(self):
        """Initialize the naming manager."""
        self._used_names: Set[str] = set()
        self._used_ids: Set[int] = set()
    
    def generate_unique_deck_name(self, base_name: str = None, 
                                 source_info: str = None) -> str:
        """
        Generate a unique deck name.
        
        Args:
            base_name: Base name for the deck (auto-generated if None)
            source_info: Additional info about the source (e.g., filename)
            
        Returns:
            Unique deck name
        """
        if base_name is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            base_name = f"Cantonese Vocabulary - {timestamp}"
        
        # Add source info if provided
        if source_info:
            clean_source = self._sanitize_name(source_info)
            base_name = f"{base_name} ({clean_source})"
        
        # Ensure uniqueness
        unique_name = self._ensure_unique_name(base_name)
        
        logger.info(f"Generated unique deck name: {unique_name}")
        return unique_name
    
    def generate_unique_deck_id(self, deck_name: str) -> int:
        """
        Generate a unique deck ID.
        
        Args:
            deck_name: Name of the deck
            
        Returns:
            Unique integer ID for the deck
        """
        # Create base ID from deck name and timestamp
        timestamp = datetime.now().isoformat()
        unique_string = f"{deck_name}_{timestamp}"
        
        # Generate hash
        hash_object = hashlib.md5(unique_string.encode())
        base_id = int(hash_object.hexdigest()[:8], 16)
        
        # Ensure it's positive and within range
        base_id = abs(base_id) % 2147483647  # Max 32-bit signed int
        
        # Ensure uniqueness
        unique_id = self._ensure_unique_id(base_id)
        
        logger.debug(f"Generated unique deck ID: {unique_id}")
        return unique_id
    
    def generate_unique_package_filename(self, base_name: str = None, 
                                       output_dir: str = ".") -> str:
        """
        Generate a unique filename for the .apkg package.
        
        Args:
            base_name: Base name for the file (auto-generated if None)
            output_dir: Directory where the file will be saved
            
        Returns:
            Unique filename (without directory path)
        """
        if base_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"cantonese_vocab_{timestamp}"
        
        # Ensure .apkg extension
        if not base_name.lower().endswith('.apkg'):
            base_name += '.apkg'
        
        # Sanitize the name
        clean_name = self._sanitize_filename(base_name)
        
        # Check for conflicts in the target directory
        output_path = Path(output_dir)
        counter = 0
        unique_name = clean_name
        
        while (output_path / unique_name).exists():
            counter += 1
            name_part = clean_name[:-5]  # Remove .apkg
            unique_name = f"{name_part}_{counter:03d}.apkg"
        
        logger.info(f"Generated unique package filename: {unique_name}")
        return unique_name
    
    def _ensure_unique_name(self, base_name: str) -> str:
        """
        Ensure a name is unique by adding a counter if needed.
        
        Args:
            base_name: Base name to make unique
            
        Returns:
            Unique name
        """
        if base_name not in self._used_names:
            self._used_names.add(base_name)
            return base_name
        
        counter = 1
        while True:
            unique_name = f"{base_name} ({counter})"
            if unique_name not in self._used_names:
                self._used_names.add(unique_name)
                return unique_name
            counter += 1
    
    def _ensure_unique_id(self, base_id: int) -> int:
        """
        Ensure an ID is unique by incrementing if needed.
        
        Args:
            base_id: Base ID to make unique
            
        Returns:
            Unique ID
        """
        if base_id not in self._used_ids:
            self._used_ids.add(base_id)
            return base_id
        
        # If collision, increment until we find a unique ID
        unique_id = base_id
        while unique_id in self._used_ids:
            unique_id = (unique_id + 1) % 2147483647
        
        self._used_ids.add(unique_id)
        return unique_id
    
    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize a name for use in deck names.
        
        Args:
            name: Name to sanitize
            
        Returns:
            Sanitized name
        """
        # Remove problematic characters but keep spaces
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        
        # Limit length
        if len(sanitized) > 50:
            sanitized = sanitized[:47] + "..."
        
        return sanitized.strip()
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a filename for filesystem compatibility.
        
        Args:
            filename: Filename to sanitize
            
        Returns:
            Sanitized filename
        """
        # Remove or replace problematic characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Remove multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Remove leading/trailing underscores and dots
        sanitized = sanitized.strip('_.')
        
        # Ensure it's not empty
        if not sanitized or sanitized == '.apkg':
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sanitized = f"cantonese_vocab_{timestamp}.apkg"
        
        return sanitized
    
    def register_existing_names(self, names: list):
        """
        Register existing names to avoid conflicts.
        
        Args:
            names: List of existing names to avoid
        """
        for name in names:
            self._used_names.add(name)
        
        logger.info(f"Registered {len(names)} existing names")
    
    def register_existing_ids(self, ids: list):
        """
        Register existing IDs to avoid conflicts.
        
        Args:
            ids: List of existing IDs to avoid
        """
        for id_val in ids:
            self._used_ids.add(id_val)
        
        logger.info(f"Registered {len(ids)} existing IDs")


class ConflictDetector:
    """
    Detects potential conflicts with existing Anki data.
    """
    
    @staticmethod
    def check_package_conflicts(output_dir: str, filename: str) -> bool:
        """
        Check if a package filename would conflict with existing files.
        
        Args:
            output_dir: Directory to check
            filename: Filename to check
            
        Returns:
            True if conflict exists, False otherwise
        """
        full_path = Path(output_dir) / filename
        exists = full_path.exists()
        
        if exists:
            logger.warning(f"Package conflict detected: {full_path}")
        
        return exists
    
    @staticmethod
    def suggest_alternative_name(conflicting_name: str, output_dir: str) -> str:
        """
        Suggest an alternative name when a conflict is detected.
        
        Args:
            conflicting_name: Name that has a conflict
            output_dir: Directory where the file will be saved
            
        Returns:
            Alternative name without conflicts
        """
        naming_manager = UniqueNamingManager()
        return naming_manager.generate_unique_package_filename(
            conflicting_name, output_dir
        )
    
    @staticmethod
    def get_conflict_report(output_dir: str, proposed_names: list) -> dict:
        """
        Generate a report of potential conflicts.
        
        Args:
            output_dir: Directory to check
            proposed_names: List of proposed names to check
            
        Returns:
            Dictionary with conflict information
        """
        report = {
            'conflicts_found': 0,
            'conflicts': [],
            'safe_names': []
        }
        
        for name in proposed_names:
            if ConflictDetector.check_package_conflicts(output_dir, name):
                report['conflicts_found'] += 1
                report['conflicts'].append({
                    'name': name,
                    'alternative': ConflictDetector.suggest_alternative_name(name, output_dir)
                })
            else:
                report['safe_names'].append(name)
        
        return report
"""
Anki package (.apkg) generation using genanki library.

This module creates valid Anki packages with embedded audio files
and proper metadata structure.
"""

import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import genanki

from ..models import AlignedPair, AnkiCard
from .templates import CantoneseCardTemplate, CardFormatter


logger = logging.getLogger(__name__)


class AnkiPackageGenerator:
    """
    Generates complete .apkg files with cards and media.
    
    Uses genanki library to create valid Anki packages with embedded
    audio files and proper package metadata.
    """
    
    def __init__(self):
        """Initialize the package generator."""
        self.model = CantoneseCardTemplate.create_model()
        self.formatter = CardFormatter()
    
    def generate_package(self, aligned_pairs: List[AlignedPair], 
                        output_path: str, deck_name: str = None) -> bool:
        """
        Generate a complete Anki package from aligned vocabulary pairs.
        
        Args:
            aligned_pairs: List of vocabulary-audio aligned pairs
            output_path: Path where to save the .apkg file
            deck_name: Name for the Anki deck (auto-generated if None)
            
        Returns:
            True if package was created successfully, False otherwise
        """
        try:
            logger.info(f"Generating Anki package with {len(aligned_pairs)} cards")
            
            # Generate deck name if not provided
            if deck_name is None:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
                deck_name = f"Cantonese Vocabulary - {timestamp}"
            
            # Create deck with unique ID
            deck_id = self._generate_deck_id(deck_name)
            deck = genanki.Deck(deck_id, deck_name)
            
            logger.info(f"Created deck: {deck_name} (ID: {deck_id})")
            
            # Create cards and collect media files
            media_files = []
            cards_created = 0
            
            for i, aligned_pair in enumerate(aligned_pairs, 1):
                try:
                    # Create Anki card
                    card = self._create_anki_card(aligned_pair, i)
                    if card:
                        deck.add_note(card)
                        cards_created += 1
                        
                        # Add audio file to media
                        if aligned_pair.audio_file_path and os.path.exists(aligned_pair.audio_file_path):
                            media_files.append(aligned_pair.audio_file_path)
                        else:
                            logger.warning(f"Audio file not found: {aligned_pair.audio_file_path}")
                
                except Exception as e:
                    logger.error(f"Failed to create card {i}: {e}")
                    continue
            
            logger.info(f"Created {cards_created} cards with {len(media_files)} media files")
            
            # Generate the package
            package = genanki.Package(deck)
            package.media_files = media_files
            
            # Ensure output directory exists
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Write the package
            package.write_to_file(output_path)
            
            logger.info(f"Successfully created Anki package: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate Anki package: {e}")
            return False
    
    def _create_anki_card(self, aligned_pair: AlignedPair, index: int) -> Optional[genanki.Note]:
        """
        Create an Anki note (card) from an aligned pair.
        
        Args:
            aligned_pair: Vocabulary-audio aligned pair
            index: Index for unique naming
            
        Returns:
            genanki.Note object or None if creation failed
        """
        try:
            vocab = aligned_pair.vocabulary_entry
            
            # Generate audio filename
            audio_filename = self.formatter.generate_audio_filename(
                vocab.english, vocab.cantonese, index
            )
            
            # Copy audio file to match expected filename
            if aligned_pair.audio_file_path and os.path.exists(aligned_pair.audio_file_path):
                # Get the directory of the original audio file
                original_dir = Path(aligned_pair.audio_file_path).parent
                new_audio_path = original_dir / audio_filename
                
                # Copy if names don't match
                if str(new_audio_path) != aligned_pair.audio_file_path:
                    shutil.copy2(aligned_pair.audio_file_path, new_audio_path)
                    # Update the aligned pair to point to the new file
                    aligned_pair.audio_file_path = str(new_audio_path)
            
            # Format card fields
            fields = self.formatter.format_card_fields(
                english=vocab.english,
                cantonese=vocab.cantonese,
                audio_filename=audio_filename,
                tags=['cantonese', 'vocabulary', f'confidence_{int(aligned_pair.alignment_confidence * 100)}']
            )
            
            # Create the note
            note = genanki.Note(
                model=self.model,
                fields=[
                    fields['English'],
                    fields['Cantonese'],
                    fields['Audio'],
                    fields['Tags']
                ]
            )
            
            logger.debug(f"Created note: {vocab.english} → {vocab.cantonese}")
            return note
            
        except Exception as e:
            logger.error(f"Failed to create note for {aligned_pair.vocabulary_entry.english}: {e}")
            return None
    
    def _generate_deck_id(self, deck_name: str) -> int:
        """
        Generate a unique deck ID based on deck name and timestamp.
        
        Args:
            deck_name: Name of the deck
            
        Returns:
            Unique integer ID for the deck
        """
        # Use hash of deck name + timestamp for uniqueness
        import hashlib
        
        timestamp = datetime.now().isoformat()
        unique_string = f"{deck_name}_{timestamp}"
        
        # Generate hash and convert to positive integer
        hash_object = hashlib.md5(unique_string.encode())
        deck_id = int(hash_object.hexdigest()[:8], 16)
        
        # Ensure it's positive and within reasonable range
        deck_id = abs(deck_id) % 2147483647  # Max 32-bit signed int
        
        logger.debug(f"Generated deck ID {deck_id} for '{deck_name}'")
        return deck_id
    
    def create_anki_cards_from_pairs(self, aligned_pairs: List[AlignedPair]) -> List[AnkiCard]:
        """
        Convert aligned pairs to AnkiCard objects for further processing.
        
        Args:
            aligned_pairs: List of vocabulary-audio aligned pairs
            
        Returns:
            List of AnkiCard objects
        """
        anki_cards = []
        
        for i, aligned_pair in enumerate(aligned_pairs, 1):
            try:
                vocab = aligned_pair.vocabulary_entry
                
                # Generate audio filename
                audio_filename = self.formatter.generate_audio_filename(
                    vocab.english, vocab.cantonese, i
                )
                
                # Create AnkiCard object
                anki_card = AnkiCard(
                    front_text=vocab.english,
                    back_text=vocab.cantonese,
                    audio_file=audio_filename,
                    tags=['cantonese', 'vocabulary'],
                    card_id=f"cantonese_{i:03d}"
                )
                
                anki_cards.append(anki_card)
                
            except Exception as e:
                logger.error(f"Failed to create AnkiCard for pair {i}: {e}")
                continue
        
        logger.info(f"Created {len(anki_cards)} AnkiCard objects")
        return anki_cards


class PackageValidator:
    """
    Validates Anki packages for correctness and completeness.
    """
    
    @staticmethod
    def validate_package(package_path: str) -> bool:
        """
        Validate that an Anki package is properly formatted.
        
        Args:
            package_path: Path to the .apkg file
            
        Returns:
            True if package is valid, False otherwise
        """
        try:
            if not os.path.exists(package_path):
                logger.error(f"Package file not found: {package_path}")
                return False
            
            # Check file extension
            if not package_path.lower().endswith('.apkg'):
                logger.error(f"Invalid file extension: {package_path}")
                return False
            
            # Check file size (should be > 0)
            file_size = os.path.getsize(package_path)
            if file_size == 0:
                logger.error(f"Package file is empty: {package_path}")
                return False
            
            logger.info(f"Package validation passed: {package_path} ({file_size} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Package validation failed: {e}")
            return False
    
    @staticmethod
    def get_package_info(package_path: str) -> dict:
        """
        Get information about an Anki package.
        
        Args:
            package_path: Path to the .apkg file
            
        Returns:
            Dictionary with package information
        """
        info = {
            'path': package_path,
            'exists': False,
            'size_bytes': 0,
            'valid': False
        }
        
        try:
            if os.path.exists(package_path):
                info['exists'] = True
                info['size_bytes'] = os.path.getsize(package_path)
                info['valid'] = PackageValidator.validate_package(package_path)
            
        except Exception as e:
            logger.error(f"Failed to get package info: {e}")
        
        return info
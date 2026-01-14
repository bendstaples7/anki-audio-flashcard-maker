"""Tests for session API endpoints."""

import pytest
import json
import tempfile
import os
from datetime import datetime
from flask import Flask

from cantonese_anki_generator.web.app import create_app
from cantonese_anki_generator.web.session_manager import SessionManager
from cantonese_anki_generator.web.session_models import TermAlignment, AlignmentSession
from cantonese_anki_generator.web.audio_extractor import AudioExtractor


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = create_app()
    app.config['TESTING'] = True
    
    # Create temporary directories for testing
    temp_dir = tempfile.mkdtemp()
    session_dir = os.path.join(temp_dir, 'sessions')
    audio_dir = os.path.join(temp_dir, 'audio_segments')
    
    # Initialize session manager and audio extractor
    session_manager = SessionManager(storage_dir=session_dir)
    audio_extractor = AudioExtractor(temp_dir=audio_dir)
    
    app.config['SESSION_MANAGER'] = session_manager
    app.config['AUDIO_EXTRACTOR'] = audio_extractor
    
    yield app
    
    # Cleanup
    import shutil
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def sample_session(app):
    """Create a sample session for testing."""
    session_manager = app.config['SESSION_MANAGER']
    
    # Create sample terms
    terms = [
        TermAlignment(
            term_id='term_0_hello',
            english='hello',
            cantonese='你好',
            start_time=0.0,
            end_time=1.5,
            original_start=0.0,
            original_end=1.5,
            is_manually_adjusted=False,
            confidence_score=0.95,
            audio_segment_url='/api/audio/test_session/term_0_hello'
        ),
        TermAlignment(
            term_id='term_1_goodbye',
            english='goodbye',
            cantonese='再見',
            start_time=2.0,
            end_time=3.5,
            original_start=2.0,
            original_end=3.5,
            is_manually_adjusted=False,
            confidence_score=0.88,
            audio_segment_url='/api/audio/test_session/term_1_goodbye'
        ),
        TermAlignment(
            term_id='term_2_thanks',
            english='thanks',
            cantonese='多謝',
            start_time=4.0,
            end_time=5.0,
            original_start=4.0,
            original_end=5.0,
            is_manually_adjusted=False,
            confidence_score=0.92,
            audio_segment_url='/api/audio/test_session/term_2_thanks'
        )
    ]
    
    # Create session
    session_id = session_manager.create_session(
        doc_url='https://docs.google.com/document/d/test123',
        audio_file_path='/tmp/test_audio.wav',
        terms=terms,
        audio_duration=10.0
    )
    
    return session_id


class TestGetSession:
    """Test GET /api/session/<session_id> endpoint."""
    
    def test_get_existing_session(self, client, sample_session):
        """Test retrieving an existing session."""
        response = client.get(f'/api/session/{sample_session}')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['success'] is True
        assert 'data' in data
        
        session_data = data['data']
        assert session_data['session_id'] == sample_session
        assert session_data['audio_duration'] == 10.0
        assert session_data['status'] == 'ready'
        assert len(session_data['terms']) == 3
        assert session_data['total_terms'] == 3
        assert session_data['manually_adjusted_count'] == 0
        
        # Check first term
        first_term = session_data['terms'][0]
        assert first_term['term_id'] == 'term_0_hello'
        assert first_term['english'] == 'hello'
        assert first_term['cantonese'] == '你好'
        assert first_term['start_time'] == 0.0
        assert first_term['end_time'] == 1.5
        assert first_term['is_manually_adjusted'] is False
        assert first_term['confidence_score'] == 0.95
        assert f'/api/audio/{sample_session}/term_0_hello' in first_term['audio_segment_url']
    
    def test_get_nonexistent_session(self, client):
        """Test retrieving a non-existent session."""
        response = client.get('/api/session/nonexistent_session_id')
        
        assert response.status_code == 404
        data = response.get_json()
        
        assert data['success'] is False
        assert 'not found' in data['error'].lower()
    
    def test_get_session_includes_all_fields(self, client, sample_session):
        """Test that all required fields are included in response."""
        response = client.get(f'/api/session/{sample_session}')
        data = response.get_json()
        
        session_data = data['data']
        required_fields = [
            'session_id', 'doc_url', 'audio_file_path', 'audio_duration',
            'status', 'created_at', 'last_modified', 'terms', 'total_terms',
            'manually_adjusted_count'
        ]
        
        for field in required_fields:
            assert field in session_data, f"Missing field: {field}"
        
        # Check term fields
        term = session_data['terms'][0]
        term_fields = [
            'term_id', 'english', 'cantonese', 'start_time', 'end_time',
            'original_start', 'original_end', 'is_manually_adjusted',
            'confidence_score', 'audio_segment_url'
        ]
        
        for field in term_fields:
            assert field in term, f"Missing term field: {field}"


class TestUpdateSession:
    """Test POST /api/session/<session_id>/update endpoint."""
    
    def test_update_boundaries_success(self, client, sample_session):
        """Test successfully updating term boundaries."""
        update_data = {
            'term_id': 'term_0_hello',
            'start_time': 0.2,
            'end_time': 1.3
        }
        
        response = client.post(
            f'/api/session/{sample_session}/update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['success'] is True
        assert 'Boundaries updated successfully' in data['message']
        
        term_data = data['data']
        assert term_data['term_id'] == 'term_0_hello'
        assert term_data['start_time'] == 0.2
        assert term_data['end_time'] == 1.3
        assert term_data['is_manually_adjusted'] is True
    
    def test_update_missing_term_id(self, client, sample_session):
        """Test update fails when term_id is missing."""
        update_data = {
            'start_time': 0.2,
            'end_time': 1.3
        }
        
        response = client.post(
            f'/api/session/{sample_session}/update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'term_id is required' in data['error']
    
    def test_update_missing_times(self, client, sample_session):
        """Test update fails when times are missing."""
        update_data = {
            'term_id': 'term_0_hello'
        }
        
        response = client.post(
            f'/api/session/{sample_session}/update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'start_time and end_time are required' in data['error']
    
    def test_update_invalid_time_values(self, client, sample_session):
        """Test update fails with invalid time values."""
        update_data = {
            'term_id': 'term_0_hello',
            'start_time': 'invalid',
            'end_time': 1.3
        }
        
        response = client.post(
            f'/api/session/{sample_session}/update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'numeric' in data['error'].lower()
    
    def test_update_negative_times(self, client, sample_session):
        """Test update fails with negative time values."""
        update_data = {
            'term_id': 'term_0_hello',
            'start_time': -0.5,
            'end_time': 1.3
        }
        
        response = client.post(
            f'/api/session/{sample_session}/update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'non-negative' in data['error'].lower()
    
    def test_update_start_after_end(self, client, sample_session):
        """Test update fails when start_time >= end_time."""
        update_data = {
            'term_id': 'term_0_hello',
            'start_time': 1.5,
            'end_time': 1.0
        }
        
        response = client.post(
            f'/api/session/{sample_session}/update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'start_time must be less than end_time' in data['error']
    
    def test_update_overlap_with_previous(self, client, sample_session):
        """Test update fails when overlapping with previous term."""
        # Try to update term_1 to overlap with term_0
        update_data = {
            'term_id': 'term_1_goodbye',
            'start_time': 1.0,  # term_0 ends at 1.5
            'end_time': 3.0
        }
        
        response = client.post(
            f'/api/session/{sample_session}/update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'overlaps with previous term' in data['error'].lower()
    
    def test_update_overlap_with_next(self, client, sample_session):
        """Test update fails when overlapping with next term."""
        # Try to update term_1 to overlap with term_2
        update_data = {
            'term_id': 'term_1_goodbye',
            'start_time': 2.5,
            'end_time': 4.5  # term_2 starts at 4.0
        }
        
        response = client.post(
            f'/api/session/{sample_session}/update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'overlaps with next term' in data['error'].lower()
    
    def test_update_exceeds_audio_duration(self, client, sample_session):
        """Test update fails when end time exceeds audio duration."""
        update_data = {
            'term_id': 'term_2_thanks',
            'start_time': 4.0,
            'end_time': 15.0  # audio duration is 10.0
        }
        
        response = client.post(
            f'/api/session/{sample_session}/update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'exceeds audio duration' in data['error'].lower()
    
    def test_update_nonexistent_session(self, client):
        """Test update fails for non-existent session."""
        update_data = {
            'term_id': 'term_0_hello',
            'start_time': 0.2,
            'end_time': 1.3
        }
        
        response = client.post(
            '/api/session/nonexistent_session/update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'not found' in data['error'].lower()
    
    def test_update_nonexistent_term(self, client, sample_session):
        """Test update fails for non-existent term."""
        update_data = {
            'term_id': 'nonexistent_term',
            'start_time': 0.2,
            'end_time': 1.3
        }
        
        response = client.post(
            f'/api/session/{sample_session}/update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'Term not found' in data['error']


class TestGetAudioSegment:
    """Test GET /api/audio/<session_id>/<term_id> endpoint."""
    
    def test_get_audio_nonexistent_session(self, client):
        """Test audio retrieval fails for non-existent session."""
        response = client.get('/api/audio/nonexistent_session/term_0_hello')
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'Session not found' in data['error']
    
    def test_get_audio_nonexistent_term(self, client, sample_session):
        """Test audio retrieval fails for non-existent term."""
        response = client.get(f'/api/audio/{sample_session}/nonexistent_term')
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'Term not found' in data['error']
    
    def test_get_audio_missing_file(self, client, sample_session):
        """Test audio retrieval fails when audio file doesn't exist."""
        # The audio file won't exist since we didn't create actual audio segments
        response = client.get(f'/api/audio/{sample_session}/term_0_hello')
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'Audio segment not found' in data['error']


class TestResetTerm:
    """Test POST /api/session/<session_id>/reset/<term_id> endpoint."""
    
    def test_reset_manually_adjusted_term(self, client, sample_session, app):
        """Test resetting a manually adjusted term to original boundaries."""
        session_manager = app.config['SESSION_MANAGER']
        
        # First, manually adjust a term
        update_data = {
            'term_id': 'term_0_hello',
            'start_time': 0.3,
            'end_time': 1.2
        }
        
        client.post(
            f'/api/session/{sample_session}/update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        # Verify term is manually adjusted
        session = session_manager.get_session(sample_session)
        term = next(t for t in session.terms if t.term_id == 'term_0_hello')
        assert term.is_manually_adjusted is True
        assert term.start_time == 0.3
        assert term.end_time == 1.2
        
        # Now reset the term
        response = client.post(f'/api/session/{sample_session}/reset/term_0_hello')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['success'] is True
        assert 'reset to original alignment' in data['message'].lower()
        
        term_data = data['data']
        assert term_data['term_id'] == 'term_0_hello'
        assert term_data['start_time'] == 0.0  # Original start
        assert term_data['end_time'] == 1.5  # Original end
        assert term_data['is_manually_adjusted'] is False
        
        # Verify in session
        session = session_manager.get_session(sample_session)
        term = next(t for t in session.terms if t.term_id == 'term_0_hello')
        assert term.is_manually_adjusted is False
        assert term.start_time == 0.0
        assert term.end_time == 1.5
    
    def test_reset_unadjusted_term(self, client, sample_session, app):
        """Test resetting a term that hasn't been manually adjusted."""
        session_manager = app.config['SESSION_MANAGER']
        
        # Reset a term that hasn't been adjusted
        response = client.post(f'/api/session/{sample_session}/reset/term_1_goodbye')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['success'] is True
        
        # Verify boundaries remain the same
        session = session_manager.get_session(sample_session)
        term = next(t for t in session.terms if t.term_id == 'term_1_goodbye')
        assert term.is_manually_adjusted is False
        assert term.start_time == 2.0
        assert term.end_time == 3.5
    
    def test_reset_nonexistent_session(self, client):
        """Test reset fails for non-existent session."""
        response = client.post('/api/session/nonexistent_session/reset/term_0_hello')
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'Session not found' in data['error']
    
    def test_reset_nonexistent_term(self, client, sample_session):
        """Test reset fails for non-existent term."""
        response = client.post(f'/api/session/{sample_session}/reset/nonexistent_term')
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'Term not found' in data['error']


class TestResetAllTerms:
    """Test POST /api/session/<session_id>/reset-all endpoint."""
    
    def test_reset_all_manually_adjusted_terms(self, client, sample_session, app):
        """Test resetting all manually adjusted terms."""
        session_manager = app.config['SESSION_MANAGER']
        
        # Manually adjust multiple terms
        updates = [
            {'term_id': 'term_0_hello', 'start_time': 0.3, 'end_time': 1.2},
            {'term_id': 'term_1_goodbye', 'start_time': 2.2, 'end_time': 3.3},
            {'term_id': 'term_2_thanks', 'start_time': 4.1, 'end_time': 4.9}
        ]
        
        for update_data in updates:
            client.post(
                f'/api/session/{sample_session}/update',
                data=json.dumps(update_data),
                content_type='application/json'
            )
        
        # Verify all terms are manually adjusted
        session = session_manager.get_session(sample_session)
        adjusted_count = sum(1 for t in session.terms if t.is_manually_adjusted)
        assert adjusted_count == 3
        
        # Reset all terms
        response = client.post(f'/api/session/{sample_session}/reset-all')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['success'] is True
        assert 'All' in data['message']
        assert 'reset to original alignment' in data['message'].lower()
        
        result_data = data['data']
        assert result_data['session_id'] == sample_session
        assert result_data['reset_count'] == 3
        assert result_data['total_terms'] == 3
        
        # Verify all terms are reset
        session = session_manager.get_session(sample_session)
        for term in session.terms:
            assert term.is_manually_adjusted is False
            assert term.start_time == term.original_start
            assert term.end_time == term.original_end
    
    def test_reset_all_with_no_adjustments(self, client, sample_session, app):
        """Test reset all when no terms have been adjusted."""
        session_manager = app.config['SESSION_MANAGER']
        
        # Verify no terms are adjusted
        session = session_manager.get_session(sample_session)
        adjusted_count = sum(1 for t in session.terms if t.is_manually_adjusted)
        assert adjusted_count == 0
        
        # Reset all terms
        response = client.post(f'/api/session/{sample_session}/reset-all')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['success'] is True
        result_data = data['data']
        assert result_data['reset_count'] == 0
        assert result_data['total_terms'] == 3
    
    def test_reset_all_with_partial_adjustments(self, client, sample_session, app):
        """Test reset all when only some terms have been adjusted."""
        session_manager = app.config['SESSION_MANAGER']
        
        # Manually adjust only two terms
        updates = [
            {'term_id': 'term_0_hello', 'start_time': 0.3, 'end_time': 1.2},
            {'term_id': 'term_2_thanks', 'start_time': 4.1, 'end_time': 4.9}
        ]
        
        for update_data in updates:
            client.post(
                f'/api/session/{sample_session}/update',
                data=json.dumps(update_data),
                content_type='application/json'
            )
        
        # Verify two terms are manually adjusted
        session = session_manager.get_session(sample_session)
        adjusted_count = sum(1 for t in session.terms if t.is_manually_adjusted)
        assert adjusted_count == 2
        
        # Reset all terms
        response = client.post(f'/api/session/{sample_session}/reset-all')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['success'] is True
        result_data = data['data']
        assert result_data['reset_count'] == 2
        assert result_data['total_terms'] == 3
        
        # Verify all terms are reset
        session = session_manager.get_session(sample_session)
        for term in session.terms:
            assert term.is_manually_adjusted is False
            assert term.start_time == term.original_start
            assert term.end_time == term.original_end
    
    def test_reset_all_nonexistent_session(self, client):
        """Test reset all fails for non-existent session."""
        response = client.post('/api/session/nonexistent_session/reset-all')
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'Session not found' in data['error']


def test_generate_anki_package_endpoint_exists(client):
    """Test that the generate endpoint exists and returns proper error for missing session."""
    response = client.post('/api/session/nonexistent-session/generate')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'not found' in data['error'].lower()


def test_generation_progress_endpoint_exists(client):
    """Test that the progress endpoint exists."""
    response = client.get('/api/session/test-session/generate/progress')
    # Should return 404 if no generation in progress
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['success'] is False


def test_download_endpoint_exists(client):
    """Test that the download endpoint exists."""
    response = client.get('/api/download/test-session/test-file.apkg')
    # Should return 404 if file doesn't exist
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['success'] is False

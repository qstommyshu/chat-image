"""
Unit tests for app.models.session module.

This module contains comprehensive tests for CrawlSession and SessionManager classes,
including concurrency, threading safety, and edge cases.
"""

import pytest
import queue
import threading
import time
import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.session import CrawlSession, SessionManager


class TestCrawlSession:
    """Test cases for CrawlSession class."""
    
    def test_init_creates_session_with_correct_attributes(self):
        """Test that CrawlSession initializes with correct default values."""
        session_id = "test-session-123"
        url = "https://example.com"
        limit = 10
        
        session = CrawlSession(session_id, url, limit)
        
        assert session.session_id == session_id
        assert session.url == url
        assert session.limit == limit
        assert session.status == "initializing"
        assert isinstance(session.messages, queue.Queue)
        assert session.total_images == 0
        assert session.total_pages == 0
        assert session.error is None
        assert session.completed is False
        assert session.image_stats == {}
    
    def test_add_message_adds_to_queue(self):
        """Test that add_message properly adds messages to the queue."""
        session = CrawlSession("test", "https://example.com", 5)
        
        message_type = "status"
        data = {"progress": 50, "message": "Processing..."}
        
        session.add_message(message_type, data)
        
        # Verify message was added to queue
        assert not session.messages.empty()
        
        # Get the message and verify its structure
        message = session.messages.get_nowait()
        assert message["type"] == message_type
        assert message["data"] == data
        assert "timestamp" in message
        assert isinstance(message["timestamp"], str)
        
        # Verify timestamp is a valid ISO format
        datetime.fromisoformat(message["timestamp"])
    
    def test_add_multiple_messages_preserves_order(self):
        """Test that multiple messages are added in correct order."""
        session = CrawlSession("test", "https://example.com", 5)
        
        messages_to_add = [
            ("status", {"step": 1}),
            ("progress", {"step": 2}),
            ("completed", {"step": 3})
        ]
        
        for msg_type, data in messages_to_add:
            session.add_message(msg_type, data)
        
        # Verify all messages are in queue
        assert session.messages.qsize() == 3
        
        # Verify order is preserved (FIFO)
        for i, (expected_type, expected_data) in enumerate(messages_to_add):
            message = session.messages.get_nowait()
            assert message["type"] == expected_type
            assert message["data"] == expected_data
    
    def test_session_attributes_can_be_modified(self):
        """Test that session attributes can be updated after initialization."""
        session = CrawlSession("test", "https://example.com", 5)
        
        # Update various attributes
        session.status = "crawling"
        session.total_images = 25
        session.total_pages = 3
        session.error = "Network timeout"
        session.completed = True
        session.image_stats = {"jpg": 10, "png": 15}
        
        # Verify updates
        assert session.status == "crawling"
        assert session.total_images == 25
        assert session.total_pages == 3
        assert session.error == "Network timeout"
        assert session.completed is True
        assert session.image_stats == {"jpg": 10, "png": 15}


class TestSessionManager:
    """Test cases for SessionManager class."""
    
    def test_init_creates_empty_manager(self):
        """Test that SessionManager initializes with empty state."""
        manager = SessionManager(max_concurrent_crawls=5)
        
        assert manager.crawl_sessions == {}
        assert manager.session_namespaces == {}
        assert manager.max_concurrent_crawls == 5
        assert isinstance(manager.crawl_lock, threading.Lock)
    
    @patch('app.config.Config')
    def test_init_uses_config_default_when_no_max_specified(self, mock_config):
        """Test that SessionManager uses Config.MAX_CONCURRENT_CRAWLS as default."""
        mock_config.MAX_CONCURRENT_CRAWLS = 3
        
        manager = SessionManager()
        
        assert manager.max_concurrent_crawls == 3
    
    def test_create_session_success(self):
        """Test successful session creation."""
        manager = SessionManager(max_concurrent_crawls=2)
        
        session, error = manager.create_session(
            session_id="test-123",
            url="https://example.com",
            limit=10,
            domain="example.com"
        )
        
        assert error is None
        assert session is not None
        assert isinstance(session, CrawlSession)
        assert session.session_id == "test-123"
        assert session.url == "https://example.com"
        assert session.limit == 10
        
        # Verify session is stored in manager
        assert "test-123" in manager.crawl_sessions
        assert manager.crawl_sessions["test-123"] == session
    
    def test_create_session_exceeds_concurrent_limit(self):
        """Test that session creation fails when concurrent limit is exceeded."""
        manager = SessionManager(max_concurrent_crawls=2)
        
        # Create two active sessions
        session1, _ = manager.create_session("s1", "https://example1.com", 5, "example1.com")
        session2, _ = manager.create_session("s2", "https://example2.com", 5, "example2.com")
        
        # Set them to active status
        session1.status = "crawling"
        session2.status = "processing"
        
        # Try to create a third session - should fail
        session3, error = manager.create_session("s3", "https://example3.com", 5, "example3.com")
        
        assert session3 is None
        assert error is not None
        assert "Maximum 2 concurrent crawls allowed" in error
        assert "s3" not in manager.crawl_sessions
    
    def test_create_session_allows_if_existing_sessions_completed(self):
        """Test that completed sessions don't count toward concurrent limit."""
        manager = SessionManager(max_concurrent_crawls=1)
        
        # Create and complete a session
        session1, _ = manager.create_session("s1", "https://example1.com", 5, "example1.com")
        session1.status = "completed"
        
        # Should be able to create another session
        session2, error = manager.create_session("s2", "https://example2.com", 5, "example2.com")
        
        assert error is None
        assert session2 is not None
        assert len(manager.crawl_sessions) == 2
    
    def test_get_session_existing(self):
        """Test retrieving an existing session."""
        manager = SessionManager()
        
        # Create a session
        original_session, _ = manager.create_session("test-456", "https://test.com", 3, "test.com")
        
        # Retrieve it
        retrieved_session = manager.get_session("test-456")
        
        assert retrieved_session is not None
        assert retrieved_session == original_session
        assert retrieved_session.session_id == "test-456"
    
    def test_get_session_nonexistent(self):
        """Test retrieving a non-existent session returns None."""
        manager = SessionManager()
        
        session = manager.get_session("nonexistent-session")
        
        assert session is None
    
    def test_set_and_get_namespace(self):
        """Test setting and getting Pinecone namespaces."""
        manager = SessionManager()
        
        session_id = "test-namespace"
        namespace = "user-123-crawl"
        
        # Set namespace
        manager.set_namespace(session_id, namespace)
        
        # Verify it's stored
        assert session_id in manager.session_namespaces
        assert manager.session_namespaces[session_id] == namespace
        
        # Retrieve namespace
        retrieved_namespace = manager.get_namespace(session_id)
        assert retrieved_namespace == namespace
    
    def test_get_namespace_nonexistent(self):
        """Test getting namespace for non-existent session returns None."""
        manager = SessionManager()
        
        namespace = manager.get_namespace("nonexistent-session")
        
        assert namespace is None
    
    def test_concurrent_session_creation_thread_safety(self):
        """Test that concurrent session creation is thread-safe."""
        manager = SessionManager(max_concurrent_crawls=3)
        
        # Pre-create some active sessions to test the limit
        for i in range(3):
            session, _ = manager.create_session(f"pre-{i}", f"https://pre{i}.com", 5, f"pre{i}.com")
            session.status = "crawling"  # Set to active status
        
        results = []
        errors = []
        
        def create_session_worker(session_id):
            try:
                session, error = manager.create_session(
                    f"session-{session_id}",
                    f"https://example{session_id}.com",
                    5,
                    f"example{session_id}.com"
                )
                results.append((session_id, session, error))
            except Exception as e:
                errors.append((session_id, e))
        
        # Try to create 3 more sessions concurrently (should all fail due to limit)
        threads = []
        for i in range(3):
            thread = threading.Thread(target=create_session_worker, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no exceptions occurred
        assert len(errors) == 0
        
        # Verify results
        assert len(results) == 3
        
        # All new sessions should fail due to limit
        failed_sessions = [r for r in results if r[1] is None]
        successful_sessions = [r for r in results if r[1] is not None]
        
        assert len(failed_sessions) == 3  # All should fail
        assert len(successful_sessions) == 0
        
        # Verify original sessions are still there
        assert len(manager.crawl_sessions) == 3
    
    def test_active_session_status_counting(self):
        """Test that only active statuses count toward concurrent limit."""
        manager = SessionManager(max_concurrent_crawls=2)
        
        # Create sessions with different statuses
        session1, _ = manager.create_session("s1", "https://example1.com", 5, "example1.com")
        session2, _ = manager.create_session("s2", "https://example2.com", 5, "example2.com")
        
        # Set various statuses
        session1.status = "completed"  # Not active
        session2.status = "error"      # Not active
        
        # Should be able to create more sessions
        session3, error3 = manager.create_session("s3", "https://example3.com", 5, "example3.com")
        session4, error4 = manager.create_session("s4", "https://example4.com", 5, "example4.com")
        
        assert error3 is None
        assert error4 is None
        assert session3 is not None
        assert session4 is not None
        
        # Now set active statuses
        session3.status = "crawling"     # Active
        session4.status = "processing"   # Active
        
        # Should not be able to create another session
        session5, error5 = manager.create_session("s5", "https://example5.com", 5, "example5.com")
        
        assert session5 is None
        assert error5 is not None
    
    def test_namespace_operations_with_same_session_id(self):
        """Test namespace operations when session_id is reused."""
        manager = SessionManager()
        
        session_id = "reused-session"
        
        # Set initial namespace
        manager.set_namespace(session_id, "namespace-1")
        assert manager.get_namespace(session_id) == "namespace-1"
        
        # Override with new namespace
        manager.set_namespace(session_id, "namespace-2")
        assert manager.get_namespace(session_id) == "namespace-2"
        
        # Verify only one entry exists
        assert len(manager.session_namespaces) == 1


class TestSessionManagerIntegration:
    """Integration tests for SessionManager with real threading scenarios."""
    
    def test_realistic_crawl_workflow(self):
        """Test a realistic workflow with session lifecycle."""
        manager = SessionManager(max_concurrent_crawls=2)
        
        # Create a session
        session, error = manager.create_session(
            "workflow-test",
            "https://example.com",
            10,
            "example.com"
        )
        
        assert error is None
        assert session.status == "initializing"
        
        # Set namespace
        manager.set_namespace("workflow-test", "user-123-crawl")
        
        # Simulate workflow progression
        session.status = "crawling"
        session.add_message("status", {"message": "Starting crawl"})
        
        session.status = "processing"
        session.total_pages = 5
        session.add_message("progress", {"pages": 5})
        
        session.status = "indexing"
        session.total_images = 50
        session.add_message("progress", {"images": 50})
        
        session.status = "completed"
        session.completed = True
        session.image_stats = {"jpg": 30, "png": 20}
        session.add_message("completed", {"total_images": 50})
        
        # Verify final state
        retrieved_session = manager.get_session("workflow-test")
        assert retrieved_session.completed is True
        assert retrieved_session.total_images == 50
        assert retrieved_session.total_pages == 5
        assert retrieved_session.status == "completed"
        
        # Verify namespace
        assert manager.get_namespace("workflow-test") == "user-123-crawl"
        
        # Verify messages were queued
        assert retrieved_session.messages.qsize() == 4
    
    def test_error_handling_workflow(self):
        """Test workflow when errors occur."""
        manager = SessionManager(max_concurrent_crawls=1)
        
        # Create session
        session, error = manager.create_session(
            "error-test",
            "https://invalid-url.com",
            5,
            "invalid-url.com"
        )
        
        assert error is None
        
        # Simulate error during crawling
        session.status = "crawling"
        session.add_message("status", {"message": "Crawling started"})
        
        # Error occurs
        session.status = "error"
        session.error = "Failed to connect to host"
        session.add_message("error", {"message": "Failed to connect to host"})
        
        # Verify error state
        retrieved_session = manager.get_session("error-test")
        assert retrieved_session.status == "error"
        assert retrieved_session.error == "Failed to connect to host"
        assert retrieved_session.completed is False
        
        # Verify we can create new session since this one is in error state
        new_session, new_error = manager.create_session(
            "recovery-test",
            "https://example.com",
            5,
            "example.com"
        )
        
        assert new_error is None
        assert new_session is not None


# Test fixtures and utilities
@pytest.fixture
def clean_session_manager():
    """Provide a fresh SessionManager instance for each test."""
    return SessionManager(max_concurrent_crawls=3)


@pytest.fixture
def sample_session():
    """Provide a sample CrawlSession for testing."""
    return CrawlSession("sample-123", "https://test.com", 5)


# Additional parametrized tests
@pytest.mark.parametrize("status", ["crawling", "processing", "indexing"])
def test_active_statuses_count_toward_limit(status):
    """Test that various active statuses count toward concurrent limit."""
    manager = SessionManager(max_concurrent_crawls=1)
    
    # Create and activate session
    session, _ = manager.create_session("test", "https://example.com", 5, "example.com")
    session.status = status
    
    # Try to create another session - should fail
    new_session, error = manager.create_session("test2", "https://example2.com", 5, "example2.com")
    
    assert new_session is None
    assert error is not None


@pytest.mark.parametrize("status", ["completed", "error", "cancelled"])
def test_inactive_statuses_dont_count_toward_limit(status):
    """Test that inactive statuses don't count toward concurrent limit."""
    manager = SessionManager(max_concurrent_crawls=1)
    
    # Create and set inactive session
    session, _ = manager.create_session("test", "https://example.com", 5, "example.com")
    session.status = status
    
    # Should be able to create another session
    new_session, error = manager.create_session("test2", "https://example2.com", 5, "example2.com")
    
    assert new_session is not None
    assert error is None


@pytest.mark.parametrize("limit", [1, 5, 10, 100])
def test_session_creation_with_various_limits(limit):
    """Test session creation with different crawl limits."""
    manager = SessionManager()
    
    session, error = manager.create_session(
        f"test-{limit}",
        "https://example.com",
        limit,
        "example.com"
    )
    
    assert error is None
    assert session.limit == limit 
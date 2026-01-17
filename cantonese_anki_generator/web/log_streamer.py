"""
Real-time log streaming for processing feedback.

Provides Server-Sent Events (SSE) endpoint for streaming processing logs to the frontend.
"""

import logging
import queue
import threading
from typing import Dict, Optional
from flask import Response
import time


class LogStreamer:
    """
    Manages log streaming to multiple clients via Server-Sent Events.
    
    Captures log messages and broadcasts them to connected clients.
    """
    
    def __init__(self):
        """Initialize the log streamer."""
        self.clients: Dict[str, queue.Queue] = {}
        self.lock = threading.Lock()
        
    def add_client(self, client_id: str) -> queue.Queue:
        """
        Add a new client for log streaming.
        
        Args:
            client_id: Unique identifier for the client
            
        Returns:
            Queue for sending messages to this client
        """
        with self.lock:
            message_queue = queue.Queue(maxsize=100)
            self.clients[client_id] = message_queue
            return message_queue
    
    def remove_client(self, client_id: str):
        """
        Remove a client from log streaming.
        
        Args:
            client_id: Client identifier to remove
        """
        with self.lock:
            if client_id in self.clients:
                del self.clients[client_id]
    
    def broadcast_log(self, message: str, level: str = "info", session_id: Optional[str] = None):
        """
        Broadcast a log message to all connected clients.
        
        Args:
            message: Log message to broadcast
            level: Log level (info, success, warning, error, stage)
            session_id: Optional session ID to filter clients
        """
        timestamp = time.strftime("%H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        
        with self.lock:
            for client_id, message_queue in list(self.clients.items()):
                try:
                    # Non-blocking put with timeout
                    message_queue.put(log_entry, block=False)
                except queue.Full:
                    # Queue is full, skip this message for this client
                    pass
    
    def generate_stream(self, client_id: str):
        """
        Generate Server-Sent Events stream for a client.
        
        Args:
            client_id: Client identifier
            
        Yields:
            SSE-formatted messages
        """
        message_queue = self.add_client(client_id)
        
        try:
            # Send initial connection message
            yield f"data: {{'type': 'connected', 'message': 'Log stream connected'}}\n\n"
            
            while True:
                try:
                    # Wait for messages with timeout
                    log_entry = message_queue.get(timeout=30)
                    
                    # Format as SSE
                    import json
                    data = json.dumps(log_entry)
                    yield f"data: {data}\n\n"
                    
                except queue.Empty:
                    # Send keepalive ping
                    yield f": keepalive\n\n"
                    
        except GeneratorExit:
            # Client disconnected
            self.remove_client(client_id)


# Global log streamer instance
log_streamer = LogStreamer()


class StreamingLogHandler(logging.Handler):
    """
    Custom logging handler that streams logs to connected clients.
    """
    
    def __init__(self, streamer: LogStreamer):
        """
        Initialize the streaming log handler.
        
        Args:
            streamer: LogStreamer instance to use
        """
        super().__init__()
        self.streamer = streamer
        
    def emit(self, record: logging.LogRecord):
        """
        Emit a log record to the streamer.
        
        Args:
            record: Log record to emit
        """
        try:
            message = self.format(record)
            
            # Map log levels to frontend levels
            level_map = {
                logging.DEBUG: "info",
                logging.INFO: "info",
                logging.WARNING: "warning",
                logging.ERROR: "error",
                logging.CRITICAL: "error"
            }
            
            level = level_map.get(record.levelno, "info")
            
            # Detect stage messages (messages starting with "Stage" or containing "...")
            if "Stage" in message or message.endswith("..."):
                level = "stage"
            elif "✓" in message or "complete" in message.lower() or "success" in message.lower():
                level = "success"
            
            self.streamer.broadcast_log(message, level)
            
        except Exception:
            self.handleError(record)


def setup_log_streaming(app):
    """
    Set up log streaming for the Flask app.
    
    Args:
        app: Flask application instance
    """
    # Add streaming handler to processing controller logger
    from cantonese_anki_generator.web.processing_controller import logger as controller_logger
    
    # Set logger level to INFO to ensure messages are captured
    controller_logger.setLevel(logging.INFO)
    
    streaming_handler = StreamingLogHandler(log_streamer)
    streaming_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(message)s')
    streaming_handler.setFormatter(formatter)
    
    controller_logger.addHandler(streaming_handler)
    
    # Also add to speech verification logger
    try:
        from cantonese_anki_generator.audio.speech_verification import logger as speech_logger
        speech_logger.setLevel(logging.INFO)
        speech_logger.addHandler(streaming_handler)
    except ImportError:
        pass

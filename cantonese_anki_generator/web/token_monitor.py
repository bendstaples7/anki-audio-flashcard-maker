"""
Background token monitoring for proactive OAuth token refresh.

This module provides a TokenMonitor class that runs as a background task
to periodically check token expiration and refresh tokens before they expire.
"""

import logging
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler

from ..processors.google_docs_auth import GoogleDocsAuthenticator


logger = logging.getLogger(__name__)


class TokenMonitor:
    """
    Background monitor for OAuth token health and automatic refresh.
    
    The TokenMonitor runs as a background task using APScheduler to periodically
    check if OAuth tokens are expiring soon and automatically refresh them to
    prevent authentication failures during user operations.
    """
    
    def __init__(self, authenticator: GoogleDocsAuthenticator, check_interval_hours: int = 6):
        """
        Initialize the token monitor.
        
        Args:
            authenticator: GoogleDocsAuthenticator instance to monitor
            check_interval_hours: How often to check token status (default: 6 hours)
        """
        self.authenticator = authenticator
        self.check_interval_hours = check_interval_hours
        self.scheduler: Optional[BackgroundScheduler] = None
        self._is_running = False
    
    def start(self) -> None:
        """
        Start the background token monitoring task.
        
        Initializes the APScheduler BackgroundScheduler and schedules periodic
        token checks. The scheduler runs as a daemon thread and won't block
        application shutdown.
        """
        if self._is_running:
            logger.warning("TokenMonitor is already running")
            return
        
        try:
            # Create background scheduler (daemon=True means it won't block shutdown)
            self.scheduler = BackgroundScheduler(daemon=True)
            
            # Schedule periodic token checks
            self.scheduler.add_job(
                func=self.check_and_refresh,
                trigger='interval',
                hours=self.check_interval_hours,
                id='token_refresh_monitor',
                name='OAuth Token Refresh Monitor',
                replace_existing=True
            )
            
            # Start the scheduler
            self.scheduler.start()
            self._is_running = True
            
            logger.info(
                f"TokenMonitor started - checking every {self.check_interval_hours} hours"
            )
            
            # Perform initial check immediately
            self.check_and_refresh()
            
        except Exception as e:
            logger.error(f"Failed to start TokenMonitor: {e}")
            self._is_running = False
    
    def stop(self) -> None:
        """
        Stop the background token monitoring task.
        
        Shuts down the APScheduler and cleans up resources. This method is
        safe to call multiple times.
        """
        if not self._is_running:
            logger.debug("TokenMonitor is not running")
            return
        
        try:
            if self.scheduler:
                self.scheduler.shutdown(wait=False)
                self.scheduler = None
            
            self._is_running = False
            logger.info("TokenMonitor stopped")
            
        except Exception as e:
            logger.error(f"Error stopping TokenMonitor: {e}")
    
    def check_and_refresh(self) -> None:
        """
        Check token expiration and refresh if needed.
        
        This method is called periodically by the scheduler. It checks if tokens
        are expiring within 24 hours and attempts automatic refresh if needed.
        
        The method handles errors gracefully and logs warnings when refresh fails,
        but does not raise exceptions to avoid disrupting the scheduler.
        """
        try:
            logger.debug("TokenMonitor: Checking token status")
            
            # Get current token status
            status = self.authenticator.get_token_status()
            
            # Log current status
            if not status['valid']:
                logger.warning("TokenMonitor: No valid tokens found")
                return
            
            if status['expires_at']:
                logger.debug(f"TokenMonitor: Token expires at {status['expires_at']}")
            
            # Check if token is expiring soon (within 24 hours)
            if self.authenticator.is_token_expiring_soon(hours=24):
                logger.info("TokenMonitor: Token expiring soon, attempting refresh")
                
                # Attempt refresh
                if self.authenticator.refresh_tokens():
                    logger.info("TokenMonitor: Token refresh successful")
                else:
                    logger.warning(
                        "TokenMonitor: Token refresh failed - user intervention may be required"
                    )
            else:
                logger.debug("TokenMonitor: Token is valid and not expiring soon")
        
        except Exception as e:
            # Log error but don't raise - we don't want to crash the scheduler
            logger.error(f"TokenMonitor: Error during check_and_refresh: {e}")
    
    @property
    def is_running(self) -> bool:
        """Check if the monitor is currently running."""
        return self._is_running

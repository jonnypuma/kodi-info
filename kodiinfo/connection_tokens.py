#!/usr/bin/env python3
"""
Connection Tokens Module

In-memory token store for managing temporary Kodi connection credentials.
Tokens expire after 7 days of inactivity.
"""

import threading
import uuid
from typing import Dict, Optional
from datetime import datetime, timedelta


class TokenStore:
    """Thread-safe in-memory token store"""
    
    def __init__(self):
        self._store: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._expiry_days = 7
    
    def issue_token(self, conn: dict) -> str:
        """
        Store a connection and return a unique token
        
        Args:
            conn: Connection dictionary with host, username, password, etc.
        
        Returns:
            Unique token (UUID hex string)
        """
        token = uuid.uuid4().hex
        
        with self._lock:
            self._store[token] = {
                "connection": conn,
                "created_at": datetime.now(),
                "last_used": datetime.now(),
            }
        
        return token
    
    def get_connection(self, token: str) -> Optional[dict]:
        """
        Retrieve connection by token
        
        Args:
            token: Token string
        
        Returns:
            Connection dict or None if not found/expired
        """
        with self._lock:
            self._cleanup_expired()
            
            if token not in self._store:
                return None
            
            entry = self._store[token]
            
            # Check if expired
            if self._is_expired(entry):
                del self._store[token]
                return None
            
            # Update last_used
            entry["last_used"] = datetime.now()
            
            return entry["connection"]
    
    def touch(self, token: str) -> bool:
        """
        Update the last_used timestamp for a token
        
        Args:
            token: Token string
        
        Returns:
            True if token exists and was touched, False otherwise
        """
        with self._lock:
            if token in self._store:
                entry = self._store[token]
                if not self._is_expired(entry):
                    entry["last_used"] = datetime.now()
                    return True
                else:
                    del self._store[token]
        
        return False
    
    def _is_expired(self, entry: Dict) -> bool:
        """Check if a token entry is expired"""
        expiry = entry["last_used"] + timedelta(days=self._expiry_days)
        return datetime.now() > expiry
    
    def _cleanup_expired(self):
        """Remove expired tokens (called during get_connection)"""
        expired = [
            token for token, entry in self._store.items()
            if self._is_expired(entry)
        ]
        for token in expired:
            del self._store[token]


# Global singleton instance
_token_store = TokenStore()


def issue_token(conn: dict) -> str:
    """
    Store a connection and return a unique token
    
    Args:
        conn: Connection dictionary
    
    Returns:
        Unique token string
    """
    return _token_store.issue_token(conn)


def get_connection(token: str) -> Optional[dict]:
    """
    Retrieve connection by token
    
    Args:
        token: Token string
    
    Returns:
        Connection dict or None if not found/expired
    """
    return _token_store.get_connection(token)


def touch(token: str) -> bool:
    """
    Update the last_used timestamp for a token
    
    Args:
        token: Token string
    
    Returns:
        True if token exists, False otherwise
    """
    return _token_store.touch(token)

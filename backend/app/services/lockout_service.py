import time
from typing import Dict, Tuple, Optional
import threading

class AccountLockoutService:
    """
    OWASP A07:2021 - Identification and Authentication Failures Defense.
    Tracks failed login attempts by (account + IP) to protect against credential stuffing
    while preventing account denial-of-service against legitimate users from other IPs.
    """

    def __init__(self, max_attempts: int = 10, lockout_duration_seconds: int = 900):
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_duration_seconds
        self._failed_attempts: Dict[str, int] = {}
        self._lockout_expiry: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _make_key(self, identifier: str, ip: Optional[str] = None) -> str:
        ident_clean = identifier.lower().strip()
        return f"{ident_clean}::{ip.strip()}" if ip else ident_clean

    def is_locked(self, identifier: str, ip: Optional[str] = None) -> Tuple[bool, int]:
        """
        Checks if an account/IP identifier is currently locked out.
        Returns: (is_locked, remaining_seconds)
        """
        key = self._make_key(identifier, ip)
        with self._lock:
            if key in self._lockout_expiry:
                remaining = int(self._lockout_expiry[key] - time.time())
                if remaining > 0:
                    return True, remaining
                else:
                    # Lockout expired
                    del self._lockout_expiry[key]
                    self._failed_attempts.pop(key, None)
            return False, 0

    def record_failed_attempt(self, identifier: str, ip: Optional[str] = None) -> Tuple[int, bool, int]:
        """
        Records a failed login attempt.
        Returns: (current_attempts, is_now_locked, lockout_seconds_remaining)
        """
        key = self._make_key(identifier, ip)
        with self._lock:
            current = self._failed_attempts.get(key, 0) + 1
            self._failed_attempts[key] = current

            if current >= self.max_attempts:
                self._lockout_expiry[key] = time.time() + self.lockout_duration
                return current, True, self.lockout_duration

            return current, False, 0

    def reset_attempts(self, identifier: str, ip: Optional[str] = None):
        """Resets failed attempt counters upon successful authentication."""
        key = self._make_key(identifier, ip)
        with self._lock:
            self._failed_attempts.pop(key, None)
            self._lockout_expiry.pop(key, None)


# Singleton instance
lockout_service = AccountLockoutService()

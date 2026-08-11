import html
import re
import os
from typing import Optional, Any, Dict, List

class InputSanitizer:
    """
    Centralized Input Sanitizer & Defensive Guard.
    Provides sanitization against XSS, Path Traversal, Null-Byte Injection,
    Control Character Abuse, and malformed medical domain values.
    """

    ALLOWED_BLOOD_GROUPS = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
    PHONE_REGEX = re.compile(r"^\+?[0-9\s\-()]{7,20}$")
    USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.@]{3,50}$")

    @classmethod
    def sanitize_text(cls, val: Optional[str], max_length: Optional[int] = None) -> Optional[str]:
        """
        Sanitizes text strings:
        - Strips null-bytes (\x00) and unprintable control characters
        - Neutralizes HTML tags and script injections via HTML-escaping
        - Trims leading/trailing whitespace
        - Truncates to max_length if specified
        """
        if val is None:
            return None

        if not isinstance(val, str):
            val = str(val)

        # 1. Strip null-bytes and dangerous ASCII control characters (0-31, except newline/tab)
        cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", val)

        # 2. Strip explicit <script> blocks and javascript: pseudo-protocols
        cleaned = re.sub(r"(?i)<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", "", cleaned)
        cleaned = re.sub(r"(?i)javascript:", "", cleaned)

        # 3. HTML-escape special characters (&, <, >, ", ')
        cleaned = html.escape(cleaned, quote=True).strip()

        # 4. Truncate if max_length is enforced
        if max_length and len(cleaned) > max_length:
            cleaned = cleaned[:max_length]

        return cleaned

    @classmethod
    def sanitize_filename(cls, name: Optional[str]) -> str:
        """
        Sanitizes filenames to prevent Path Traversal and filesystem exploitation:
        - Isolates pure basename (strips ../, ..\\)
        - Removes null-bytes and illegal characters
        - Replaces whitespace with underscores
        """
        if not name:
            return "unnamed_document.pdf"

        # Extract pure basename
        safe_name = os.path.basename(name.replace("\\", "/"))

        # Strip null bytes and control chars
        safe_name = re.sub(r"[\x00-\x1F\x7F]", "", safe_name)

        # Remove path traversal tokens
        safe_name = safe_name.replace("..", "").replace("/", "").replace("\\", "").strip()

        # Remove illegal file characters for Windows and POSIX
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", safe_name)

        return safe_name or "unnamed_document.pdf"

    @classmethod
    def sanitize_phone(cls, phone: Optional[str]) -> Optional[str]:
        """
        Sanitizes and validates phone numbers.
        """
        if not phone:
            return None

        cleaned = re.sub(r"[\x00-\x1F\x7F]", "", str(phone)).strip()
        if not cls.PHONE_REGEX.match(cleaned):
            raise ValueError(f"Invalid phone number format: '{phone}'. Must be 7-20 digits with optional + prefix.")

        # Normalize spaces and dashes
        return re.sub(r"\s+", "", cleaned)

    @classmethod
    def sanitize_blood_group(cls, bg: Optional[str]) -> Optional[str]:
        """
        Validates and standardizes clinical blood group notation.
        """
        if not bg:
            return None

        normalized = bg.strip().upper()
        if normalized not in cls.ALLOWED_BLOOD_GROUPS:
            raise ValueError(f"Invalid blood group: '{bg}'. Allowed values: {', '.join(sorted(cls.ALLOWED_BLOOD_GROUPS))}")

        return normalized

    @classmethod
    def sanitize_username(cls, username: Optional[str]) -> str:
        """
        Validates and sanitizes username strings.
        """
        if not username:
            raise ValueError("Username cannot be empty.")

        cleaned = username.strip()
        if not cls.USERNAME_REGEX.match(cleaned):
            raise ValueError("Username must be 3-50 characters containing only alphanumeric, underscores, hyphens, dots, or @.")

        return cleaned

sanitizer = InputSanitizer()

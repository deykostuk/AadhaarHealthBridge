import re
from typing import Optional

class PIIMasker:
    """
    Data Minimization & PII Masking Utility compliant with DPDP Act 2023 & UIDAI Guidelines.
    Prevents unintentional exposure of sensitive identifiers in logs, API responses, and reports.
    """

    @staticmethod
    def mask_aadhaar(aadhaar_number: Optional[str]) -> str:
        """
        Masks 12-digit Aadhaar number to display only the last 4 digits (UIDAI compliance).
        Example: '1234 5678 9012' -> 'XXXX-XXXX-9012'
        """
        if not aadhaar_number:
            return ""
        clean_num = re.sub(r"\D", "", str(aadhaar_number))
        if len(clean_num) != 12:
            return "XXXX-XXXX-XXXX"
        return f"XXXX-XXXX-{clean_num[-4:]}"

    @staticmethod
    def mask_phone(phone: Optional[str]) -> str:
        """
        Masks phone numbers preserving country code and last 4 digits.
        Example: '+919876543210' -> '+91******3210'
        """
        if not phone:
            return ""
        clean_phone = str(phone).strip()
        if len(clean_phone) <= 4:
            return "****"
        prefix = clean_phone[:3] if clean_phone.startswith("+") else clean_phone[:2]
        suffix = clean_phone[-4:]
        masked_middle = "*" * max(3, len(clean_phone) - len(prefix) - len(suffix))
        return f"{prefix}{masked_middle}{suffix}"

    @staticmethod
    def mask_email(email: Optional[str]) -> str:
        """
        Masks email addresses.
        Example: 'johndoe@example.com' -> 'j***e@example.com'
        """
        if not email or "@" not in email:
            return ""
        parts = email.split("@", 1)
        name, domain = parts[0], parts[1]
        if len(name) <= 2:
            masked_name = name[0] + "*"
        else:
            masked_name = name[0] + ("*" * (len(name) - 2)) + name[-1]
        return f"{masked_name}@{domain}"

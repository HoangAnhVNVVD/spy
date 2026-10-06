"""Privacy protection & data sanitization engine.

Protects user confidentiality before any data is written to local storage
or transmitted over the network.
"""

from __future__ import annotations

import re
from typing import List, Pattern, Tuple

from client.config import PrivacySettings


# Private browsing window title signatures across Edge, Chrome, Firefox, Brave, Opera (including Vietnamese & French)
PRIVATE_BROWSING_REGEX = re.compile(
    r"\b(inprivate|incognito|private browsing|private window|tor browser|ẩn danh|riêng tư)\b",
    re.IGNORECASE,
)


class PrivacyEngine:
    """Sanitizes process names and window titles according to privacy policies."""

    def __init__(self, settings: PrivacySettings):
        self.settings = settings
        self._ignored_set = {p.lower() for p in settings.ignored_processes}
        self._compiled_patterns: List[Pattern[str]] = []

        for pat in settings.redact_patterns:
            try:
                self._compiled_patterns.append(re.compile(pat))
            except re.error as e:
                print(f"[Privacy] Warning: Invalid redaction pattern '{pat}': {e}")

        # Precompile keyword patterns, handling symbols & word boundaries intelligently
        kw_patterns = []
        for kw in settings.redact_keywords:
            if not kw:
                continue
            escaped = re.escape(kw)
            prefix = r"\b" if kw[0].isalnum() else ""
            suffix = r"\b" if kw[-1].isalnum() else ""
            kw_patterns.append(rf"{prefix}{escaped}{suffix}")

        if kw_patterns:
            self._keywords_regex = re.compile("|".join(kw_patterns), re.IGNORECASE)
        else:
            self._keywords_regex = None

    def should_ignore_process(self, process_name: str) -> bool:
        """
        Check if process is in the ignored list.
        Comparison is case-insensitive.
        """
        if not self.settings.enabled:
            return False
        if not process_name:
            return False
        return process_name.lower() in self._ignored_set

    def sanitize_title(self, window_title: str, process_name: str) -> Tuple[str, bool]:
        """
        Sanitize window title.
        Returns (sanitized_title, was_redacted).
        """
        if not self.settings.enabled:
            return (window_title.strip() if window_title else "", False)

        if not window_title:
            return ("", False)

        was_redacted = False

        # 1. Total title masking mode
        if self.settings.mask_all_titles:
            return (f"[{process_name}]" if process_name else "[Protected App]", True)

        # 2. Private browsing detection
        if self.settings.mask_private_browsing and PRIVATE_BROWSING_REGEX.search(window_title):
            return ("[Private Browsing]", True)

        sanitized = window_title

        # 3. Pattern-based redaction first (structured credentials, tokens, credit cards, emails)
        for pattern in self._compiled_patterns:
            if pattern.search(sanitized):
                sanitized = pattern.sub(self.settings.replacement_text, sanitized)
                was_redacted = True

        # 4. Keyword-based redaction (isolated keywords)
        if self._keywords_regex and self._keywords_regex.search(sanitized):
            sanitized = self._keywords_regex.sub(self.settings.replacement_text, sanitized)
            was_redacted = True

        # Normalize whitespace
        sanitized = " ".join(sanitized.split())

        return (sanitized, was_redacted)

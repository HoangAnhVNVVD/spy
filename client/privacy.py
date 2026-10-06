from __future__ import annotations
import re
from typing import List, Pattern, Tuple
from client.config import PrivacySettings
PRIVATE_BROWSING_REGEX = re.compile('\\b(inprivate|incognito|private browsing|private window|tor browser|ẩn danh|riêng tư)\\b', re.IGNORECASE)

class PrivacyEngine:

    def __init__(self, settings: PrivacySettings):
        self.settings = settings
        self._ignored_set = {p.lower() for p in settings.ignored_processes}
        self._compiled_patterns: List[Pattern[str]] = []
        for pat in settings.redact_patterns:
            try:
                self._compiled_patterns.append(re.compile(pat))
            except re.error as e:
                print(f"[Privacy] Warning: Invalid redaction pattern '{pat}': {e}")
        kw_patterns = []
        for kw in settings.redact_keywords:
            if not kw:
                continue
            escaped = re.escape(kw)
            prefix = '\\b' if kw[0].isalnum() else ''
            suffix = '\\b' if kw[-1].isalnum() else ''
            kw_patterns.append(f'{prefix}{escaped}{suffix}')
        if kw_patterns:
            self._keywords_regex = re.compile('|'.join(kw_patterns), re.IGNORECASE)
        else:
            self._keywords_regex = None

    def should_ignore_process(self, process_name: str) -> bool:
        if not self.settings.enabled:
            return False
        if not process_name:
            return False
        return process_name.lower() in self._ignored_set

    def sanitize_title(self, window_title: str, process_name: str) -> Tuple[str, bool]:
        if not self.settings.enabled:
            return (window_title.strip() if window_title else '', False)
        if not window_title:
            return ('', False)
        was_redacted = False
        if self.settings.mask_all_titles:
            return (f'[{process_name}]' if process_name else '[Protected App]', True)
        if self.settings.mask_private_browsing and PRIVATE_BROWSING_REGEX.search(window_title):
            return ('[Private Browsing]', True)
        sanitized = window_title
        for pattern in self._compiled_patterns:
            if pattern.search(sanitized):
                sanitized = pattern.sub(self.settings.replacement_text, sanitized)
                was_redacted = True
        if self._keywords_regex and self._keywords_regex.search(sanitized):
            sanitized = self._keywords_regex.sub(self.settings.replacement_text, sanitized)
            was_redacted = True
        sanitized = ' '.join(sanitized.split())
        return (sanitized, was_redacted)

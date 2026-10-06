from client.config import PrivacySettings
from client.privacy import PrivacyEngine

def test_ignore_process_list():
    settings = PrivacySettings(ignored_processes=['1password.exe', 'keepass.exe', 'lockapp.exe'])
    engine = PrivacyEngine(settings)
    assert engine.should_ignore_process('1password.exe') is True
    assert engine.should_ignore_process('1Password.EXE') is True
    assert engine.should_ignore_process('KeePass.exe') is True
    assert engine.should_ignore_process('lockapp.exe') is True
    assert engine.should_ignore_process('code.exe') is False
    assert engine.should_ignore_process('chrome.exe') is False
    assert engine.should_ignore_process('') is False

def test_redact_sensitive_keywords():
    settings = PrivacySettings()
    engine = PrivacyEngine(settings)
    title = 'Settings - Change your password now'
    sanitized, redacted = engine.sanitize_title(title, 'chrome.exe')
    assert redacted is True
    assert 'password' not in sanitized.lower()
    assert '[REDACTED]' in sanitized
    title2 = 'Developer Console - api_key configuration'
    sanitized2, redacted2 = engine.sanitize_title(title2, 'code.exe')
    assert redacted2 is True
    assert 'api_key' not in sanitized2.lower()
    assert '[REDACTED]' in sanitized2

def test_redact_email_addresses():
    settings = PrivacySettings()
    engine = PrivacyEngine(settings)
    title = 'Draft message to john.doe@company.org - Thunderbird'
    sanitized, redacted = engine.sanitize_title(title, 'thunderbird.exe')
    assert redacted is True
    assert 'john.doe@company.org' not in sanitized
    assert '[REDACTED]' in sanitized

def test_redact_credit_cards():
    settings = PrivacySettings()
    engine = PrivacyEngine(settings)
    title = 'Checkout - Card 4111 2222 3333 4444 approved'
    sanitized, redacted = engine.sanitize_title(title, 'chrome.exe')
    assert redacted is True
    assert '4111 2222 3333 4444' not in sanitized
    assert '[REDACTED]' in sanitized

def test_redact_url_tokens():
    settings = PrivacySettings()
    engine = PrivacyEngine(settings)
    title = 'https://internal.service/oauth?token=secret123456789 - Edge'
    sanitized, redacted = engine.sanitize_title(title, 'msedge.exe')
    assert redacted is True
    assert 'secret123456789' not in sanitized
    assert '[REDACTED]' in sanitized

def test_private_browsing_detection():
    settings = PrivacySettings(mask_private_browsing=True)
    engine = PrivacyEngine(settings)
    titles = ['InPrivate - Personal Banking - Microsoft Edge', 'Incognito - Flight Search - Google Chrome', 'Private Browsing - Mozilla Firefox', 'Tor Browser - Hidden Service']
    for t in titles:
        sanitized, redacted = engine.sanitize_title(t, 'browser.exe')
        assert redacted is True
        assert sanitized == '[Private Browsing]'

def test_mask_all_titles_mode():
    settings = PrivacySettings(mask_all_titles=True)
    engine = PrivacyEngine(settings)
    sanitized, redacted = engine.sanitize_title('Confidential Project Roadmap', 'code.exe')
    assert redacted is True
    assert sanitized == '[code.exe]'

def test_normal_title_unaffected():
    settings = PrivacySettings()
    engine = PrivacyEngine(settings)
    title = 'main.py - win-activity-tracker - Visual Studio Code'
    sanitized, redacted = engine.sanitize_title(title, 'code.exe')
    assert redacted is False
    assert sanitized == title

def test_empty_and_unicode_titles():
    settings = PrivacySettings()
    engine = PrivacyEngine(settings)
    sanitized, redacted = engine.sanitize_title('', 'code.exe')
    assert redacted is False
    assert sanitized == ''
    unicode_title = 'Dự án phát triển phần mềm - Tài liệu tiếng Việt 🚀'
    sanitized_u, redacted_u = engine.sanitize_title(unicode_title, 'winword.exe')
    assert redacted_u is False
    assert sanitized_u == unicode_title

def test_raw_mode_disabled_privacy():
    settings = PrivacySettings(enabled=False)
    engine = PrivacyEngine(settings)
    assert engine.should_ignore_process('1password.exe') is False
    assert engine.should_ignore_process('lockapp.exe') is False
    raw_title = 'Admin Panel - password=secret_token123 - user@example.com (Incognito)'
    sanitized, redacted = engine.sanitize_title(raw_title, 'chrome.exe')
    assert redacted is False
    assert sanitized == raw_title

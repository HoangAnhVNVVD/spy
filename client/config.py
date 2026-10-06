from __future__ import annotations
import json
import os
import platform
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, List, Optional
DEFAULT_IGNORED_PROCESSES = ['lockapp.exe', 'screensaver.exe', 'logonui.exe', '1password.exe', 'keepass.exe', 'keepassxc.exe', 'bitwarden.exe', 'credentialui.exe', 'shellexperiencehost.exe', 'searchapp.exe', 'startmenuexperiencehost.exe']
DEFAULT_REDACT_KEYWORDS = ['password', 'passcode', 'api_key', 'secret', 'token', 'credit card', 'ssn', 'cvv']
DEFAULT_REDACT_PATTERNS = ['\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b', '\\b(?:\\d{4}[ -]?){3}\\d{4}\\b', '\\b\\d{4}[ -]?\\d{6}[ -]?\\d{5}\\b', '\\beyJ[A-Za-z0-9-_=]+\\.[A-Za-z0-9-_=]+\\.?[A-Za-z0-9-_.+/=]*\\b', '(?i)(password|passwd|token|secret|api_?key|auth|bearer)=[^&\\s]+']

@dataclass
class PrivacySettings:
    enabled: bool = True
    ignored_processes: List[str] = field(default_factory=lambda: list(DEFAULT_IGNORED_PROCESSES))
    mask_all_titles: bool = False
    mask_private_browsing: bool = True
    redact_keywords: List[str] = field(default_factory=lambda: list(DEFAULT_REDACT_KEYWORDS))
    redact_patterns: List[str] = field(default_factory=lambda: list(DEFAULT_REDACT_PATTERNS))
    replacement_text: str = '[REDACTED]'

@dataclass
class ClientConfig:
    server_url: str = 'http://localhost:8000'
    api_token: str = 'default-secret-token'
    client_id: str = field(default_factory=lambda: platform.node() or 'windows-client-1')
    poll_interval_seconds: float = 1.0
    idle_threshold_seconds: float = 120.0
    sync_interval_seconds: float = 30.0
    sync_batch_size: int = 100
    min_duration_seconds: float = 1.0
    db_path: str = field(default_factory=lambda: str(Path.home() / '.win_activity_tracker' / 'buffer.db'))
    privacy: PrivacySettings = field(default_factory=PrivacySettings)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClientConfig:
        cfg_data = dict(data)
        privacy_data = cfg_data.pop('privacy', None)
        if isinstance(privacy_data, dict):
            valid_p_keys = {f.name for f in fields(PrivacySettings)}
            filtered_p = {k: v for k, v in privacy_data.items() if k in valid_p_keys}
            privacy = PrivacySettings(**filtered_p)
        else:
            privacy = PrivacySettings()
        valid_c_keys = {f.name for f in fields(cls) if f.name != 'privacy'}
        filtered_c = {k: v for k, v in cfg_data.items() if k in valid_c_keys}
        return cls(**filtered_c, privacy=privacy)

    @classmethod
    def load(cls, config_path: Optional[str | Path]=None) -> ClientConfig:
        config = cls()
        target_path: Optional[Path] = None
        if config_path:
            target_path = Path(config_path)
        else:
            default_loc = Path.home() / '.win_activity_tracker' / 'config.json'
            local_loc = Path('config.json')
            if local_loc.exists():
                target_path = local_loc
            elif default_loc.exists():
                target_path = default_loc
        if target_path and target_path.exists():
            try:
                with open(target_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    config = cls.from_dict(content)
            except Exception as e:
                print(f'[Config] Warning: Failed to load {target_path}: {e}, using defaults.')
        if (env_url := os.getenv('ACTIVITY_SERVER_URL')):
            config.server_url = env_url.rstrip('/')
        if (env_token := os.getenv('ACTIVITY_API_TOKEN')):
            config.api_token = env_token
        if (env_cid := os.getenv('ACTIVITY_CLIENT_ID')):
            config.client_id = env_cid
        if (env_db := os.getenv('ACTIVITY_DB_PATH')):
            config.db_path = env_db
        if (env_idle := os.getenv('ACTIVITY_IDLE_THRESHOLD')):
            try:
                config.idle_threshold_seconds = float(env_idle)
            except ValueError:
                pass
        if (env_sync := os.getenv('ACTIVITY_SYNC_INTERVAL')):
            try:
                config.sync_interval_seconds = float(env_sync)
            except ValueError:
                pass
        if (env_poll := os.getenv('ACTIVITY_POLL_INTERVAL')):
            try:
                config.poll_interval_seconds = float(env_poll)
            except ValueError:
                pass
        if (env_min_dur := os.getenv('ACTIVITY_MIN_DURATION')):
            try:
                config.min_duration_seconds = float(env_min_dur)
            except ValueError:
                pass
        if os.getenv('ACTIVITY_MASK_ALL_TITLES', '').lower() in ('1', 'true', 'yes'):
            config.privacy.mask_all_titles = True
        if os.getenv('ACTIVITY_RAW_MODE', '').lower() in ('1', 'true', 'yes') or os.getenv('ACTIVITY_DISABLE_PRIVACY', '').lower() in ('1', 'true', 'yes'):
            config.privacy.enabled = False
        return config

    def save(self, destination: str | Path) -> None:
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)

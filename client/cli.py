"""Command-line interface for the Windows Activity Tracker client."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from client.buffer import ActivityBuffer
from client.config import ClientConfig
from client.privacy import PrivacyEngine
from client.sync import SyncClient
from client.tracker import ActivityTracker
from client.win32_monitor import Win32Monitor


def cmd_run(args: argparse.Namespace) -> None:
    """Run the tracking loop."""
    config = ClientConfig.load(args.config)
    if getattr(args, "server_url", None):
        config.server_url = args.server_url.rstrip("/")
    if getattr(args, "api_token", None):
        config.api_token = args.api_token
    if getattr(args, "client_id", None):
        config.client_id = args.client_id
    if getattr(args, "poll_interval", None) is not None:
        config.poll_interval_seconds = args.poll_interval
    if getattr(args, "idle_threshold", None) is not None:
        config.idle_threshold_seconds = args.idle_threshold
    if getattr(args, "sync_interval", None) is not None:
        config.sync_interval_seconds = args.sync_interval
    if getattr(args, "min_duration", None) is not None:
        config.min_duration_seconds = args.min_duration
    if getattr(args, "mask_all_titles", False):
        config.privacy.mask_all_titles = True
    if getattr(args, "raw_mode", False):
        config.privacy.enabled = False

    tracker = ActivityTracker(config)
    tracker.run()


def cmd_probe(args: argparse.Namespace) -> None:
    """Probe current active window and idle time for verification."""
    config = ClientConfig.load(args.config)
    if getattr(args, "raw_mode", False):
        config.privacy.enabled = False
    monitor = Win32Monitor(idle_threshold_seconds=config.idle_threshold_seconds)
    privacy = PrivacyEngine(config.privacy)

    print("=" * 60)
    print("Windows Activity Tracker - Win32 Monitor Probe")
    print("=" * 60)
    print("Polling active window every 1.5 seconds. Press Ctrl+C to exit.\n")

    try:
        while True:
            snap = monitor.snapshot()
            is_ignored = privacy.should_ignore_process(snap.process_name)
            sanitized_title, was_redacted = privacy.sanitize_title(snap.window_title, snap.process_name)

            print(f"Timestamp    : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(snap.timestamp))}")
            print(f"Process Name : {snap.process_name or '(None)'} (PID: {snap.pid})")
            print(f"Window HWND  : {snap.hwnd}")
            print(f"Raw Title    : {snap.window_title or '(Empty)'}")
            print(f"Sanitized    : {sanitized_title}")
            print(f"Redacted?    : {was_redacted}")
            print(f"Ignored?     : {is_ignored}")
            print(f"Idle Seconds : {snap.idle_seconds:.1f}s (Idle threshold: {config.idle_threshold_seconds}s)")
            print(f"User Status  : {'[IDLE / AWAY]' if snap.is_idle else '[ACTIVE]'}")
            print("-" * 60)
            time.sleep(1.5)
    except KeyboardInterrupt:
        print("\nProbe exited.")


def cmd_status(args: argparse.Namespace) -> None:
    """Check local buffer statistics and server connectivity."""
    config = ClientConfig.load(args.config)
    buffer = ActivityBuffer(config.db_path)
    sync_client = SyncClient(
        server_url=config.server_url,
        api_token=config.api_token,
        client_id=config.client_id,
    )

    stats = buffer.get_stats()
    server_online = sync_client.check_health()

    print("=" * 60)
    print("Windows Activity Tracker - Client Status")
    print("=" * 60)
    print(f"Client ID         : {config.client_id}")
    print(f"Database File     : {stats['db_path']}")
    print(f"Total Logged      : {stats['total_records']} intervals")
    print(f"Pending Sync      : {stats['unsynced_records']} records")
    print(f"Synced to Server  : {stats['synced_records']} records")
    print(f"Oldest Unsynced   : {stats['oldest_unsynced'] or 'None (up to date)'}")
    print(f"Server Target     : {config.server_url}")
    print(f"Server Status     : {'ONLINE (Connected)' if server_online else 'OFFLINE (Will buffer locally)'}")
    print("=" * 60)


def cmd_sync(args: argparse.Namespace) -> None:
    """Force an immediate sync of buffered activities to backend."""
    config = ClientConfig.load(args.config)
    buffer = ActivityBuffer(config.db_path)
    sync_client = SyncClient(
        server_url=config.server_url,
        api_token=config.api_token,
        client_id=config.client_id,
    )

    stats_before = buffer.get_stats()
    pending = stats_before["unsynced_records"]
    print(f"[Sync] Attempting to sync {pending} pending records to {config.server_url}...")

    synced_count = sync_client.sync_pending(buffer, batch_size=config.sync_batch_size)
    print(f"[Sync] Successfully uploaded and confirmed {synced_count} records.")

    stats_after = buffer.get_stats()
    print(f"[Sync] Remaining unsynced records: {stats_after['unsynced_records']}")


def cmd_config(args: argparse.Namespace) -> None:
    """Display current config or save default config template."""
    config = ClientConfig.load(args.config)
    if args.save_default:
        save_path = Path(args.save_default)
        config.save(save_path)
        print(f"[Config] Saved default configuration to {save_path}")
    else:
        print(json.dumps(config.to_dict(), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="win-activity-tracker",
        description="Personal privacy-first activity & productivity tracker for Windows.",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to custom config.json file",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # run
    run_parser = subparsers.add_parser("run", help="Start active window monitoring daemon")
    run_parser.add_argument("--server-url", type=str, help="Backend server URL (e.g. http://localhost:8000)")
    run_parser.add_argument("--api-token", type=str, help="Bearer authentication token")
    run_parser.add_argument("--client-id", type=str, help="Unique identifier for this client")
    run_parser.add_argument("--poll-interval", type=float, help="Seconds between window checks (default: 1.0)")
    run_parser.add_argument("--idle-threshold", type=float, help="Seconds of inactivity before idle state (default: 120.0)")
    run_parser.add_argument("--sync-interval", type=float, help="Seconds between sync attempts (default: 30.0)")
    run_parser.add_argument("--min-duration", type=float, help="Minimum duration to retain activity interval (default: 1.0)")
    run_parser.add_argument("--mask-all-titles", action="store_true", help="Mask all window titles completely")
    run_parser.add_argument("--raw-mode", action="store_true", help="Disable privacy filtering and redaction (record raw 100%% details)")
    run_parser.set_defaults(func=cmd_run)

    # probe
    probe_parser = subparsers.add_parser("probe", help="Live probe of active window & idle detection")
    probe_parser.add_argument("--raw-mode", action="store_true", help="Disable privacy filtering in probe")
    probe_parser.set_defaults(func=cmd_probe)

    # status
    status_parser = subparsers.add_parser("status", help="Show local buffer and sync stats")
    status_parser.set_defaults(func=cmd_status)

    # sync
    sync_parser = subparsers.add_parser("sync", help="Synchronize pending buffer to server")
    sync_parser.set_defaults(func=cmd_sync)

    # config
    config_parser = subparsers.add_parser("config", help="View or generate configuration")
    config_parser.add_argument("--save-default", type=str, help="Destination file path to save default config")
    config_parser.set_defaults(func=cmd_config)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

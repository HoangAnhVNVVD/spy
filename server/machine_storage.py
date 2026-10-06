from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

class MachineStorageManager:

    def __init__(self, base_dir: Optional[str | Path]=None):
        if base_dir is None:
            if Path('/app/data').exists() and Path('/app/data').is_dir():
                base_dir = os.getenv('STORAGE_DIR', '/app/data/machines')
            else:
                base_dir = os.getenv('STORAGE_DIR', './data/machines')
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def sanitize_client_id(self, client_id: str) -> str:
        if not client_id:
            return 'unnamed_machine'
        clean = re.sub('[^\\w\\.-]', '_', client_id.strip())
        return clean or 'unnamed_machine'

    def get_machine_dir(self, client_id: str) -> Path:
        safe_name = self.sanitize_client_id(client_id)
        machine_dir = self.base_dir / safe_name
        machine_dir.mkdir(parents=True, exist_ok=True)
        (machine_dir / 'daily').mkdir(parents=True, exist_ok=True)
        return machine_dir

    def record_activities(self, client_id: str, activities: List[Dict[str, Any]], client_ip: str='') -> Dict[str, Any]:
        if not activities:
            return {}
        machine_dir = self.get_machine_dir(client_id)
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()
        jsonl_path = machine_dir / 'activities.jsonl'
        with open(jsonl_path, 'a', encoding='utf-8') as f:
            for item in activities:
                record = dict(item)
                record['ingested_at'] = now_iso
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        for item in activities:
            st = str(item.get('start_time', ''))
            day_str = st[:10] if len(st) >= 10 else now_utc.strftime('%Y-%m-%d')
            daily_file = machine_dir / 'daily' / f'{day_str}.log'
            idle_str = '[AFK]' if item.get('is_idle') else '[ACTIVE]'
            dur = item.get('duration_seconds', 0)
            proc = item.get('process_name', 'Unknown')
            title = item.get('window_title', '')
            cat = item.get('category', 'Uncategorized')
            line = f"[{st}] {idle_str} [{proc}] ({dur}s) '{title}' | {cat}\n"
            with open(daily_file, 'a', encoding='utf-8') as df:
                df.write(line)
        info_path = machine_dir / 'machine_info.json'
        info = {'client_id': client_id, 'machine_name': client_id, 'storage_folder': str(machine_dir.name), 'storage_path': str(machine_dir.resolve()), 'first_seen': now_iso, 'last_seen': now_iso, 'last_ip': client_ip, 'total_records': 0, 'last_active_app': '', 'last_active_title': ''}
        if info_path.exists():
            try:
                with open(info_path, 'r', encoding='utf-8') as inf:
                    existing = json.load(inf)
                    info['first_seen'] = existing.get('first_seen', info['first_seen'])
                    info['total_records'] = existing.get('total_records', 0)
            except Exception:
                pass
        info['last_seen'] = now_iso
        info['total_records'] += len(activities)
        last_item = activities[-1]
        info['last_active_app'] = last_item.get('process_name', '')
        info['last_active_title'] = last_item.get('window_title', '')
        if client_ip:
            info['last_ip'] = client_ip
        with open(info_path, 'w', encoding='utf-8') as inf:
            json.dump(info, inf, indent=2, ensure_ascii=False)
        return info

    def get_machine_info(self, client_id: str) -> Dict[str, Any]:
        machine_dir = self.get_machine_dir(client_id)
        info_path = machine_dir / 'machine_info.json'
        if info_path.exists():
            try:
                with open(info_path, 'r', encoding='utf-8') as inf:
                    return json.load(inf)
            except Exception:
                pass
        return {'client_id': client_id, 'machine_name': client_id, 'storage_folder': machine_dir.name, 'storage_path': str(machine_dir.resolve()), 'first_seen': 'N/A', 'last_seen': 'N/A', 'total_records': 0}

    def get_recent_activities(self, client_id: str, limit: int=100) -> List[Dict[str, Any]]:
        machine_dir = self.get_machine_dir(client_id)
        jsonl_path = machine_dir / 'activities.jsonl'
        if not jsonl_path.exists():
            return []
        results: List[Dict[str, Any]] = []
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in reversed(lines):
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        results.append(json.loads(line_str))
                        if len(results) >= limit:
                            break
                    except Exception:
                        continue
        except Exception:
            pass
        return results

    def list_machines(self) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        if not self.base_dir.exists():
            return results
        for entry in sorted(self.base_dir.iterdir()):
            if entry.is_dir():
                info_file = entry / 'machine_info.json'
                if info_file.exists():
                    try:
                        with open(info_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            total_bytes = sum((f.stat().st_size for f in entry.rglob('*') if f.is_file()))
                            data['disk_bytes'] = total_bytes
                            data['disk_mb'] = round(total_bytes / (1024 * 1024), 2)
                            results.append(data)
                            continue
                    except Exception:
                        pass
                results.append({'client_id': entry.name, 'machine_name': entry.name, 'storage_folder': entry.name, 'storage_path': str(entry.resolve()), 'total_records': 0, 'disk_bytes': 0, 'disk_mb': 0.0})
        return results

    def get_machine_logs(self, client_id: str, date_str: Optional[str]=None, max_lines: int=100) -> List[str]:
        machine_dir = self.get_machine_dir(client_id)
        daily_dir = machine_dir / 'daily'
        if not daily_dir.exists():
            return []
        if date_str:
            target_file = daily_dir / f'{date_str}.log'
            files = [target_file] if target_file.exists() else []
        else:
            files = sorted(daily_dir.glob('*.log'), reverse=True)
        lines: List[str] = []
        for log_file in files:
            if not log_file.exists():
                continue
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                file_lines = f.readlines()
                lines.extend(file_lines[-max_lines:])
            if len(lines) >= max_lines:
                break
        return lines[-max_lines:]

    def record_live_tasks(self, client_id: str, tasks: List[Dict[str, Any]], client_ip: str='') -> Dict[str, Any]:
        machine_dir = self.get_machine_dir(client_id)
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()
        live_data = {'client_id': client_id, 'last_updated': now_iso, 'is_online': True, 'task_count': len(tasks), 'client_ip': client_ip, 'tasks': tasks}
        tasks_file = machine_dir / 'current_tasks.json'
        with open(tasks_file, 'w', encoding='utf-8') as f:
            json.dump(live_data, f, indent=2, ensure_ascii=False)
        info_path = machine_dir / 'machine_info.json'
        info = {'client_id': client_id, 'machine_name': client_id, 'storage_folder': str(machine_dir.name), 'storage_path': str(machine_dir.resolve()), 'first_seen': now_iso, 'last_seen': now_iso, 'last_ip': client_ip, 'total_records': 0, 'last_active_app': '', 'last_active_title': ''}
        if info_path.exists():
            try:
                with open(info_path, 'r', encoding='utf-8') as inf:
                    existing = json.load(inf)
                    info.update(existing)
            except Exception:
                pass
        info['last_seen'] = now_iso
        if client_ip:
            info['last_ip'] = client_ip
        focused_task = next((t for t in tasks if t.get('is_focused')), None)
        if focused_task:
            info['last_active_app'] = focused_task.get('process_name', '')
            info['last_active_title'] = focused_task.get('window_title', '')
        elif tasks:
            info['last_active_app'] = tasks[0].get('process_name', '')
            info['last_active_title'] = tasks[0].get('window_title', '')
        with open(info_path, 'w', encoding='utf-8') as inf:
            json.dump(info, inf, indent=2, ensure_ascii=False)
        return live_data

    def get_live_tasks(self, client_id: str) -> Optional[Dict[str, Any]]:
        machine_dir = self.get_machine_dir(client_id)
        tasks_file = machine_dir / 'current_tasks.json'
        if not tasks_file.exists():
            return None
        try:
            with open(tasks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            last_dt = datetime.fromisoformat(data['last_updated'])
            now_utc = datetime.now(timezone.utc)
            diff_sec = (now_utc - last_dt).total_seconds()
            data['is_online'] = diff_sec <= 15.0
            return data
        except Exception:
            return None

    def get_all_live_tasks(self) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        if not self.base_dir.exists():
            return results
        now_utc = datetime.now(timezone.utc)
        for entry in sorted(self.base_dir.iterdir()):
            if entry.is_dir():
                tasks_file = entry / 'current_tasks.json'
                if tasks_file.exists():
                    try:
                        with open(tasks_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        last_dt = datetime.fromisoformat(data['last_updated'])
                        diff_sec = (now_utc - last_dt).total_seconds()
                        data['is_online'] = diff_sec <= 15.0
                        results.append(data)
                    except Exception:
                        pass
        results.sort(key=lambda x: (1 if x.get('is_online') else 0, x.get('last_updated', '')), reverse=True)
        return results

    def delete_machine(self, client_id: str) -> bool:
        safe_name = self.sanitize_client_id(client_id)
        machine_dir = self.base_dir / safe_name
        if machine_dir.exists():
            import shutil
            shutil.rmtree(machine_dir, ignore_errors=True)
            return True
        return False
machine_storage = MachineStorageManager()

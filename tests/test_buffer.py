import threading
from datetime import datetime, timezone
from client.buffer import ActivityBuffer, ActivityEvent

def test_buffer_insert_and_retrieve(activity_buffer: ActivityBuffer):
    now = datetime.now(timezone.utc).isoformat()
    event = ActivityEvent(client_id='test-client-1', start_time=now, end_time=now, duration_seconds=12.5, process_name='code.exe', window_title='buffer.py - win-activity-tracker', category='Development', is_idle=False)
    event_id = activity_buffer.insert(event)
    assert event_id > 0
    batch = activity_buffer.get_unsynced_batch(limit=10)
    assert len(batch) == 1
    assert batch[0].id == event_id
    assert batch[0].process_name == 'code.exe'
    assert batch[0].duration_seconds == 12.5
    assert batch[0].synced is False

def test_buffer_mark_synced(activity_buffer: ActivityBuffer):
    now = datetime.now(timezone.utc).isoformat()
    ids = []
    for i in range(5):
        ev = ActivityEvent(client_id='test-client-1', start_time=now, end_time=now, duration_seconds=10.0, process_name=f'app_{i}.exe', window_title=f'Window {i}')
        ids.append(activity_buffer.insert(ev))
    stats1 = activity_buffer.get_stats()
    assert stats1['unsynced_records'] == 5
    assert stats1['synced_records'] == 0
    marked = activity_buffer.mark_synced(ids[:3])
    assert marked == 3
    stats2 = activity_buffer.get_stats()
    assert stats2['unsynced_records'] == 2
    assert stats2['synced_records'] == 3
    pending = activity_buffer.get_unsynced_batch(limit=10)
    assert len(pending) == 2
    assert pending[0].id == ids[3]
    assert pending[1].id == ids[4]

def test_buffer_empty_and_edge_cases(activity_buffer: ActivityBuffer):
    batch = activity_buffer.get_unsynced_batch(limit=50)
    assert batch == []
    marked = activity_buffer.mark_synced([])
    assert marked == 0
    pruned = activity_buffer.prune_synced(keep_days=14)
    assert pruned == 0

def test_buffer_thread_safety(activity_buffer: ActivityBuffer):
    now = datetime.now(timezone.utc).isoformat()

    def worker(worker_id: int):
        for j in range(20):
            ev = ActivityEvent(client_id=f'worker-{worker_id}', start_time=now, end_time=now, duration_seconds=1.0, process_name='test.exe', window_title=f'Worker {worker_id} Item {j}')
            activity_buffer.insert(ev)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    stats = activity_buffer.get_stats()
    assert stats['total_records'] == 100
    assert stats['unsynced_records'] == 100

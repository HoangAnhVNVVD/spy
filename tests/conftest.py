import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from client.config import ClientConfig, PrivacySettings
from client.buffer import ActivityBuffer
from server.database import Base, get_db
from server.app import app
from server.config import settings

@pytest.fixture
def temp_dir():
    td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    yield Path(td.name)
    try:
        td.cleanup()
    except Exception:
        pass

@pytest.fixture
def test_client_config(temp_dir):
    db_file = temp_dir / 'test_buffer.db'
    return ClientConfig(server_url='http://testserver', api_token='test-secret-token', client_id='test-client-device', poll_interval_seconds=0.1, idle_threshold_seconds=5.0, sync_interval_seconds=1.0, min_duration_seconds=0.5, db_path=str(db_file), privacy=PrivacySettings())

@pytest.fixture
def activity_buffer(temp_dir):
    db_file = temp_dir / 'buffer.db'
    return ActivityBuffer(db_file)

@pytest.fixture
def test_db_session(temp_dir):
    test_db_url = f'sqlite:///{temp_dir}/test_server.db'
    test_engine = create_engine(test_db_url, connect_args={'check_same_thread': False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        test_engine.dispose()

@pytest.fixture
def api_client(temp_dir):
    test_db_url = f'sqlite:///{temp_dir}/api_server.db'
    test_engine = create_engine(test_db_url, connect_args={'check_same_thread': False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    settings.API_KEY = 'test-secret-token'
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    test_engine.dispose()

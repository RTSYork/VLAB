"""Unit tests for the live config reload web API endpoints."""

import pytest
import fakeredis
from unittest.mock import patch


# app is importable because 'web' is in pythonpath (pytest.ini)
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        yield c


@pytest.fixture
def fake_db():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.mark.unit
class TestApiBoardsConfigReloadField:
    """The /api/boards response includes a config_reload_pending field."""

    def _get_boards(self, client, fake_db):
        with patch('redis_queries.connect', return_value=fake_db):
            return client.get('/api/boards')

    def test_field_present_in_response(self, client, fake_db):
        resp = self._get_boards(client, fake_db)
        assert resp.status_code == 200
        assert 'config_reload_pending' in resp.get_json()

    def test_field_false_when_key_absent(self, client, fake_db):
        resp = self._get_boards(client, fake_db)
        assert resp.get_json()['config_reload_pending'] is False

    def test_field_true_when_trigger_key_set(self, client, fake_db):
        fake_db.set('vlab:config:reload', '1')
        resp = self._get_boards(client, fake_db)
        assert resp.get_json()['config_reload_pending'] is True

    def test_field_false_after_trigger_key_deleted(self, client, fake_db):
        fake_db.set('vlab:config:reload', '1')
        fake_db.delete('vlab:config:reload')
        resp = self._get_boards(client, fake_db)
        assert resp.get_json()['config_reload_pending'] is False

    def test_field_false_when_redis_unavailable(self, client):
        with patch('redis_queries.connect', return_value=None):
            resp = client.get('/api/boards')
        # Response should still succeed (redis_ok=False path)
        data = resp.get_json()
        assert 'config_reload_pending' in data
        assert data['config_reload_pending'] is False


@pytest.mark.unit
class TestApiConfigReloadEndpoint:
    """POST /api/config/reload sets the Redis trigger key."""

    def test_returns_200_with_ok_true(self, client, fake_db):
        with patch('redis_queries.connect', return_value=fake_db):
            resp = client.post('/api/config/reload')
        assert resp.status_code == 200
        assert resp.get_json() == {'ok': True}

    def test_sets_trigger_key_in_redis(self, client, fake_db):
        with patch('redis_queries.connect', return_value=fake_db):
            client.post('/api/config/reload')
        assert fake_db.get('vlab:config:reload') == '1'

    def test_trigger_key_has_expiry(self, client, fake_db):
        with patch('redis_queries.connect', return_value=fake_db):
            client.post('/api/config/reload')
        ttl = fake_db.ttl('vlab:config:reload')
        assert ttl > 0, "Trigger key should have a TTL so it auto-expires"

    def test_trigger_key_ttl_is_reasonable(self, client, fake_db):
        with patch('redis_queries.connect', return_value=fake_db):
            client.post('/api/config/reload')
        ttl = fake_db.ttl('vlab:config:reload')
        assert ttl <= 120, f"TTL {ttl}s seems unexpectedly long"

    def test_returns_503_when_redis_unavailable(self, client):
        with patch('redis_queries.connect', return_value=None):
            resp = client.post('/api/config/reload')
        assert resp.status_code == 503
        data = resp.get_json()
        assert data['ok'] is False
        assert 'error' in data

    def test_get_method_not_allowed(self, client):
        resp = client.get('/api/config/reload')
        assert resp.status_code == 405

    def test_idempotent_successive_posts(self, client, fake_db):
        """Posting twice should not cause an error."""
        with patch('redis_queries.connect', return_value=fake_db):
            r1 = client.post('/api/config/reload')
            r2 = client.post('/api/config/reload')
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert fake_db.get('vlab:config:reload') == '1'

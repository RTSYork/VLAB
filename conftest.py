"""Shared fixtures and CLI options for the VLAB test suite."""

import time

import pytest


# ---------------------------------------------------------------------------
# CLI options
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run live tests that require SSH access to pegasus",
    )
    parser.addoption(
        "--run-direct",
        action="store_true",
        default=False,
        help="Run tests that require direct TCP/Redis/HTTP access to pegasus",
    )
    parser.addoption(
        "--pegasus-host",
        default="pegasus",
        help="Hostname or IP of the pegasus server (default: pegasus)",
    )
    parser.addoption(
        "--redis-port",
        default=6379,
        type=int,
        help="Redis port on pegasus (default: 6379)",
    )
    parser.addoption(
        "--ssh-port",
        default=2222,
        type=int,
        help="SSH relay port on pegasus (default: 2222)",
    )
    parser.addoption(
        "--web-port",
        default=9000,
        type=int,
        help="Web dashboard port on pegasus (default: 9000)",
    )
    parser.addoption(
        "--vlab-user",
        default=None,
        help="VLAB username for SSH login tests (e.g. vqt501)",
    )
    parser.addoption(
        "--vlab-key",
        default=None,
        help="Path to VLAB private key for SSH login tests (e.g. keys/vqt501.vlabkey)",
    )


# ---------------------------------------------------------------------------
# Automatic skip for live tests
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(config, items):
    run_live = config.getoption("--run-live")
    run_direct = config.getoption("--run-direct")
    skip_live = pytest.mark.skip(reason="need --run-live option to run")
    skip_direct = pytest.mark.skip(reason="need --run-direct option to run")
    for item in items:
        is_live = "integration" in item.keywords or "e2e" in item.keywords or "live" in item.keywords
        is_direct = "direct" in item.keywords
        if is_direct and not run_direct:
            item.add_marker(skip_direct)
        elif is_live and not is_direct and not run_live:
            item.add_marker(skip_live)


# ---------------------------------------------------------------------------
# Host / port fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def pegasus_host(request):
    return request.config.getoption("--pegasus-host")


@pytest.fixture(scope="session")
def redis_port(request):
    return request.config.getoption("--redis-port")


@pytest.fixture(scope="session")
def ssh_port(request):
    return request.config.getoption("--ssh-port")


@pytest.fixture(scope="session")
def web_port(request):
    return request.config.getoption("--web-port")


@pytest.fixture(scope="session")
def web_base_url(pegasus_host, web_port):
    return f"http://{pegasus_host}:{web_port}"


# ---------------------------------------------------------------------------
# Mock Redis fixtures (for unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    """Function-scoped fakeredis instance."""
    import fakeredis
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def populated_redis(mock_redis):
    """fakeredis pre-loaded with a realistic 2-user, 2-board state.

    Users:
        testuser   - normal user
        testoverlord - overlord

    Board class: vlab_test

    Boards:
        BOARD001 - available, no session, no lock
        BOARD002 - in active session by testuser, locked
    """
    db = mock_redis
    now = int(time.time())

    # Users
    db.sadd("vlab:users", "testuser", "testoverlord")
    db.set("vlab:user:testuser:overlord", "false")
    db.set("vlab:user:testoverlord:overlord", "true")

    # Board classes
    db.sadd("vlab:boardclasses", "vlab_test")

    # Register both boards in the class
    db.sadd("vlab:boardclass:vlab_test:boards", "BOARD001", "BOARD002")

    # Board metadata
    db.set("vlab:board:BOARD001:server", "boardserver1")
    db.set("vlab:board:BOARD001:port", "30001")
    db.set("vlab:board:BOARD002:server", "boardserver2")
    db.set("vlab:board:BOARD002:port", "30002")

    # Known board metadata
    db.set("vlab:knownboard:BOARD001:class", "vlab_test")
    db.set("vlab:knownboard:BOARD001:type", "zybo-z7")
    db.set("vlab:knownboard:BOARD002:class", "vlab_test")
    db.set("vlab:knownboard:BOARD002:type", "zybo-z7")

    # Port counter
    db.set("vlab:port", "30100")

    # BOARD001: available, unlocked
    db.zadd("vlab:boardclass:vlab_test:availableboards", {"BOARD001": now - 300})
    db.zadd("vlab:boardclass:vlab_test:unlockedboards", {"BOARD001": now - 300})

    # BOARD002: in session, locked by testuser
    session_start = now - 600
    db.set("vlab:board:BOARD002:lock:username", "testuser")
    db.set("vlab:board:BOARD002:lock:time", str(session_start))
    db.set("vlab:board:BOARD002:session:username", "testuser")
    db.set("vlab:board:BOARD002:session:starttime", str(session_start))
    db.set("vlab:board:BOARD002:session:pingtime", str(now - 30))

    return db


# ---------------------------------------------------------------------------
# Live Redis fixture (for integration tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def live_redis(pegasus_host, redis_port):
    """Session-scoped connection to the pegasus Redis instance."""
    import redis as redis_lib
    db = redis_lib.Redis(
        host=pegasus_host, port=redis_port, db=0, decode_responses=True
    )
    db.ping()  # will raise if unreachable
    return db


# ---------------------------------------------------------------------------
# Sample config fixture (for vlabconfig tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_config_dict():
    """Minimal valid vlab.conf as a Python dict."""
    return {
        "users": {
            "testuser": {},
            "testoverlord": {"overlord": True},
        },
        "boards": {
            "BOARD001": {"class": "vlab_test", "type": "zybo-z7"},
            "BOARD002": {"class": "vlab_test", "type": "zybo-z7"},
        },
    }


# ---------------------------------------------------------------------------
# VLAB SSH login fixtures (for e2e login tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def vlab_user(request):
    user = request.config.getoption("--vlab-user")
    if user is None:
        pytest.skip("need --vlab-user option for SSH login tests")
    return user


@pytest.fixture(scope="session")
def vlab_key(request):
    import os
    key = request.config.getoption("--vlab-key")
    if key is None:
        pytest.skip("need --vlab-key option for SSH login tests")
    key = os.path.expanduser(key)
    if not os.path.isfile(key):
        pytest.fail(f"VLAB key file not found: {key}")
    return key

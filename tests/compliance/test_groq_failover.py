import pytest
import os
import time
import urllib.error
from unittest.mock import patch, MagicMock

from scripts.phase12_f2_orchestrator import GroqClient

@pytest.fixture(autouse=True)
def mock_load_env(monkeypatch):
    monkeypatch.setattr("scripts.phase12_f2_orchestrator.load_env_file", lambda: None)

@pytest.fixture(autouse=True)
def clean_env():
    # Clear out GROQ_API_KEY environment variables
    keys = ["GROQ_API_KEY"] + [f"GROQ_API_KEY_{i}" for i in range(1, 20)]
    old_env = {}
    for k in keys:
        old_env[k] = os.environ.get(k)
        if k in os.environ:
            del os.environ[k]
    
    yield
    
    # Restore environment
    for k, v in old_env.items():
        if v is not None:
            os.environ[k] = v
        elif k in os.environ:
            del os.environ[k]
    
    # Reset GroqClient global state
    GroqClient._keys = []
    GroqClient._key_state = {}
    GroqClient._initialized = False
    GroqClient._current_index = 0

def set_keys(**kwargs):
    for k, v in kwargs.items():
        os.environ[k] = v

def create_mock_response(content="mocked response"):
    mock_resp = MagicMock()
    mock_resp.read.return_value = f'{{"choices": [{{"message": {{"content": "{content}"}}}}]}}'.encode('utf-8')
    return mock_resp

def create_http_error(code, body=""):
    fp = MagicMock()
    fp.read.return_value = body.encode('utf-8')
    return urllib.error.HTTPError("http://test", code, "Error", {}, fp)

class TestMultiKeyFailover:

    def test_01_initializes_with_no_keys(self):
        client = GroqClient()
        assert client.is_configured == False
        assert len(GroqClient._keys) == 0

    def test_02_initializes_with_one_key(self):
        set_keys(GROQ_API_KEY_1="key1")
        client = GroqClient()
        assert client.is_configured == True
        assert len(GroqClient._keys) == 1
        assert "KEY_1" in GroqClient._keys

    def test_03_initializes_with_multiple_keys(self):
        set_keys(GROQ_API_KEY_1="key1", GROQ_API_KEY_2="key2", GROQ_API_KEY_3="key3")
        client = GroqClient()
        assert len(GroqClient._keys) == 3

    def test_04_initializes_with_legacy_key(self):
        set_keys(GROQ_API_KEY="legacy")
        client = GroqClient()
        assert len(GroqClient._keys) == 1

    def test_05_legacy_key_not_duplicated(self):
        set_keys(GROQ_API_KEY_1="key1", GROQ_API_KEY="key1")
        client = GroqClient()
        assert len(GroqClient._keys) == 1

    @patch('urllib.request.urlopen')
    def test_06_successful_request_first_key(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1")
        mock_urlopen.return_value.__enter__.return_value = create_mock_response("success")
        client = GroqClient()
        
        trace = {}
        res = client.chat_completion([], trace_info=trace)
        
        assert res == "success"
        assert trace["selected_key_id"] == "KEY_1"
        assert trace["attempt_count"] == 1
        assert trace["failover_used"] == False
        assert trace["final_status"] == "SUCCESS"

    @patch('urllib.request.urlopen')
    def test_07_round_robin_distribution(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1", GROQ_API_KEY_2="key2")
        mock_urlopen.return_value.__enter__.return_value = create_mock_response("success")
        client = GroqClient()
        
        trace1, trace2, trace3 = {}, {}, {}
        client.chat_completion([], trace_info=trace1)
        client.chat_completion([], trace_info=trace2)
        client.chat_completion([], trace_info=trace3)
        
        # Should alternate
        assert trace1["selected_key_id"] != trace2["selected_key_id"]
        assert trace1["selected_key_id"] == trace3["selected_key_id"]

    @patch('urllib.request.urlopen')
    def test_08_failover_on_429(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1", GROQ_API_KEY_2="key2")
        # First call fails with 429, second succeeds
        mock_urlopen.side_effect = [
            create_http_error(429, "try again in 5s"),
            MagicMock(__enter__=lambda _: create_mock_response("success2"))
        ]
        client = GroqClient()
        
        trace = {}
        res = client.chat_completion([], trace_info=trace)
        
        assert res == "success2"
        assert trace["attempt_count"] == 2
        assert trace["failover_used"] == True
        assert trace["final_status"] == "SUCCESS"

    @patch('urllib.request.urlopen')
    def test_09_all_keys_rate_limited(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1", GROQ_API_KEY_2="key2")
        mock_urlopen.side_effect = [
            create_http_error(429),
            create_http_error(429)
        ]
        client = GroqClient()
        
        trace = {}
        with pytest.raises(RuntimeError, match="GROQ_ALL_KEYS_RATE_LIMITED"):
            client.chat_completion([], trace_info=trace)
            
        assert trace["attempt_count"] == 2
        assert trace["failover_used"] == True
        assert trace["final_status"] == "ERROR"

    @patch('urllib.request.urlopen')
    def test_10_cooldown_respects_retry_after(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1")
        mock_urlopen.side_effect = create_http_error(429, "try again in 0.5s")
        client = GroqClient()
        
        with pytest.raises(RuntimeError):
            client.chat_completion([])
            
        # Key should be in cooldown
        assert GroqClient._key_state["KEY_1"]["status"] == "COOLDOWN"
        assert GroqClient._get_next_available_key() is None
        
        time.sleep(1.6) # Wait for cooldown to expire (0.5 + 1.0 padding)
        
        assert GroqClient._get_next_available_key() == "KEY_1"

    @patch('urllib.request.urlopen')
    def test_11_failover_on_5xx(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1", GROQ_API_KEY_2="key2")
        mock_urlopen.side_effect = [
            create_http_error(503),
            MagicMock(__enter__=lambda _: create_mock_response("success_503"))
        ]
        client = GroqClient()
        trace = {}
        res = client.chat_completion([], trace_info=trace)
        assert res == "success_503"
        assert trace["failover_used"] == True

    @patch('urllib.request.urlopen')
    def test_12_failover_on_timeout(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1", GROQ_API_KEY_2="key2")
        mock_urlopen.side_effect = [
            urllib.error.URLError("timeout"),
            MagicMock(__enter__=lambda _: create_mock_response("success_timeout"))
        ]
        client = GroqClient()
        trace = {}
        res = client.chat_completion([], trace_info=trace)
        assert res == "success_timeout"
        assert trace["failover_used"] == True

    @patch('urllib.request.urlopen')
    def test_13_no_failover_on_400(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1", GROQ_API_KEY_2="key2")
        mock_urlopen.side_effect = create_http_error(400, "Bad request")
        client = GroqClient()
        trace = {}
        with pytest.raises(RuntimeError, match="400"):
            client.chat_completion([], trace_info=trace)
        assert trace["attempt_count"] == 1
        assert trace["failover_used"] == False

    @patch('urllib.request.urlopen')
    def test_14_mark_invalid_on_401(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1", GROQ_API_KEY_2="key2")
        mock_urlopen.side_effect = [
            create_http_error(401, "Unauthorized"),
            MagicMock(__enter__=lambda _: create_mock_response("success_401"))
        ]
        client = GroqClient()
        client.chat_completion([])
        assert any(state["status"] == "INVALID" for state in GroqClient._key_state.values())

    @patch('urllib.request.urlopen')
    def test_15_mark_invalid_on_403(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1", GROQ_API_KEY_2="key2")
        mock_urlopen.side_effect = [
            create_http_error(403, "Forbidden"),
            MagicMock(__enter__=lambda _: create_mock_response("success_403"))
        ]
        client = GroqClient()
        client.chat_completion([])
        assert any(state["status"] == "INVALID" for state in GroqClient._key_state.values())

    @patch('urllib.request.urlopen')
    def test_16_state_counters_incremented(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1")
        mock_urlopen.return_value.__enter__.return_value = create_mock_response("success")
        client = GroqClient()
        client.chat_completion([])
        assert GroqClient._key_state["KEY_1"]["usage_count"] == 1

    @patch('urllib.request.urlopen')
    def test_17_multiple_instances_share_state(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1", GROQ_API_KEY_2="key2")
        mock_urlopen.side_effect = [create_http_error(429), create_http_error(429)]
        c1 = GroqClient()
        with pytest.raises(RuntimeError):
            c1.chat_completion([])
        
        c2 = GroqClient()
        assert c2.is_configured == True
        assert GroqClient._get_next_available_key() is None

    @patch('urllib.request.urlopen')
    def test_18_trace_info_retained_on_success(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1", GROQ_API_KEY_2="key2")
        mock_urlopen.side_effect = [
            create_http_error(429),
            MagicMock(__enter__=lambda _: create_mock_response("final"))
        ]
        client = GroqClient()
        trace = {}
        client.chat_completion([], trace_info=trace)
        assert trace["final_status"] == "SUCCESS"
        assert trace["failover_used"] == True
        assert trace["attempt_count"] == 2

    @patch('urllib.request.urlopen')
    def test_19_legacy_fallback_no_env_keys(self, mock_urlopen):
        # Already tested in 04, adding explicit check for api_key arg
        client = GroqClient(api_key="provided_key")
        assert "KEY_PROVIDED" in GroqClient._keys
        mock_urlopen.return_value.__enter__.return_value = create_mock_response("success")
        res = client.chat_completion([])
        assert res == "success"

    @patch('urllib.request.urlopen')
    def test_20_cooldown_default_duration(self, mock_urlopen):
        set_keys(GROQ_API_KEY_1="key1")
        mock_urlopen.side_effect = create_http_error(429, "Rate limited") # No 'try again in X'
        client = GroqClient()
        with pytest.raises(RuntimeError):
            client.chat_completion([])
        
        state = GroqClient._key_state["KEY_1"]
        # Default should be 30s
        assert state["cooldown_until"] - time.time() > 25.0

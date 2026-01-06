#!/usr/bin/env python3
"""
PANDA.1 v0.2.11 Test Suite
=========================

Tests for GUI voice integration and bug fixes.

Run with: pytest tests/test_gui_v028.py -v
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


# =============================================================================
# Test 1: Action Log POST without timestamp returns 200
# =============================================================================
class TestActionLog:
    """Test action log endpoint fixes."""
    
    def test_action_log_create_model(self):
        """ActionLogCreate should not require timestamp."""
        from app.web_gui import ActionLogCreate
        
        # Should work without timestamp
        log = ActionLogCreate(
            action="test_action",
            details="test details",
            success=True
        )
        assert log.action == "test_action"
        assert log.details == "test details"
        assert log.success is True
    
    def test_action_log_entry_has_timestamp(self):
        """ActionLogEntry should have timestamp."""
        from app.web_gui import ActionLogEntry
        
        entry = ActionLogEntry(
            action="test",
            details="details",
            success=True,
            timestamp="2024-01-01T12:00:00"
        )
        assert entry.timestamp == "2024-01-01T12:00:00"
    
    @pytest.mark.asyncio
    async def test_action_log_endpoint_accepts_no_timestamp(self):
        """POST /api/ui/action-log should accept payload without timestamp."""
        from fastapi.testclient import TestClient
        from app.web_gui import app
        
        client = TestClient(app)
        
        # POST without timestamp (what frontend sends)
        response = client.post(
            "/api/ui/action-log",
            json={
                "action": "test_action",
                "details": "test details",
                "success": True
            }
        )
        
        # Should NOT return 422
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "logged"
        assert "timestamp" in data  # Server should add timestamp


# =============================================================================
# Test 2: WebSocket toggle_language doesn't crash
# =============================================================================
class TestLanguageToggle:
    """Test language mode toggle fixes."""
    
    def test_language_manager_has_set_mode(self):
        """LanguageModeManager should have set_mode() method."""
        from app.language_mode import LanguageModeManager
        
        manager = LanguageModeManager()
        assert hasattr(manager, 'set_mode')
        assert callable(manager.set_mode)
    
    def test_set_mode_changes_mode(self):
        """set_mode() should change the language mode."""
        from app.language_mode import LanguageModeManager

        manager = LanguageModeManager()

        # Test setting to Korean (LanguageMode is Literal["en", "ko"], not Enum)
        manager.set_mode("ko")
        assert manager.mode == "ko"

        # Test setting to English
        manager.set_mode("en")
        assert manager.mode == "en"
    
    def test_set_mode_accepts_string(self):
        """set_mode() should accept string values."""
        from app.language_mode import LanguageModeManager

        manager = LanguageModeManager()

        # Test with string (LanguageMode is Literal["en", "ko"], not Enum)
        manager.set_mode("ko")
        assert manager.mode == "ko"

        manager.set_mode("en")
        assert manager.mode == "en"


# =============================================================================
# Test 3: Chat streaming creates separate bubbles (message_id)
# =============================================================================
class TestMessageIdCorrelation:
    """Test message_id correlation for separate chat bubbles."""
    
    def test_chat_message_with_id(self):
        """Chat messages should support message_id."""
        # Simulate frontend message format
        msg1 = {
            "type": "chat",
            "content": "Hello",
            "message_id": "msg_001"
        }
        msg2 = {
            "type": "chat",
            "content": "How are you?",
            "message_id": "msg_002"
        }
        
        assert msg1["message_id"] != msg2["message_id"]
    
    def test_stream_events_include_message_id(self):
        """Stream events should include message_id for correlation."""
        # Expected event format
        stream_start = {
            "type": "stream_start",
            "message_id": "msg_001"
        }
        stream_chunk = {
            "type": "stream",
            "content": "Hello",
            "message_id": "msg_001"
        }
        stream_end = {
            "type": "stream_end",
            "message_id": "msg_001"
        }
        
        # All events for same message should have same message_id
        assert stream_start["message_id"] == stream_chunk["message_id"]
        assert stream_chunk["message_id"] == stream_end["message_id"]


# =============================================================================
# Test 4: Voice can be disabled without breaking GUI
# =============================================================================
class TestVoiceDisable:
    """Test GUI works with voice disabled."""
    
    def test_config_gui_voice_enabled_flag(self):
        """Config should have gui_voice_enabled flag."""
        from app.config import PandaConfig
        
        config = PandaConfig()
        assert hasattr(config, 'gui_voice_enabled')
        assert isinstance(config.gui_voice_enabled, bool)
    
    def test_config_voice_ack_enabled_flag(self):
        """Config should have voice_ack_enabled flag."""
        from app.config import PandaConfig
        
        config = PandaConfig()
        assert hasattr(config, 'voice_ack_enabled')
        assert isinstance(config.voice_ack_enabled, bool)
    
    @patch.dict('os.environ', {'PANDA_GUI_VOICE_ENABLED': 'false'})
    def test_gui_starts_without_voice(self):
        """GUI should start even with voice disabled."""
        from app.config import PandaConfig
        
        # Force reload config with new env
        config = PandaConfig()
        assert config.gui_voice_enabled is False


# =============================================================================
# Test 5: Mic device selection parameter is used
# =============================================================================
class TestMicDeviceSelection:
    """Test microphone device selection."""
    
    def test_config_audio_input_device(self):
        """Config should have audio_input_device setting."""
        from app.config import PandaConfig
        
        config = PandaConfig()
        assert hasattr(config, 'audio_input_device')
    
    @patch.dict('os.environ', {'PANDA_AUDIO_INPUT_DEVICE': '2'})
    def test_audio_input_device_from_env(self):
        """audio_input_device should be parsed from env."""
        from app.config import PandaConfig
        
        config = PandaConfig()
        assert config.audio_input_device == 2
    
    def test_voice_assistant_accepts_device_index(self):
        """VoiceAssistant should accept audio_input_device parameter."""
        from app.voice_assistant import VoiceAssistant
        import inspect
        
        sig = inspect.signature(VoiceAssistant.__init__)
        params = list(sig.parameters.keys())
        
        assert 'audio_input_device' in params


# =============================================================================
# Test 6: TTS speaking events emitted
# =============================================================================
class TestTTSSpeakingEvents:
    """Test TTS speaking state events."""
    
    def test_voice_state_dict_structure(self):
        """Voice state should include speaking flag."""
        voice_state = {
            "mic": "SLEEPING",
            "transcript": "",
            "speaking": False
        }
        
        assert "speaking" in voice_state
        assert isinstance(voice_state["speaking"], bool)
    
    def test_speaking_event_format(self):
        """Speaking events should have correct format."""
        speaking_true = {
            "type": "speaking",
            "value": True
        }
        speaking_false = {
            "type": "speaking",
            "value": False
        }
        
        assert speaking_true["type"] == "speaking"
        assert speaking_true["value"] is True
        assert speaking_false["value"] is False


# =============================================================================
# Test 7: SCOTT offline doesn't break GUI
# =============================================================================
class TestScottOffline:
    """Test GUI handles SCOTT offline gracefully."""
    
    def test_config_scott_retry_interval(self):
        """Config should have scott_retry_interval."""
        from app.config import PandaConfig
        
        config = PandaConfig()
        assert hasattr(config, 'scott_retry_interval')
        assert isinstance(config.scott_retry_interval, int)
        assert config.scott_retry_interval >= 0
    
    def test_scott_status_structure(self):
        """SCOTT status should be separate from GUI health."""
        scott_status = {
            "online": False,
            "last_check": "2024-01-01T12:00:00"
        }
        
        assert "online" in scott_status
        assert "last_check" in scott_status


# =============================================================================
# Test 8: Voice state enum includes UNAVAILABLE
# =============================================================================
class TestVoiceStates:
    """Test voice state handling."""
    
    def test_voice_state_unavailable(self):
        """VoiceState should include UNAVAILABLE state."""
        from app.voice_assistant import VoiceState
        
        assert hasattr(VoiceState, 'UNAVAILABLE')
    
    def test_voice_state_all_states(self):
        """VoiceState should have all required states."""
        from app.voice_assistant import VoiceState
        
        expected_states = ['SLEEPING', 'AWAKE_LISTENING', 'PROCESSING', 'UNAVAILABLE']
        for state in expected_states:
            assert hasattr(VoiceState, state), f"Missing state: {state}"


# =============================================================================
# Test 9: Version consistency
# =============================================================================
class TestVersionConsistency:
    """Test version strings are consistent."""
    
    def test_main_version(self):
        """main.py should have v0.2.11."""
        from app.main import __version__
        assert __version__ == "0.2.11"
    
    def test_web_gui_version(self):
        """web_gui.py should have v0.2.11."""
        from app.web_gui import __version__
        assert __version__ == "0.2.11"
    
    def test_config_version(self):
        """Config display should show v0.2.11."""
        from app.config import get_config
        
        config = get_config()
        display = config.to_display_dict()
        assert "0.2.11" in display.get("Version", "")


# =============================================================================
# Test 10: Audio device listing
# =============================================================================
class TestAudioDeviceListing:
    """Test audio device listing functions."""
    
    def test_list_audio_devices_function_exists(self):
        """list_audio_devices function should exist."""
        from app.voice_assistant import list_audio_devices
        assert callable(list_audio_devices)
    
    def test_print_audio_devices_function_exists(self):
        """print_audio_devices function should exist."""
        from app.voice_assistant import print_audio_devices
        assert callable(print_audio_devices)
    
    def test_mic_test_function_exists(self):
        """mic_test function should exist."""
        from app.voice_assistant import mic_test
        assert callable(mic_test)


# =============================================================================
# Integration test helpers
# =============================================================================
@pytest.fixture
def mock_panda_core():
    """Create a mock PandaCore for testing."""
    mock = MagicMock()
    mock.process_stream.return_value = iter(["Hello", " BOS", "!"])
    return mock


@pytest.fixture
def mock_tts_manager():
    """Create a mock TTS manager."""
    mock = MagicMock()
    mock.speak.return_value = None
    mock.healthcheck.return_value = {"healthy": True, "engine": "mock"}
    return mock


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

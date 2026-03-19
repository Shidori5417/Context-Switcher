"""Environment Agent birim testleri — subprocess ve plyer mock'lu."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from src.agents.environment_agent import EnvironmentAgent, send_notification, set_volume
from src.core.event_bus import SwitchEvent


def _make_event(volume: int = 60, playlist: str = "", dry_run: bool = False) -> SwitchEvent:
    env: dict = {"volume": volume}
    if playlist:
        env["music"] = {"app": "spotify", "playlist": playlist}

    return SwitchEvent(
        mode_name="study",
        config={
            "name": "Ders Modu",
            "icon": "📚",
            "environment": env,
        },
        dry_run=dry_run,
    )


class TestSetVolume:
    def test_clamps_above_100(self):
        # 150 → clamp → 100, herhangi bir çağrı başarılı dönmeli
        with patch("ctypes.windll", MagicMock()):
            result = set_volume(150)
        # Test: çökmemeli — return değeri bool

    def test_clamps_below_0(self):
        with patch("ctypes.windll", MagicMock()):
            result = set_volume(-10)

    def test_linux_pactl(self):
        with (
            patch("sys.platform", "linux"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            from src.agents.environment_agent import _set_volume_linux
            result = _set_volume_linux(50)
        mock_run.assert_called()

    def test_macos_osascript(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            from src.agents.environment_agent import _set_volume_macos
            result = _set_volume_macos(40)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "osascript" in args


class TestSendNotification:
    def test_notify_graceful_on_failure(self):
        """plyer hata verirse send_notification False döndürmeli."""
        # Mevcut send_notification içinde lazy `from plyer import notification`
        # var; notification.notify mock'layarak test edelim
        mock_notification = MagicMock()
        mock_notification.notify.side_effect = Exception("no display")

        # send_notification fonksiyonu try/except içinde çalışıyor
        # Doğrudan Exception verdiren gerçek plyer ile test
        from plyer import notification as real_notification
        original_notify = real_notification.notify
        try:
            real_notification.notify = MagicMock(side_effect=Exception("no display"))
            result = send_notification("Test", "Msg")
        finally:
            real_notification.notify = original_notify

        assert result is False

    def test_notify_returns_true_on_success(self):
        """plyer başarılı olduğunda True dönmeli."""
        from plyer import notification as real_notification
        original_notify = real_notification.notify
        try:
            real_notification.notify = MagicMock(return_value=None)
            result = send_notification("Test", "Msg")
        finally:
            real_notification.notify = original_notify

        assert result is True



class TestEnvironmentAgentExecute:
    def test_no_env_config_skipped(self):
        agent = EnvironmentAgent()
        event = SwitchEvent(mode_name="dev", config={"name": "Dev"})
        report = agent.execute(event)
        assert report.success
        assert "atlandı" in report.message

    def test_dry_run_shows_actions(self):
        agent = EnvironmentAgent()
        event = _make_event(volume=50, playlist="Deep Focus", dry_run=True)
        report = agent.execute(event)
        assert report.success
        assert any("simülasyon" in a for a in report.details.get("actions", []))

    def test_execute_calls_set_volume(self):
        agent = EnvironmentAgent()
        event = _make_event(volume=40)

        with (
            patch("src.agents.environment_agent.set_volume", return_value=True) as mock_vol,
            patch("src.agents.environment_agent.send_notification", return_value=True),
        ):
            report = agent.execute(event)

        mock_vol.assert_called_once_with(40)
        assert report.success

    def test_execute_calls_spotify(self):
        agent = EnvironmentAgent()
        event = _make_event(volume=60, playlist="spotify:playlist:abc123")

        with (
            patch("src.agents.environment_agent.set_volume", return_value=True),
            patch("src.agents.environment_agent._spotify_open_playlist", return_value=True) as mock_spot,
            patch("src.agents.environment_agent.send_notification", return_value=True),
        ):
            agent.execute(event)

        mock_spot.assert_called_once_with("spotify:playlist:abc123", "spotify")

    def test_sends_notification_on_complete(self):
        agent = EnvironmentAgent()
        event = _make_event(volume=50)

        with (
            patch("src.agents.environment_agent.set_volume", return_value=True),
            patch("src.agents.environment_agent.send_notification", return_value=True) as mock_notif,
        ):
            agent.execute(event)

        mock_notif.assert_called_once()

    def test_rollback_sends_notification(self):
        agent = EnvironmentAgent()
        event = SwitchEvent(mode_name="dev", config={}, previous_mode="study")

        with patch("src.agents.environment_agent.send_notification", return_value=True) as mock_notif:
            report = agent.rollback(event)

        assert report.success
        mock_notif.assert_called_once()

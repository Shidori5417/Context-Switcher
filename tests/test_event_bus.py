"""EventBus birim testleri."""

from src.core.event_bus import EventBus, StatusReport, SwitchEvent


def _make_handler(agent_name: str, success: bool = True):
    """Test için basit bir handler factory."""

    def handler(event: SwitchEvent) -> StatusReport:
        return StatusReport(
            agent_name=agent_name,
            success=success,
            message=f"{agent_name}: {'OK' if success else 'FAIL'}",
        )

    return handler


class TestSwitchEvent:
    def test_create_basic(self):
        event = SwitchEvent(mode_name="dev", config={"name": "Dev"})
        assert event.mode_name == "dev"
        assert event.previous_mode is None
        assert event.dry_run is False

    def test_create_full(self):
        event = SwitchEvent(
            mode_name="study",
            config={"name": "Study"},
            previous_mode="dev",
            dry_run=True,
        )
        assert event.mode_name == "study"
        assert event.previous_mode == "dev"
        assert event.dry_run is True

    def test_repr(self):
        event = SwitchEvent(mode_name="dev", config={})
        r = repr(event)
        assert "dev" in r
        assert "dry_run=False" in r


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        bus.subscribe("switch", _make_handler("test_agent"))
        event = SwitchEvent(mode_name="dev", config={})
        reports = bus.publish("switch", event)
        assert len(reports) == 1
        assert reports[0].success is True
        assert reports[0].agent_name == "test_agent"

    def test_multiple_subscribers(self):
        bus = EventBus()
        bus.subscribe("switch", _make_handler("agent_a"))
        bus.subscribe("switch", _make_handler("agent_b"))
        event = SwitchEvent(mode_name="dev", config={})
        reports = bus.publish("switch", event)
        assert len(reports) == 2
        names = {r.agent_name for r in reports}
        assert names == {"agent_a", "agent_b"}

    def test_publish_no_subscribers(self):
        bus = EventBus()
        event = SwitchEvent(mode_name="dev", config={})
        reports = bus.publish("unknown_event", event)
        assert reports == []

    def test_clear(self):
        bus = EventBus()
        bus.subscribe("switch", _make_handler("agent"))
        assert bus.subscriber_count == 1
        bus.clear()
        assert bus.subscriber_count == 0

    def test_subscriber_count(self):
        bus = EventBus()
        bus.subscribe("switch", _make_handler("a"))
        bus.subscribe("rollback", _make_handler("b"))
        assert bus.subscriber_count == 2

    def test_failed_handler(self):
        bus = EventBus()
        bus.subscribe("switch", _make_handler("failing", success=False))
        event = SwitchEvent(mode_name="dev", config={})
        reports = bus.publish("switch", event)
        assert reports[0].success is False

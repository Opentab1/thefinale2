"""Unit-style tests for AudioMonitor restart helpers.

These tests focus on the stream interruption logic which previously
allowed zombie PyAudio streams to persist after watchdog-triggered
restarts. The tests operate purely on the helper methods and do not
require actual audio hardware.
"""

import threading
from threading import Lock


from services.sensors.mic_song_detect import AudioMonitor


class DummyStream:
    """Minimal fake audio stream collecting stop/close calls."""

    def __init__(self) -> None:
        self.stopped = 0
        self.closed = 0

    def stop_stream(self) -> None:
        self.stopped += 1

    def close(self) -> None:
        self.closed += 1


def _build_monitor_with_dummy_stream() -> tuple[AudioMonitor, DummyStream]:
    monitor = AudioMonitor.__new__(AudioMonitor)
    monitor._stream_restart_request = threading.Event()
    monitor._active_stream_lock = Lock()
    dummy = DummyStream()
    monitor._active_pa_stream = dummy
    monitor._active_sd_stream = None
    return monitor, dummy


def test_request_stream_restart_sets_event_and_closes_stream() -> None:
    monitor, dummy = _build_monitor_with_dummy_stream()

    monitor._request_stream_restart("unit_test")

    assert monitor._stream_restart_request.is_set()
    assert monitor._active_pa_stream is None
    assert dummy.stopped == 1
    assert dummy.closed == 1


def test_request_stream_restart_idempotent_when_already_closed() -> None:
    monitor, dummy = _build_monitor_with_dummy_stream()

    monitor._request_stream_restart("unit_test")
    first_stop_count = dummy.stopped
    first_close_count = dummy.closed

    # Second invocation should not attempt to close again because
    # the active handle has already been cleared.
    monitor._request_stream_restart("repeat_call")

    assert dummy.stopped == first_stop_count
    assert dummy.closed == first_close_count

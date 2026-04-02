import os
import time
import tempfile
import pytest
from app.utils.helpers import smooth, clamp_coords, FPSCounter, log_command


def test_smooth_no_prev():
    assert smooth(None, 100) == 100


def test_smooth_with_prev():
    result = smooth(0, 100, alpha=0.5)
    assert result == 50


def test_smooth_alpha_one():
    assert smooth(50, 100, alpha=1.0) == 100


def test_smooth_alpha_zero():
    assert smooth(50, 100, alpha=0.0) == 50


def test_clamp_coords_in_bounds():
    assert clamp_coords(100, 200, 960, 720) == (100, 200)


def test_clamp_coords_negative():
    assert clamp_coords(-5, -10, 960, 720) == (0, 0)


def test_clamp_coords_over_max():
    assert clamp_coords(1000, 800, 960, 720) == (959, 719)


def test_fps_counter_single_tick():
    counter = FPSCounter()
    fps = counter.tick()
    assert fps == 0.0


def test_fps_counter_multiple_ticks():
    counter = FPSCounter()
    counter.tick()
    time.sleep(0.05)
    counter.tick()
    fps = counter.tick()
    assert fps > 0


def test_log_command_creates_file(tmp_path, monkeypatch):
    log_file = tmp_path / "logs" / "commands.txt"
    monkeypatch.setattr("app.utils.helpers.LOG_PATH", str(log_file))
    log_command("SAVE")
    assert log_file.exists()
    content = log_file.read_text()
    assert "SAVE" in content


def test_log_command_appends(tmp_path, monkeypatch):
    log_file = tmp_path / "logs" / "commands.txt"
    monkeypatch.setattr("app.utils.helpers.LOG_PATH", str(log_file))
    log_command("CLEAR")
    log_command("SAVE")
    lines = log_file.read_text().strip().splitlines()
    assert len(lines) == 2
    assert "CLEAR" in lines[0]
    assert "SAVE" in lines[1]

import os
import time
import cv2

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "logs", "commands.txt")


def smooth(prev, curr, alpha=0.6):
    if prev is None:
        return curr
    return int(alpha * curr + (1 - alpha) * prev)


class FPSCounter:
    def __init__(self, smoothing=10):
        self._times = []
        self._smoothing = smoothing

    def tick(self):
        now = time.time()
        self._times.append(now)
        if len(self._times) > self._smoothing:
            self._times.pop(0)
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / elapsed if elapsed > 0 else 0.0


def clamp_coords(x, y, width, height):
    return max(0, min(x, width - 1)), max(0, min(y, height - 1))


def log_command(command: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a") as f:
        f.write(f"[{timestamp}] {command}\n")


def draw_fps(frame, fps: float):
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    return frame

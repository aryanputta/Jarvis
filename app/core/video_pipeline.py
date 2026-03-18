import cv2
import time

from app.core.hand_detection import HandDetector
from app.core.command_parser import CommandParser
from app.core.voice_input import listen_command
from app.utils.config import (
    CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT,
    USE_WEBCAM, ENABLE_VOICE, COMMAND_COOLDOWN,
)
from app.utils.helpers import FPSCounter, log_command, draw_fps

detector = HandDetector()
parser = CommandParser()
fps_counter = FPSCounter()

source = CAMERA_INDEX if USE_WEBCAM else "app/data/recordings/videos/your_video.mp4"  # swap filename in here
cap = cv2.VideoCapture(source)

last_command_time = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

    frame, x, y, landmarks = detector.detect(frame)

    command = None

    if ENABLE_VOICE:
        now = time.time()
        if now - last_command_time >= COMMAND_COOLDOWN:
            text = listen_command()
            command = parser.parse(text)
            if command:
                last_command_time = now
                log_command(command)

    if x is not None and y is not None:
        cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)

    if command is not None:
        cv2.putText(frame, command, (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

    frame = draw_fps(frame, fps_counter.tick())
    cv2.imshow("Feed", frame)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
        break

cap.release()
cv2.destroyAllWindows()

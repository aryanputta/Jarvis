import cv2
import time
import numpy as np
import os, sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)
from app.core.face_detection import FaceDetector
from app.core.command_parser import CommandParser
from app.core.voice_input import listen_command
from app.utils.config import (
    CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT,
    USE_WEBCAM, ENABLE_VOICE, COMMAND_COOLDOWN,
)
from app.utils.helpers import FPSCounter, log_command, draw_fps
from app.processing.drawing import create_ui, Draw



parser = CommandParser()
fps_counter = FPSCounter()

source = CAMERA_INDEX if USE_WEBCAM else "app/data/recordings/videos/your_video.mp4"  # swap filename in here
cap = cv2.VideoCapture(source)

last_command_time = 0


canvas = np.full((FRAME_HEIGHT, FRAME_WIDTH, 3), 255, dtype = np.uint8)



detector = FaceDetector(canvas)
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

    #rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
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

    if landmarks is not None:
        filter_img, hull, hullIndex = detector.load_filter(landmarks,"img.png")
        for pt in hull:
            x, y = pt
            #cv2.circle(frame, (x, y), 2, (0, 255, 0), -1)
        if filter_img is not None:
            print(filter_img)
            frame = detector.apply_filter_simple(frame, filter_img, hull)
        else:
            print("No filter image")
            
    output = cv2.addWeighted(frame, 0.6, canvas, 0.4, 0)

    if command is not None:
        cv2.putText(frame, command, (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

    output = draw_fps(output, fps_counter.tick())
    cv2.imshow("Feed", output)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
        break

cap.release()
cv2.destroyAllWindows()

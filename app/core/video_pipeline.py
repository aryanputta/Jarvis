import cv2
import time
import numpy as np

from app.core.hand_detection import HandDetector
from app.core.command_parser import CommandParser
from app.core.voice_input import listen_command
from app.utils.config import (
    CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT,
    USE_WEBCAM, ENABLE_VOICE, COMMAND_COOLDOWN,
)
from app.utils.helpers import FPSCounter, log_command, draw_fps
from app.processing.drawing import create_ui, Draw
import sys, subprocess

detector = HandDetector()
parser = CommandParser()
fps_counter = FPSCounter()

source = CAMERA_INDEX if USE_WEBCAM else "app/data/recordings/videos/your_video.mp4"  # swap filename in here
cap = cv2.VideoCapture(source)

last_command_time = 0

UI = create_ui(FRAME_WIDTH, FRAME_HEIGHT)
canvas = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype = np.uint8)

drawing_board = Draw(canvas)

image_saved = False

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

    if x is not None and y is not None:
        cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
    if drawing_board.check_index_finger_is_raised(landmarks):
        if drawing_board.check_if_using_toolbar(x,y) and drawing_board.saved_img ==True:
            image_saved = True
            break #quit after saving image

        if not drawing_board.check_if_using_toolbar(x,y):
            print("this is the landmark values", x,y)
            drawing_board.is_drawing = True
            drawing_board.create_stroke(landmarks)
    else:
        drawing_board.prev_point = None
    
    ##output = cv2.addWeighted(frame, 1.0, canvas, 1.0, 0)
    ##output[:(FRAME_HEIGHT//8), :] = UI
    # 1. Create a mask of where you have drawn (anything that isn't black)
    gray_canvas = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray_canvas, 1, 255, cv2.THRESH_BINARY)

    # 2. Start with the webcam frame
    output = frame.copy()

    # 3. Only paste the canvas colors where the mask is active
    output[mask > 0] = canvas[mask > 0]

    # Assuming you modified create_ui to return the image with 4 channels (BGRA)
    ui_h = FRAME_HEIGHT // 8
    roi = output[0:ui_h, 0:FRAME_WIDTH]
    bgr = UI[:, :, :3] ## 1st 3 channels(colors)
    alpha = UI[:, :, 3] / 255.0 #4th channel - transparency 

    for c in range(0, 3):
        roi[:, :, c] = (alpha * bgr[:, :, c] + (1 - alpha) * roi[:, :, c])
    output[0:ui_h, 0:FRAME_WIDTH] = roi

    if command is not None:
        cv2.putText(frame, command, (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

    frame = draw_fps(frame, fps_counter.tick())
    cv2.imshow("Feed", output)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
        break

if (image_saved):
    subprocess.run([sys.executable, "app/core/filter_video_pipeline.py"])
cap.release()
cv2.destroyAllWindows()

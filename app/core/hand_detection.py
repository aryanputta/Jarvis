import cv2
import mediapipe as mp
import numpy as np

from app.utils.config import (
    MAX_HANDS,
    DETECTION_CONFIDENCE,
    TRACKING_CONFIDENCE,
    EDGE_REGION_SIZE,
)

_mp_draw = mp.solutions.drawing_utils
_mp_hands = mp.solutions.hands


class HandDetector:
    def __init__(self):
        self.hands = _mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=MAX_HANDS,
            min_detection_confidence=DETECTION_CONFIDENCE,
            min_tracking_confidence=TRACKING_CONFIDENCE,
        )

    def detect(self, frame: np.ndarray):
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)

        if not results.multi_hand_landmarks:
            return frame, None, None, None

        hand_landmarks = results.multi_hand_landmarks[0]
        _mp_draw.draw_landmarks(frame, hand_landmarks, _mp_hands.HAND_CONNECTIONS)

        tip = hand_landmarks.landmark[8]   # index finger tip
        tip_x = int(tip.x * width)
        tip_y = int(tip.y * height)

        frame = self._sobel_region(frame, tip_x, tip_y, width, height)

        return frame, tip_x, tip_y, hand_landmarks.landmark

    def _sobel_region(self, frame, cx, cy, width, height):
        s = EDGE_REGION_SIZE
        x1, y1 = max(0, cx - s), max(0, cy - s)
        x2, y2 = min(width, cx + s), min(height, cy + s)

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return frame

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        grad_x = cv2.Sobel(gray, cv2.CV_16S, 1, 0)
        grad_y = cv2.Sobel(gray, cv2.CV_16S, 0, 1)
        edge = cv2.addWeighted(cv2.convertScaleAbs(grad_x), 0.5,
                               cv2.convertScaleAbs(grad_y), 0.5, 0)

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 1)

        eh, ew = edge.shape[:2]
        frame[0:eh, 0:ew] = cv2.cvtColor(edge, cv2.COLOR_GRAY2BGR)  # debug overlay top-left

        return frame

import cv2
import mediapipe as mp
import numpy as np
import sys, os
#import faceBlendCommon as fbc
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

_mp_draw = mp.solutions.drawing_utils
mp_face_mesh = mp.solutions.face_mesh
from app.utils.config import (
    DETECTION_CONFIDENCE,
    TRACKING_CONFIDENCE,
    EDGE_REGION_SIZE,
)
#read 
cap = cv2.VideoCapture(0)
class FaceDetector:
    def __init__(self, img):
        self.face = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces = 1,
            refine_landmarks = True,
            min_detection_confidence=DETECTION_CONFIDENCE,
            min_tracking_confidence=TRACKING_CONFIDENCE,
        )
        
    def detect(self, frame: np.ndarray):
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face.process(rgb)

        if not results.multi_face_landmarks:
            return frame, None, None, None

        face_landmarks = results.multi_face_landmarks[0].landmark
        #_mp_draw.draw_landmarks(frame, face_landmarks, mp_face_mesh.FACEMESH_TESSELATION)

        points = [] #this is to convert normalized landmarks to pixel coordinates based on height and width
        for landmark in face_landmarks:
            pix = int(landmark.x *width)
            piy = int(landmark.y *height)
            points.append((pix,piy))

        
        #the nose tip landmark will be used as reference point
        nose_x, nose_y = points[1]
        

        return frame, nose_x, nose_y, points
        
    # detect convex hull points around prominent facial features like the lips eyes and nose
    # this allows the filter to be morphed to facial expressions
    def load_image(self, image_path):
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        return img
    
    def find_convex_hull(self, landmarks):
        given_points = [
        162, 234, 93, 58, 172, 136, 149, 148, 152, 377, 378, 365, 397, 288, 323, 454, 389, # Jaw
        71, 63, 105, 66, 107, 336, 296, 334, 293, 301, # Eyebrows
        168, 197, 5, 4, 75, 97, 2, 326, 305, # Nose
        33, 160, 158, 133, 153, 144, 362, 385, 387, 263, 373, 380, # Eyes
        61, 39, 37, 0, 267, 269, 291, 405, 314, 17, 84, 181, # Mouth (Outer)
        78, 82, 13, 312, 308, 317, 14, 87 # Mouth (Inner)
        ]
        
        landmarks = np.array(landmarks, dtype=np.int32)
        hull = [landmarks[pt] for pt in given_points]
        hullIndex = np.array([[i] for i in given_points], dtype=np.int32)

        return hull, hullIndex
    
    #denaulay Triangulation to wrap filter around the face
    def load_filter(self, landmarks, img_path):
        img = self.load_image(img_path)
        if img is None:
            print("file not found")
            return None,None,None
        #we can add feature to save filters and process them later
        hull, hullIndex = self.find_convex_hull(landmarks)
        sizeImg = img.shape
        rect = (0, 0, sizeImg[1], sizeImg[0])
        #dt = fbc.calculateDelaunayTriangles(rect, hull)
        
        return img, hull, hullIndex
    def apply_filter_simple(self, frame, filter_img, hull):
        hull = np.array(hull, dtype = np.int32).reshape(-1,2)

        #filter_resized = cv2.resize(filter_img, (w, h))

        center_x = int(np.mean(hull[:, 0]))
        center_y = int(np.mean(hull[:, 1]))

        fh, fw = filter_img.shape[:2]
        h, w = frame.shape[:2]
        x1 = center_x - fw // 2
        y1 = center_y - fh // 2
        x2 = x1 + fw
        y2 = y1 + fh
        
        frame_x1 = max(0, x1)
        frame_y1 = max(0, y1)
        frame_x2 = min(w, x2)
        frame_y2 = min(h, y2)
        
        # keep within bounds 
        if frame_x1 >= frame_x2 or frame_y1 >= frame_y2:
            return frame

        #crop 
        filter_x1 = frame_x1 - x1
        filter_y1 = frame_y1 - y1
        filter_x2 = filter_x1 + (frame_x2 - frame_x1)
        filter_y2 = filter_y1 + (frame_y2 - frame_y1)

        cropped_filter = filter_img[filter_y1:filter_y2, filter_x1: filter_x2]
        roi = frame[frame_y1: frame_y2, frame_x1:frame_x2]

        if cropped_filter.shape[2] == 4:
            alpha = cropped_filter[:, :, 3] / 255.0
            print(alpha.shape, roi.shape)
            for c in range(3):
                roi[:, :, c] = (
                    (1 - alpha) * roi[:, :, c] +
                    alpha * cropped_filter[:, :, c]
                )
        else:
            roi[:] = cropped_filter[:, :, :3]

        frame[max(0,y1):min(h,y2), max(0,x1):min(w,x2)] = roi
        return frame
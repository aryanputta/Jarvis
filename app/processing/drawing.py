import cv2
import numpy as np
import mediapipe as mp
import time
import warnings


from app.utils.config import (FRAME_WIDTH, FRAME_HEIGHT, MIN_STROKE_DISTANCE, LINE_THICKNESS)

warnings.filterwarnings("ignore", category=UserWarning, module="google.protobuf.symbol_database")

colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (0, 255, 255), (255, 0, 255), (255, 255, 0)]
color_names = ["RED", "GREEN", "BLUE", "YELLOW", "MAGENTA", "CYAN"]
colorIndex = 0

points = [[] for _ in range(len(colors))]
ui_height= FRAME_HEIGHT // 8 

def create_ui(width, height):
    
    ui = np.zeros((ui_height, width, 3), dtype=np.uint8)
    
    for y in range(ui_height):
        
        color = [int(240 * (1 - y/ui_height))] * 3
        cv2.line(ui, (0, y), (width, y), color, 1)
    
    button_width = min(50, width // (len(colors) + 2))
    for i, color in enumerate(colors):
        x = 10 + i * (button_width + 10)
        cv2.circle(ui, (x + button_width // 2, ui_height // 2), button_width // 2 - 5, color, -1)
        cv2.circle(ui, (x + button_width // 2, ui_height // 2), button_width // 2 - 5, (0, 0, 0), 2)
        cv2.putText(ui, color_names[i][:1], (x + button_width // 2 - 5, ui_height // 2 + 5), 
                    cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, (0, 0, 0), 2)
    
    cv2.rectangle(ui, (width - 100, 10), (width - 10, ui_height - 10), (200, 200, 200), -1)
    cv2.rectangle(ui, (width - 200, 10), (width - 110, ui_height - 10), (0, 0, 0), 2)
    cv2.putText(ui, "CLEAR", (width - 190, ui_height // 2 + 5), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, (0, 0, 0), 2)
    cv2.rectangle(ui, (width - 100, 10), (width - 10, ui_height - 10), (0, 0, 0), 2)
    cv2.putText(ui, "SAVE", (width - 90, ui_height // 2 + 5), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, (0, 0, 0), 2)
    
    return ui

#toolbar is split [0,860] v [860,960]
class Draw:
    def __init__(self, canvas):
        self.prev_point = None
        self.color_index = 0
        self.canvas = canvas
        self.is_drawing = False
        self.saved_img = False
        
        
    def update_landmarks(self, new_hand_landmarks):
        self.hand_landmarks = new_hand_landmarks
        
    def check_index_finger_is_raised(self, hand_landmarks):
        if (hand_landmarks is None):
            return False
        return hand_landmarks[8].y < hand_landmarks[6].y
    
    def save_img(self):
        print("Saved image button accessed")
        alph = np.ones((FRAME_HEIGHT, FRAME_WIDTH), dtype = np.uint8) * 255 # needed to create an alpha channel to control opacity
        white_mask = np.all(self.canvas>= 255, axis = 2) #detect all white pixels
        #set white pixels to transparent to create png effect
        alph[white_mask] = 0
        #combine image and save using opencv as png
        img = np.dstack((self.canvas, alph))
        cv2.imwrite("img.png", img)
        self.saved_img = True
    
    def check_if_using_toolbar(self, index_finger_x, index_finger_y):
       
        if index_finger_y <= ui_height:
            #clear
            
            if (FRAME_WIDTH - 200) <= index_finger_x <= (FRAME_WIDTH - 110) and 10 <= index_finger_y <= (ui_height - 10):
                self.canvas.fill(255)
                self.prev_point = None
            #save image
            if (FRAME_WIDTH - 100) <= index_finger_x <= (FRAME_WIDTH - 10) and 10 <= index_finger_y <= (ui_height - 10):
                self.save_img()
                return True
            
            if index_finger_x <= FRAME_WIDTH - 100:
                for i, x in enumerate(range(10, 10 + len(colors) * 60, 60)):
                    if x <= index_finger_x <= x + 50:
                        self.color_index = i
                        break
            return True
        return False
        
    
        
    
    def create_stroke(self, hand_landmarks):
        if self.is_drawing:
            index_finger_x = int(hand_landmarks[8].x *FRAME_WIDTH)
            index_finger_y = int(hand_landmarks[8].y*FRAME_HEIGHT)
            if self.prev_point is None:
                self.prev_point = (index_finger_x, index_finger_y)
                return
            
            dist = np.linalg.norm(np.array((index_finger_y, index_finger_x)) - np.array(self.prev_point))

            if dist >= MIN_STROKE_DISTANCE:
                cv2.line(self.canvas, (int(self.prev_point[0]), int(self.prev_point[1])), (int(index_finger_x), int(index_finger_y)), colors[self.color_index], LINE_THICKNESS)
                self.prev_point = (index_finger_x, index_finger_y)
                
    
        
        
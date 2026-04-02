# What i need to do next time — Jarvis Project State

## What is built

## Run it

```bash
./install.sh              # first time only
python -m app.core.video_pipeline
```

## File map

```
app/core/video_pipeline.py    main loop
app/core/hand_detection.py    MediaPipe + Sobel edge
app/core/command_parser.py    text → command string
app/core/voice_input.py       mic → text (threaded, non-blocking)
app/utils/config.py           all settings live here
app/utils/helpers.py          FPS counter, smoother, logger
```

## What I still need to be doing

- [ ] Add drawing/canvas layer on top of feed (fingertip draws on screen)
- [ ] Add gesture recognition (pinch, fist, open hand) not just fingertip
- [ ] Connect commands to actual actions (OPEN_BOARD does something)
- [ ] Add second hand support (change MAX_HANDS = 2 in config)
- [ ] UI overlay — show active tool, mode, state on screen

## MediaPipe landmark indexes

```
4  = thumb tip
8  = index finger tip    ← currently tracked
12 = middle finger tip
16 = ring finger tip
20 = pinky tip
0  = wrist
```

## To test video file

1. Drop video in app/data/recordings/videos/
2. config.py → USE_WEBCAM = False
3. video_pipeline.py line 17 → swap filename

## Output contract

Every frame returns:  frame, fingertip_x, fingertip_y, landmarks, command

## Libs in use

opencv-python, mediapipe, numpy, SpeechRecognition, pyaudio

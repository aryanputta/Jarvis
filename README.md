

## Stack

- [OpenCV](https://opencv.org/) — camera pipeline + image processing
- [MediaPipe](https://mediapipe.dev/) — hand landmark detection
- [SpeechRecognition](https://pypi.org/project/SpeechRecognition/) — voice input
- NumPy — array ops

## Setup

**macOS** (run once):
```bash
./install.sh
```

**Other platforms:**
```bash
pip install -r requirements.txt
```

## Run

```bash
python3 -m app.core.video_pipeline
```

Press `ESC` to quit.

## Configuration

All settings are in [`app/utils/config.py`](app/utils/config.py):

| Setting | Default | Description |
|---|---|---|
| `CAMERA_INDEX` | `0` | Webcam index |
| `USE_WEBCAM` | `True` | Set `False` to use a video file |
| `ENABLE_VOICE` | `True` | Toggle mic input |
| `COMMAND_COOLDOWN` | `2` | Seconds between commands |
| `EDGE_REGION_SIZE` | `80` | Sobel crop box size around fingertip |

## Using a video file instead of webcam

1. Drop your `.mp4` into `app/data/recordings/videos/`
2. In `config.py` set `USE_WEBCAM = False` and uncomment `VIDEO_PATH`
3. In `video_pipeline.py` swap the filename on the source line

## Voice commands

| Say | Action |
|---|---|
| "open board" / "open canvas" | `OPEN_BOARD` — open the styling canvas |
| "clear" / "erase" | `CLEAR` — clear the current selection |
| "save" | `SAVE` — save the current look |
| "switch" / "tool" | `SWITCH_TOOL` — switch active tool |
| "stop" | `STOP` — end the session |

Add your own in [`app/core/command_parser.py`](app/core/command_parser.py).

## Project structure

```
app/
  core/
    video_pipeline.py   — main loop
    hand_detection.py   — MediaPipe + Sobel
    command_parser.py   — text → command
    voice_input.py      — mic → text (threaded)
  utils/
    config.py           — all settings
    helpers.py          — FPS, smoothing, logger
  data/
    recordings/
      videos/           — drop test videos in here
      images/           — drop test frames in here
    logs/
      commands.txt      — recognized commands logged here
```

## Tests

```bash
python3 -m pytest tests/ -v
```

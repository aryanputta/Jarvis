import threading
import speech_recognition as sr

from app.utils.config import (
    VOICE_AMBIENT_CALIBRATION,
    VOICE_DEVICE_INDEX,
    VOICE_LISTEN_TIMEOUT,
    VOICE_PHRASE_LIMIT,
)

recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 0.8

_state = {
    "text": None,
    "status": "idle",
    "error": None,
    "last_heard": None,
}
_lock = threading.Lock()
_thread = None
_calibrated = False


def _set_state(**kwargs):
    with _lock:
        _state.update(kwargs)


def _listen_worker():
    global _calibrated
    while True:
        _set_state(status="listening", error=None)
        try:
            with sr.Microphone(device_index=VOICE_DEVICE_INDEX) as source:
                if not _calibrated:
                    recognizer.adjust_for_ambient_noise(source, duration=VOICE_AMBIENT_CALIBRATION)
                    _calibrated = True
                audio = recognizer.listen(
                    source,
                    timeout=VOICE_LISTEN_TIMEOUT,
                    phrase_time_limit=VOICE_PHRASE_LIMIT,
                )
            _set_state(status="processing", error=None)
            text = recognizer.recognize_google(audio)
            _set_state(text=text, status="heard", error=None, last_heard=text)
        except sr.WaitTimeoutError:
            _set_state(text=None, status="listening", error=None)
        except sr.UnknownValueError:
            _set_state(text=None, status="did_not_understand", error="I couldn't understand that.")
        except sr.RequestError as exc:
            _set_state(text=None, status="speech_api_error", error=str(exc))
        except Exception as exc:
            _set_state(text=None, status="mic_error", error=str(exc))


def listen_command(consume_text: bool = True):
    """Non-blocking voice poll that returns text plus mic status."""
    global _thread

    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_listen_worker, daemon=True)
        _thread.start()

    with _lock:
        snapshot = dict(_state)
        if consume_text:
            _state["text"] = None
    return snapshot

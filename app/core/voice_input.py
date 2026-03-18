import threading
import speech_recognition as sr

recognizer = sr.Recognizer()

_result = None
_lock = threading.Lock()
_thread = None


def _listen_worker():
    global _result
    try:
        with sr.Microphone() as source:  # wrong mic? add device_index=1 or 2 in here
            audio = recognizer.listen(source, phrase_time_limit=3)
        text = recognizer.recognize_google(audio)
    except Exception:
        text = None
    with _lock:
        _result = text


def listen_command():
    """Non-blocking — kicks off a background listen and returns last result."""
    global _thread, _result

    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_listen_worker, daemon=True)
        _thread.start()

    with _lock:
        text = _result
        _result = None  # consume it
    return text

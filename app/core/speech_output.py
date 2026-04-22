import queue
import re
import shutil
import subprocess
import threading
import time
from typing import Optional

from app.utils.config import ENABLE_SPEECH_OUTPUT, SYSTEM_VOICE_NAME, SYSTEM_VOICE_RATE


_speech_queue: "queue.Queue[str]" = queue.Queue()
_speech_thread: Optional[threading.Thread] = None
_last_spoken_text = ""
_last_spoken_at = 0.0


def _build_say_command(text: str) -> list[str]:
    command = ["say"]
    if SYSTEM_VOICE_NAME:
        command.extend(["-v", SYSTEM_VOICE_NAME])
    if SYSTEM_VOICE_RATE:
        command.extend(["-r", str(SYSTEM_VOICE_RATE)])
    command.append(text)
    return command


def _clean_spoken_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ""

    normalized = normalized.replace("Whiteboard", "Board")
    normalized = normalized.replace("I generated a preliminary BOM", "I put together a parts list")
    normalized = normalized.replace("I wrote a demo talk track", "I put together a demo talk track")
    normalized = normalized.replace("I drafted an email", "I drafted the email")
    normalized = normalized.replace("I sent a demo email", "I sent the demo email")

    kept_sentences = []
    for sentence in re.split(r"(?<=[.!?])\s+", normalized):
        lower = sentence.lower()
        if any(token in lower for token in {"outbox", ".eml", ".json", "saved ", "output_path", "artifact"}):
            continue
        kept_sentences.append(sentence)

    spoken = " ".join(kept_sentences[:2]) if kept_sentences else normalized
    return spoken[:240].strip()


def _speaker_worker() -> None:
    while True:
        text = _speech_queue.get()
        if text == "__STOP__":
            return
        if not ENABLE_SPEECH_OUTPUT:
            continue
        if not shutil.which("say"):
            continue
        subprocess.run(_build_say_command(text), check=False)


def speak_text(text: Optional[str]) -> bool:
    global _speech_thread, _last_spoken_text, _last_spoken_at

    if not text:
        return False

    normalized = _clean_spoken_text(text)
    if not normalized:
        return False

    now = time.time()
    if normalized == _last_spoken_text and now - _last_spoken_at < 1.5:
        return False

    if _speech_thread is None or not _speech_thread.is_alive():
        _speech_thread = threading.Thread(target=_speaker_worker, daemon=True)
        _speech_thread.start()

    _last_spoken_text = normalized
    _last_spoken_at = now
    _speech_queue.put(normalized)
    return True

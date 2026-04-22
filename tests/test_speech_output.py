from app.core.speech_output import _build_say_command, _clean_spoken_text


def test_build_say_command():
    command = _build_say_command("Hello from Jarvis")
    assert command[0] == "say"
    assert "Hello from Jarvis" == command[-1]


def test_clean_spoken_text_drops_file_path_noise():
    text = "I sent the demo email to Shrihan with the latest design attached. Saved edge-node.eml in the outbox."
    cleaned = _clean_spoken_text(text)

    assert "outbox" not in cleaned.lower()
    assert ".eml" not in cleaned.lower()
    assert "I sent the demo email" in cleaned

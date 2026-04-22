import numpy as np

from app.utils.helpers import draw_agent_hud, draw_memory_panel


def test_draw_agent_hud_renders_overlay():
    frame = np.full((720, 960, 3), 245, dtype=np.uint8)

    rendered = draw_agent_hud(
        frame.copy(),
        agent_status="listening",
        voice_status="listening",
        heard_text="Jarvis clear the board",
        response_text="Whiteboard cleared.",
        project_name="6g ai-ran edge node",
    )

    assert rendered.shape == frame.shape
    assert np.any(rendered != frame)


def test_draw_memory_panel_expands_frame():
    frame = np.full((720, 960, 3), 245, dtype=np.uint8)
    panel = {
        "header": "Jarvis Memory | Aryan",
        "learning_mode": True,
        "voice_status": "listening",
        "latest_heard": "Jarvis help me build this",
        "latest_response": "I loaded your recent project context.",
        "recent_actions": ["Loaded project memory"],
    }

    rendered = draw_memory_panel(frame, panel)

    assert rendered.shape[0] == frame.shape[0]
    assert rendered.shape[1] > frame.shape[1]

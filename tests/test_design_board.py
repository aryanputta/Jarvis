import numpy as np

from app.core.design_board import DesignBoard


def test_design_board_renders_workspace():
    board = DesignBoard(width=960, height=720)
    board.open()
    board.update_brief(
        "6g ai-ran edge node",
        {
            "budget_limit": 200,
            "preferred_design": "compact",
            "open_tasks": ["CAD export"],
        },
        "Loaded the board.",
        [{"content": "preferred compact design"}],
    )
    board.update_from_pointer(200, 220, 960, 720)
    board.update_from_pointer(320, 320, 960, 720)

    frame = np.full((720, 960, 3), 200, dtype=np.uint8)
    rendered = board.render(camera_frame=frame)

    assert rendered.shape == (720, 960, 3)
    assert np.any(rendered[:, :280] != 248)
    assert np.any(rendered != 248)


def test_design_board_switch_and_clear():
    board = DesignBoard(width=960, height=720)
    board.open()
    board.update_from_pointer(200, 220, 960, 720)
    board.update_from_pointer(340, 340, 960, 720)

    assert board.active_tool == "pen"
    board.switch_tool()
    assert board.active_tool == "eraser"
    board.clear()
    assert np.all(board.sketch_layer == 255)

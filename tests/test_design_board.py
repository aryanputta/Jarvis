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


def test_design_board_clear_restores_clean_canvas_region():
    board = DesignBoard(width=960, height=720)
    board.open()
    board.update_from_pointer(280, 240, 960, 720)
    board.update_from_pointer(420, 360, 960, 720)
    board.clear()

    cleared = board.render()
    fresh = DesignBoard(width=960, height=720)
    fresh.open()
    baseline = fresh.render()

    assert np.array_equal(cleared[88:680, 300:900], baseline[88:680, 300:900])


def test_design_board_renders_reference_preview():
    board = DesignBoard(width=960, height=720)
    board.open()
    reference = np.full((240, 320, 3), 80, dtype=np.uint8)
    board.set_reference_image(reference, title="Edge Node Concept")

    rendered = board.render()

    assert np.any(rendered[180:290, 40:220] != 43)

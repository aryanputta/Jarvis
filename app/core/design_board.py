import textwrap
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


class DesignBoard:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.is_open = False
        self.active_tool = "pen"
        self.last_point: Optional[Tuple[int, int]] = None
        self.brief: Dict[str, object] = {}
        self.sketch_layer = np.full((height, width, 3), 255, dtype=np.uint8)

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False
        self.last_point = None

    def toggle(self) -> bool:
        self.is_open = not self.is_open
        if not self.is_open:
            self.last_point = None
        return self.is_open

    def clear(self) -> None:
        self.sketch_layer[:] = 255
        self.last_point = None

    def switch_tool(self) -> str:
        self.active_tool = "eraser" if self.active_tool == "pen" else "pen"
        return self.active_tool

    def update_brief(
        self,
        project_name: Optional[str],
        project_state: Optional[Dict[str, object]],
        latest_response: Optional[str],
        relevant_memories: Optional[List[Dict[str, object]]] = None,
    ) -> None:
        project_state = project_state or {}
        relevant_memories = relevant_memories or []

        constraints = []
        if project_state.get("budget_limit") is not None:
            constraints.append(f"Budget under ${project_state['budget_limit']}")
        if project_state.get("preferred_design"):
            constraints.append(f"Design: {project_state['preferred_design']}")
        if project_state.get("preferred_parts"):
            constraints.append(f"Parts: {', '.join(project_state['preferred_parts'][:2])}")

        tasks = project_state.get("open_tasks") or []
        notes = []
        if latest_response:
            notes.append(latest_response)
        if project_state.get("last_session_summary"):
            notes.append(str(project_state["last_session_summary"]))
        if relevant_memories:
            notes.append(str(relevant_memories[0]["content"]))

        self.brief = {
            "title": (project_name or "Jarvis Concept Board").title(),
            "constraints": constraints[:3],
            "tasks": list(tasks)[:4],
            "notes": notes[:3],
        }

    def update_from_pointer(
        self,
        x: Optional[int],
        y: Optional[int],
        source_width: int,
        source_height: int,
    ) -> None:
        if not self.is_open or x is None or y is None:
            self.last_point = None
            return

        left_margin = 300
        right_margin = 24
        board_x = left_margin + int((x / max(1, source_width)) * (self.width - left_margin - right_margin))
        board_y = int((y / max(1, source_height)) * (self.height - 32)) + 16
        board_x = max(left_margin, min(board_x, self.width - right_margin))
        board_y = max(16, min(board_y, self.height - 16))
        point = (board_x, board_y)

        color = (40, 40, 40) if self.active_tool == "pen" else (255, 255, 255)
        thickness = 4 if self.active_tool == "pen" else 24

        if self.last_point is None:
            self.last_point = point
        cv2.line(self.sketch_layer, self.last_point, point, color, thickness, cv2.LINE_AA)
        self.last_point = point

    def snapshot(self) -> np.ndarray:
        return self.render()

    def render(self, camera_frame: Optional[np.ndarray] = None) -> np.ndarray:
        board = self._blank_board()
        mask = np.any(self.sketch_layer < 250, axis=2)
        board[mask] = self.sketch_layer[mask]

        self._draw_sidebar(board)
        self._draw_header(board)

        if camera_frame is not None:
            inset = cv2.resize(camera_frame, (280, 210))
            y1, y2 = 20, 230
            x1, x2 = self.width - 300, self.width - 20
            board[y1:y2, x1:x2] = inset
            cv2.rectangle(board, (x1, y1), (x2, y2), (30, 30, 30), 2)
            cv2.putText(
                board,
                "Live Camera",
                (x1 + 12, y1 + 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
            )

        return board

    def _blank_board(self) -> np.ndarray:
        board = np.full((self.height, self.width, 3), 248, dtype=np.uint8)
        for x in range(0, self.width, 40):
            cv2.line(board, (x, 0), (x, self.height), (235, 235, 235), 1)
        for y in range(0, self.height, 40):
            cv2.line(board, (0, y), (self.width, y), (235, 235, 235), 1)
        return board

    def _draw_header(self, board: np.ndarray) -> None:
        cv2.rectangle(board, (0, 0), (self.width, 72), (250, 250, 250), -1)
        cv2.line(board, (0, 72), (self.width, 72), (220, 220, 220), 2)
        cv2.putText(
            board,
            "Jarvis Design Board",
            (320, 42),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (30, 30, 30),
            2,
        )
        cv2.putText(
            board,
            f"Tool: {self.active_tool}",
            (320, 64),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (75, 75, 75),
            1,
        )
        cv2.putText(
            board,
            "Voice: open board | switch tool | clear | save",
            (520, 64),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (75, 75, 75),
            1,
        )

    def _draw_sidebar(self, board: np.ndarray) -> None:
        cv2.rectangle(board, (0, 0), (280, self.height), (28, 31, 39), -1)
        cv2.rectangle(board, (16, 88), (264, self.height - 20), (39, 44, 54), -1)

        title = str(self.brief.get("title") or "Jarvis Concept Board")
        cv2.putText(
            board,
            title[:24],
            (30, 126),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        y = 168
        y = self._draw_section(board, "Constraints", self.brief.get("constraints", []), y)
        y = self._draw_section(board, "Next Tasks", self.brief.get("tasks", []), y)
        self._draw_section(board, "Notes", self.brief.get("notes", []), y)

    def _draw_section(self, board: np.ndarray, title: str, items: object, y: int) -> int:
        cv2.putText(
            board,
            title,
            (30, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (255, 214, 102),
            2,
        )
        y += 18
        values = list(items) if isinstance(items, list) else [str(items)]
        if not values:
            values = ["Waiting for project context"]

        for value in values[:4]:
            for line in textwrap.wrap(str(value), width=26):
                cv2.putText(
                    board,
                    f"- {line}",
                    (34, y + 18),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    (240, 240, 240),
                    1,
                )
                y += 20
        return y + 16

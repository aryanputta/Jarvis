import cv2
import time
from pathlib import Path

from app.agents.jarvis_agent import JarvisAgent
from app.agents.memory_agent import MemoryAgent
from app.core.hand_detection import HandDetector
from app.core.design_board import DesignBoard
from app.core.command_parser import CommandParser
from app.core.speech_output import speak_text
from app.core.voice_input import listen_command
from app.workflows.session_loader import SessionLoader
from app.workflows.session_saver import SessionSaver
from app.utils.config import (
    CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT,
    USE_WEBCAM, ENABLE_VOICE, COMMAND_COOLDOWN, VIDEO_PATH, DEFAULT_USER_NAME,
    OPEN_DESIGN_BOARD_ON_START, ENABLE_HAND_TRACKING, ENABLE_SPEECH_OUTPUT,
)
from app.utils.helpers import (
    FPSCounter,
    draw_agent_hud,
    draw_fps,
    draw_memory_panel,
    draw_status_banner,
    log_command,
)

WINDOW_NAME = "JarvisOS"


def _build_fallback_frame(message: str | None = None):
    frame = cv2.cvtColor(
        cv2.resize(
            cv2.UMat(FRAME_HEIGHT, FRAME_WIDTH, cv2.CV_8UC1, 24).get(),
            (FRAME_WIDTH, FRAME_HEIGHT),
        ),
        cv2.COLOR_GRAY2BGR,
    )
    cv2.putText(frame, "Camera feed unavailable", (28, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (220, 220, 220), 2)
    if message:
        cv2.putText(frame, message[:72], (28, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)
    return frame


def _install_mouse_handler(board: DesignBoard):
    state = {"drawing": False}

    def _callback(event, x, y, flags, _param):
        if not board.is_open:
            return
        if x > FRAME_WIDTH:
            if event == cv2.EVENT_LBUTTONUP:
                state["drawing"] = False
                board.end_stroke()
            return

        if event == cv2.EVENT_LBUTTONDOWN:
            state["drawing"] = True
            board.begin_stroke(x, y)
            board.draw_at_board_point(x, y)
        elif event == cv2.EVENT_MOUSEMOVE and state["drawing"]:
            board.draw_at_board_point(x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            state["drawing"] = False
            board.draw_at_board_point(x, y)
            board.end_stroke()

    cv2.setMouseCallback(WINDOW_NAME, _callback)


def _render_workspace(board, camera_frame, latest_response, panel_state, agent_status, voice_status, latest_heard, active_project):
    workspace = board.render(camera_frame=camera_frame) if board.is_open else camera_frame
    workspace = draw_status_banner(workspace, latest_response)
    workspace = draw_agent_hud(
        workspace,
        agent_status,
        voice_status,
        latest_heard,
        latest_response,
        active_project,
    )
    return draw_memory_panel(workspace, panel_state)


def _handle_command(command, request_text, board, memory_agent, jarvis_agent, session_saver, active_project):
    task_result = jarvis_agent.handle_task_command(command, request_text, active_project=active_project)
    if task_result is not None:
        if not board.is_open:
            board.open()
        if task_result.preview_image_path:
            board.set_reference_image_from_path(task_result.preview_image_path, title=task_result.preview_title)
        for label, value in task_result.facts.items():
            if value:
                session_saver.record_fact(label, value)
        return task_result.message, task_result.project_name or active_project, False

    if command == "OPEN_BOARD":
        if board.is_open:
            return "Whiteboard already open.", active_project, False
        board.open()
        return "Whiteboard open. I pinned the current design context so you can sketch over it.", active_project, False

    if command == "CLOSE_BOARD":
        board.close()
        return "Whiteboard hidden. Camera view only.", active_project, False

    if command == "CLEAR":
        if board.is_open:
            board.clear()
            return "Whiteboard cleared.", active_project, False
        return "Nothing to clear on the board yet.", active_project, False

    if command == "SWITCH_TOOL":
        tool = board.switch_tool()
        return f"Switched the whiteboard tool to {tool}.", active_project, False

    if command == "SAVE":
        if not board.is_open:
            return "Open the whiteboard first, then I can save the current sketch.", active_project, False
        label = active_project or "jarvis-workspace"
        saved = memory_agent.save_sketch_snapshot(
            board.snapshot(),
            label=label,
            detected_object=active_project,
            metadata={"source": "design_board", "tool": board.active_tool},
        )
        session_saver.record_fact("saved_sketch_version", saved["version"])
        if active_project:
            memory_agent.save_project_state(
                active_project,
                {"last_version": f"design board v{saved['version']}"},
            )
        return f"Saved {label} sketch version {saved['version']}.", active_project, False

    if command == "CLEAR_MEMORY":
        memory_agent.clear_memory()
        board.clear()
        return "Cleared long-term memory for this user.", None, False

    if command == "EXPORT_MEMORY":
        export = memory_agent.export_memory()
        return f"Exported memory to {Path(export['export_path']).name}.", active_project, False

    if command == "DISABLE_LEARNING":
        memory_agent.set_learning_mode(False)
        return "Learning mode disabled. I will stop storing new preferences.", active_project, False

    if command == "ENABLE_LEARNING":
        memory_agent.set_learning_mode(True)
        return "Learning mode enabled again.", active_project, False

    if command == "DELETE_PROJECT_MEMORY":
        if not active_project:
            return "No active project is loaded yet.", active_project, False
        memory_agent.delete_project_memory(active_project)
        board.clear()
        return f"Deleted stored memory for {active_project}.", None, False

    if command == "STOP":
        return "Stopping the session and saving a summary.", active_project, True

    return None, active_project, False


def run():
    parser = CommandParser()
    fps_counter = FPSCounter()
    memory_agent = MemoryAgent(user_name=DEFAULT_USER_NAME)
    jarvis_agent = JarvisAgent(memory_agent)
    session_loader = SessionLoader(memory_agent)
    session_saver = SessionSaver(memory_agent)
    board = DesignBoard(width=FRAME_WIDTH, height=FRAME_HEIGHT)
    if OPEN_DESIGN_BOARD_ON_START:
        board.open()

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    _install_mouse_handler(board)

    source = CAMERA_INDEX if USE_WEBCAM else VIDEO_PATH
    cap = cv2.VideoCapture(source)
    camera_message = None
    if not cap.isOpened():
        camera_message = "Grant camera permission or keep using mouse mode."

    latest_response = memory_agent.session_greeting()
    voice_status = "idle"
    latest_heard = None
    agent_status = "starting"
    startup_frame = _build_fallback_frame("Starting Jarvis. Whiteboard is available with mouse input.")
    startup_panel = {
        "header": f"Jarvis Memory | {DEFAULT_USER_NAME}",
        "learning_mode": True,
        "voice_status": voice_status,
        "latest_heard": latest_heard,
        "latest_response": latest_response,
        "recent_actions": [],
    }
    cv2.imshow(
        WINDOW_NAME,
        _render_workspace(
            board,
            startup_frame,
            latest_response,
            startup_panel,
            agent_status,
            voice_status,
            latest_heard,
            None,
        ),
    )
    cv2.waitKey(1)

    detector = None
    hand_tracking_enabled = False
    if ENABLE_HAND_TRACKING:
        try:
            detector = HandDetector()
            hand_tracking_enabled = True
            latest_response = "Whiteboard ready. Hand tracking and mouse drawing are enabled."
        except Exception as exc:
            latest_response = f"Whiteboard ready. Hand tracking is unavailable, so use mouse drawing. ({exc})"
    if ENABLE_SPEECH_OUTPUT:
        speak_text(latest_response)
    agent_status = "ready"

    last_command_time = 0
    active_project = None
    latest_text = None
    should_stop = False
    last_spoken_response = latest_response
    pointer_pause_until = 0.0
    panel_state = session_loader.build_panel(
        latest_response=latest_response,
        voice_status=voice_status,
        latest_heard=latest_heard,
    )

    while not should_stop:
        ret, frame = cap.read()
        x = y = None
        if ret:
            frame = cv2.flip(frame, 1)
            frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
            if hand_tracking_enabled and detector is not None:
                frame, x, y, landmarks = detector.detect(frame)
            else:
                landmarks = None
        else:
            frame = _build_fallback_frame(camera_message)
            landmarks = None

        command = None

        now = time.time()
        if ENABLE_VOICE:
            can_consume_text = now - last_command_time >= COMMAND_COOLDOWN
            voice_event = listen_command(consume_text=can_consume_text)
            voice_status = voice_event["status"]
            if voice_status == "listening":
                agent_status = "listening"
            elif voice_status == "processing":
                agent_status = "thinking"
            elif voice_status == "heard":
                agent_status = "heard"
            elif voice_status in {"speech_api_error", "mic_error"}:
                agent_status = "voice issue"
            elif voice_status == "did_not_understand":
                agent_status = "did not understand"
            elif agent_status not in {"responding", "action complete"}:
                agent_status = "ready"

            if voice_event.get("last_heard"):
                latest_heard = voice_event["last_heard"]

            text = voice_event.get("text") if can_consume_text else None
            if text:
                latest_text = text
                latest_heard = text
                agent_status = "thinking"
                session_saver.record_user_text(text)
                observation = memory_agent.observe_text(text, active_project=active_project)
                active_project = observation.get("project_name") or active_project
                for fact in observation.get("facts", []):
                    session_saver.record_fact(fact["label"], fact["value"])

                command = parser.parse(text)
                last_command_time = now
                if command:
                    log_command(command)
                    session_saver.record_tool_usage(
                        command,
                        context={"text": text, "project": active_project},
                    )
                    latest_response, active_project, should_stop = _handle_command(
                        command,
                        text,
                        board,
                        memory_agent,
                        jarvis_agent,
                        session_saver,
                        active_project,
                    )
                    if command in {"CLEAR", "CLEAR_MEMORY", "DELETE_PROJECT_MEMORY"}:
                        pointer_pause_until = now + 0.45
                    agent_status = "action complete"
                    context = session_loader.load(text, project_name=active_project)
                    board.update_brief(
                        active_project,
                        context["project_state"],
                        latest_response,
                        context["relevant_memories"],
                    )
                else:
                    response = jarvis_agent.handle_conversation(text, active_project=active_project)
                    context = response.context or session_loader.load(text, project_name=active_project)
                    active_project = response.project_name or active_project
                    latest_response = response.message
                    agent_status = "responding"
                    board.update_brief(
                        active_project,
                        context["project_state"],
                        latest_response,
                        context["relevant_memories"],
                    )
                session_saver.record_assistant_response(latest_response)
            elif voice_event.get("error") and voice_event["status"] in {"speech_api_error", "mic_error"}:
                latest_response = f"Voice input issue: {voice_event['error']}"
                agent_status = "voice issue"

        if x is not None and y is not None:
            cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
        if now >= pointer_pause_until:
            board.update_from_pointer(x, y, FRAME_WIDTH, FRAME_HEIGHT)
        else:
            board.end_stroke()

        if command is not None:
            cv2.putText(frame, command, (20, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        frame = draw_fps(frame, fps_counter.tick())

        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord("q"):
            break
        if key == ord("c"):
            board.clear()
            latest_response = "Whiteboard cleared."
            pointer_pause_until = time.time() + 0.45
            agent_status = "action complete"
        elif key == ord("t"):
            latest_response = f"Switched the whiteboard tool to {board.switch_tool()}."
            agent_status = "action complete"
        elif key == ord("s"):
            latest_response, active_project, _ = _handle_command(
                "SAVE",
                "save",
                board,
                memory_agent,
                jarvis_agent,
                session_saver,
                active_project,
            )
            agent_status = "action complete"
            context = session_loader.load("save", project_name=active_project)
            board.update_brief(
                active_project,
                context["project_state"],
                latest_response,
                context["relevant_memories"],
            )

        if ENABLE_SPEECH_OUTPUT and latest_response != last_spoken_response:
            speak_text(latest_response)
            last_spoken_response = latest_response

        panel_state = session_loader.build_panel(
            latest_text=latest_text,
            latest_response=latest_response,
            project_name=active_project,
            voice_status=voice_status,
            latest_heard=latest_heard,
        )
        cv2.imshow(
            WINDOW_NAME,
            _render_workspace(
                board,
                frame,
                latest_response,
                panel_state,
                agent_status,
                voice_status,
                latest_heard,
                active_project,
            ),
        )
    session_saver.finalize(active_project)
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run()

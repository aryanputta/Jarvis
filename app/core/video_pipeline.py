import cv2
import time

from app.agents.jarvis_agent import JarvisAgent
from app.agents.memory_agent import MemoryAgent
from app.core.hand_detection import HandDetector
from app.core.design_board import DesignBoard
from app.core.command_parser import CommandParser
from app.core.voice_input import listen_command
from app.workflows.session_loader import SessionLoader
from app.workflows.session_saver import SessionSaver
from app.utils.config import (
    CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT,
    USE_WEBCAM, ENABLE_VOICE, COMMAND_COOLDOWN, VIDEO_PATH, DEFAULT_USER_NAME,
    OPEN_DESIGN_BOARD_ON_START,
)
from app.utils.helpers import FPSCounter, draw_fps, draw_memory_panel, draw_status_banner, log_command


def _handle_command(command, request_text, board, memory_agent, jarvis_agent, session_saver, active_project):
    task_result = jarvis_agent.handle_task_command(command, request_text, active_project=active_project)
    if task_result is not None:
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
    detector = HandDetector()
    parser = CommandParser()
    fps_counter = FPSCounter()
    memory_agent = MemoryAgent(user_name=DEFAULT_USER_NAME)
    jarvis_agent = JarvisAgent(memory_agent)
    session_loader = SessionLoader(memory_agent)
    session_saver = SessionSaver(memory_agent)
    board = DesignBoard(width=FRAME_WIDTH, height=FRAME_HEIGHT)
    if OPEN_DESIGN_BOARD_ON_START:
        board.open()

    source = CAMERA_INDEX if USE_WEBCAM else VIDEO_PATH
    cap = cv2.VideoCapture(source)

    last_command_time = 0
    active_project = None
    latest_text = None
    latest_response = memory_agent.session_greeting()
    should_stop = False
    panel_state = session_loader.build_panel(latest_response=latest_response)

    while not should_stop:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

        frame, x, y, landmarks = detector.detect(frame)

        command = None

        if ENABLE_VOICE:
            now = time.time()
            if now - last_command_time >= COMMAND_COOLDOWN:
                text = listen_command()
                if text:
                    latest_text = text
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
                    else:
                        response = jarvis_agent.handle_conversation(text, active_project=active_project)
                        context = response.context or session_loader.load(text, project_name=active_project)
                        active_project = response.project_name or active_project
                        latest_response = response.message
                        board.update_brief(
                            active_project,
                            context["project_state"],
                            latest_response,
                            context["relevant_memories"],
                        )
                    context = session_loader.load(latest_text or "", project_name=active_project)
                    board.update_brief(
                        active_project,
                        context["project_state"],
                        latest_response,
                        context["relevant_memories"],
                    )
                    session_saver.record_assistant_response(latest_response)
                    panel_state = session_loader.build_panel(
                        latest_text=latest_text,
                        latest_response=latest_response,
                        project_name=active_project,
                    )

        if x is not None and y is not None:
            cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
        board.update_from_pointer(x, y, FRAME_WIDTH, FRAME_HEIGHT)

        if command is not None:
            cv2.putText(frame, command, (20, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        frame = draw_fps(frame, fps_counter.tick())
        workspace = board.render(camera_frame=frame) if board.is_open else frame
        workspace = draw_status_banner(workspace, latest_response)
        cv2.imshow("Feed", draw_memory_panel(workspace, panel_state))

        if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
            break

    session_saver.finalize(active_project)
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run()

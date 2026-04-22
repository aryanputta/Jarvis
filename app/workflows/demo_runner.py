from pathlib import Path
from typing import Dict

import numpy as np

from app.agents.jarvis_agent import JarvisAgent
from app.agents.memory_agent import MemoryAgent
from app.core.design_board import DesignBoard
from app.db.store import MemoryStore
from app.utils.config import FRAME_HEIGHT, FRAME_WIDTH
from app.workflows.session_loader import SessionLoader
from app.workflows.session_saver import SessionSaver


def run_demo(output_dir: str) -> Dict[str, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    store = MemoryStore(db_path=str(root / "demo_memory.db"), default_user="Aryan")
    memory_agent = MemoryAgent(user_name="Aryan", store=store)
    jarvis_agent = JarvisAgent(memory_agent)
    jarvis_agent.email_composer.outbox_dir = root / "outbox"
    jarvis_agent.email_composer.outbox_dir.mkdir(parents=True, exist_ok=True)
    jarvis_agent.email_composer.sent_dir = root / "outbox" / "sent"
    jarvis_agent.email_composer.sent_dir.mkdir(parents=True, exist_ok=True)
    jarvis_agent.pitch_composer.export_dir = root / "exports" / "pitches"
    jarvis_agent.pitch_composer.export_dir.mkdir(parents=True, exist_ok=True)
    jarvis_agent.build_plan_composer.export_dir = root / "exports" / "plans"
    jarvis_agent.build_plan_composer.export_dir.mkdir(parents=True, exist_ok=True)
    jarvis_agent.bom_composer.export_dir = root / "exports" / "boms"
    jarvis_agent.bom_composer.export_dir.mkdir(parents=True, exist_ok=True)
    jarvis_agent.design_critic.export_dir = root / "exports" / "reviews"
    jarvis_agent.design_critic.export_dir.mkdir(parents=True, exist_ok=True)
    jarvis_agent.demo_script_composer.export_dir = root / "exports" / "demos"
    jarvis_agent.demo_script_composer.export_dir.mkdir(parents=True, exist_ok=True)
    board = DesignBoard(width=FRAME_WIDTH, height=FRAME_HEIGHT)
    session_loader = SessionLoader(memory_agent)
    session_saver = SessionSaver(memory_agent)

    request_text = "Jarvis help me build a 6G AI-RAN edge node over the summer."
    observation = memory_agent.observe_text(request_text)
    project_name = observation["project_name"] or "6g ai-ran edge node"
    memory_agent.save_project_state(
        project_name,
        {
            "last_version": "mechanical layout v1",
            "open_tasks": ["CAD export", "power budget review", "parts list cleanup"],
            "preferred_design": "compact",
            "budget_limit": 200,
        },
    )
    session_saver.record_user_text(request_text)

    board.open()
    context = session_loader.load(query=request_text, project_name=project_name)
    board.update_brief(
        project_name,
        context["project_state"],
        "I loaded the design board and pinned the current project context.",
        context["relevant_memories"],
    )

    for x, y in [(180, 220), (260, 280), (340, 240), (420, 320), (520, 300)]:
        board.update_from_pointer(x, y, FRAME_WIDTH, FRAME_HEIGHT)

    board_path = root / "demo_board.png"
    import cv2

    cv2.imwrite(str(board_path), board.render(camera_frame=np.full((FRAME_HEIGHT, FRAME_WIDTH, 3), 220, dtype=np.uint8)))
    saved_sketch = memory_agent.save_sketch_snapshot(
        str(board_path),
        label=project_name,
        detected_object=project_name,
        metadata={"source": "demo_runner"},
    )
    memory_agent.save_project_state(project_name, {"last_version": f"design board v{saved_sketch['version']}"})
    session_saver.record_fact("saved_sketch_version", saved_sketch["version"])

    email_request = (
        "Draft and send an email to Shrihan about this CAD design and say I want to build it over the summer."
    )
    draft = jarvis_agent.handle_task_command("WRITE_EMAIL", email_request, active_project=project_name)
    pitch = jarvis_agent.handle_task_command(
        "PITCH_PROJECT",
        "Give me a project pitch on this CAD model and tell me how to present it.",
        active_project=project_name,
    )
    plan = jarvis_agent.handle_task_command(
        "BUILD_PLAN",
        "Make a build plan for this CAD project.",
        active_project=project_name,
    )
    bom = jarvis_agent.handle_task_command(
        "GENERATE_BOM",
        "Generate a BOM and cost estimate for this design.",
        active_project=project_name,
    )
    review = jarvis_agent.handle_task_command(
        "CRITIQUE_DESIGN",
        "Critique this CAD design and tell me how to improve it.",
        active_project=project_name,
    )
    demo_script = jarvis_agent.handle_task_command(
        "DEMO_SCRIPT",
        "What should I say in the demo presentation for this project?",
        active_project=project_name,
    )
    session_saver.record_user_text(email_request)
    session_saver.record_assistant_response(
        "I drafted the email to Shrihan, attached the latest design, and completed a demo send archive."
    )
    for result in [draft, pitch, plan, bom, review, demo_script]:
        if result is None:
            continue
        for label, value in result.facts.items():
            if value:
                session_saver.record_fact(label, value)
    session_saver.finalize(project_name)

    return {
        "project_name": project_name,
        "board_path": str(board_path),
        "draft_path": str(draft.artifact_paths[0]) if draft else "",
        "draft_json_path": str(draft.artifact_paths[1]) if draft and len(draft.artifact_paths) > 1 else "",
        "delivery_state": str(draft.facts.get("email_delivery_state", "")) if draft else "",
        "sent_path": str(jarvis_agent.email_composer.sent_dir / Path(draft.artifact_paths[0]).name) if draft else "",
        "pitch_path": str(pitch.artifact_paths[0]) if pitch else "",
        "plan_path": str(plan.artifact_paths[0]) if plan else "",
        "bom_path": str(bom.artifact_paths[0]) if bom else "",
        "review_path": str(review.artifact_paths[0]) if review else "",
        "demo_script_path": str(demo_script.artifact_paths[0]) if demo_script else "",
        "latest_response": "I drafted the email to Shrihan, attached the latest design, and completed a demo send archive.",
    }


def main() -> None:
    output = run_demo("app/data/demo")
    print("Jarvis demo complete.")
    for key, value in output.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()

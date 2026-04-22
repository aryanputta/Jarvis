from pathlib import Path

from app.agents.memory_agent import MemoryAgent
from app.db.store import MemoryStore
from app.workflows.demo_runner import run_demo
from app.workflows.email_composer import EmailComposer
from app.workflows.project_pitch import ProjectPitchComposer


def build_agent(tmp_path):
    store = MemoryStore(db_path=str(tmp_path / "jarvis_memory.db"), default_user="Aryan")
    return MemoryAgent(user_name="Aryan", store=store)


def test_save_and_load_preferences(tmp_path):
    agent = build_agent(tmp_path)

    agent.save_preference("prefers_visual_workflow", True)
    agent.save_preference("preferred_response_style", "concise")

    preferences = agent.load_preferences()
    assert preferences["prefers_visual_workflow"] is True
    assert preferences["preferred_response_style"] == "concise"


def test_project_state_round_trip(tmp_path):
    agent = build_agent(tmp_path)

    agent.save_project_state(
        "robotic arm",
        {
            "last_version": "2 joint claw design",
            "open_tasks": ["CAD export", "motor search"],
            "notes": "wants cheaper parts",
        },
    )

    project_state = agent.load_project_state("robotic arm")
    assert project_state["last_version"] == "2 joint claw design"
    assert sorted(project_state["open_tasks"]) == ["CAD export", "motor search"]
    assert project_state["summary"] == "wants cheaper parts"


def test_session_summaries_are_saved(tmp_path):
    agent = build_agent(tmp_path)

    agent.save_session_summary(
        "Worked on a GPU scheduler and tightened memory usage.",
        facts=[{"label": "focus", "value": "cuda scheduler"}],
    )

    sessions = agent.store.list_recent_sessions(user_name="Aryan", limit=1)
    assert sessions[0]["summary"] == "Worked on a GPU scheduler and tightened memory usage."
    assert sessions[0]["facts"][0]["value"] == "cuda scheduler"


def test_duplicate_memory_events_are_deduplicated(tmp_path):
    agent = build_agent(tmp_path)

    agent.store.save_memory_event(
        memory_type="rejected_suggestion",
        subject="robotic arm",
        content="Rejected the expensive servo option.",
        user_name="Aryan",
        metadata={"reason": "cost"},
        importance=0.8,
    )
    agent.store.save_memory_event(
        memory_type="rejected_suggestion",
        subject="robotic arm",
        content="Rejected the expensive servo option.",
        user_name="Aryan",
        metadata={"reason": "cost"},
        importance=0.9,
    )

    events = agent.store.list_memory_events(user_name="Aryan", limit=10)
    assert len(events) == 1
    assert events[0]["importance"] == 0.9


def test_memory_ranking_prefers_relevant_project_context(tmp_path):
    agent = build_agent(tmp_path)

    agent.save_project_state(
        "robotic arm",
        {
            "last_version": "3 joint compact design",
            "open_tasks": ["motor search"],
            "preferred_parts": ["MG996R servos"],
        },
    )
    agent.save_session_summary("Budget for the robotic arm is under 100 dollars.")
    agent.save_session_summary("Write concise professional emails for internship outreach.")

    memories = agent.retrieve_relevant_memories("robotic arm budget motors", limit=3)

    assert memories
    top_memory = memories[0]
    assert top_memory["memory_type"] in {"project", "session"}
    assert "robotic arm" in f"{top_memory['subject']} {top_memory['content']}".lower()


def test_observe_text_learns_meaningful_preferences(tmp_path):
    agent = build_agent(tmp_path)

    observation = agent.observe_text(
        "I need this under 100 dollars and I prefer MG996R servos for the compact design.",
        active_project="robotic arm",
    )

    preferences = agent.load_preferences()
    project_state = agent.load_project_state(observation["project_name"])

    assert preferences["budget_limit"] == 100
    assert project_state["preferred_design"] == "compact"
    assert project_state["preferred_parts"][0] == "MG996R servos"


def test_email_composer_builds_draft_with_attachment(tmp_path):
    agent = build_agent(tmp_path)
    agent.save_project_state(
        "6g ai-ran edge node",
        {
            "last_version": "design board v2",
            "open_tasks": ["CAD export", "cost review"],
            "preferred_design": "compact",
            "budget_limit": 200,
        },
    )
    source_design = tmp_path / "edge-node.png"
    source_design.write_bytes(b"fake-png-bytes")
    agent.save_sketch_snapshot(str(source_design), label="6g ai-ran edge node")

    composer = EmailComposer(
        agent,
        outbox_dir=str(tmp_path / "outbox"),
        sent_dir=str(tmp_path / "outbox" / "sent"),
    )
    draft = composer.compose(
        "Write an email about this CAD design and send it to me and my friend Shrihan saying I want to build this over the summer.",
        project_name="6g ai-ran edge node",
    )

    assert draft["project_name"] == "6g ai-ran edge node"
    assert draft["recipients"] == ["Aryan", "Shrihan"]
    assert "summer" in draft["subject"].lower()
    assert draft["style"] == "collaborative"
    assert "really solid project to build over the summer" in draft["body"]
    assert "I'd love your take before I lock anything in." in draft["body"]
    assert draft["attachments"]
    assert draft["delivery_state"] == "sent_demo"
    assert Path(draft["eml_path"]).exists()
    assert Path(draft["json_path"]).exists()
    assert Path(draft["sent_eml_path"]).exists()


def test_demo_runner_executes_end_to_end(tmp_path):
    result = run_demo(str(tmp_path / "demo"))

    assert result["project_name"] == "6g ai-ran edge node"
    assert result["delivery_state"] == "sent_demo"
    assert Path(result["board_path"]).exists()
    assert Path(result["draft_path"]).exists()
    assert Path(result["draft_json_path"]).exists()
    assert Path(result["sent_path"]).exists()
    assert Path(result["pitch_path"]).exists()
    assert Path(result["plan_path"]).exists()
    assert Path(result["bom_path"]).exists()
    assert Path(result["review_path"]).exists()
    assert Path(result["demo_script_path"]).exists()


def test_project_pitch_composer_writes_pitch_file(tmp_path):
    agent = build_agent(tmp_path)
    agent.save_project_state(
        "robotic arm",
        {
            "last_version": "3 joint compact design",
            "open_tasks": ["motor search", "cad export"],
            "preferred_design": "compact",
            "budget_limit": 100,
        },
    )
    composer = ProjectPitchComposer(agent, export_dir=str(tmp_path / "exports"))
    pitch = composer.compose("Give me a project pitch on this CAD model and tell me how to present it.")

    assert pitch["project_name"] == "robotic arm"
    assert "presentation_tips" in pitch
    assert Path(pitch["output_path"]).exists()

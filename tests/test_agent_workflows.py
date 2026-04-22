from pathlib import Path

from app.agents.jarvis_agent import JarvisAgent
from app.agents.memory_agent import MemoryAgent
from app.db.store import MemoryStore


def build_agent(tmp_path):
    store = MemoryStore(db_path=str(tmp_path / "jarvis_memory.db"), default_user="Aryan")
    memory_agent = MemoryAgent(user_name="Aryan", store=store)
    memory_agent.save_project_state(
        "6g ai-ran edge node",
        {
            "last_version": "design board v2",
            "open_tasks": ["CAD export", "power budget review"],
            "preferred_design": "compact",
            "preferred_parts": ["Jetson Orin Nano"],
            "budget_limit": 200,
        },
    )
    return JarvisAgent(memory_agent)


def test_build_plan_command_generates_artifact(tmp_path):
    agent = build_agent(tmp_path)
    result = agent.handle_task_command(
        "BUILD_PLAN",
        "Make a build plan for this CAD project.",
        active_project="6g ai-ran edge node",
    )

    assert result is not None
    assert "plan" in result.message.lower()
    assert result.project_name == "6g ai-ran edge node"
    assert result.artifact_paths
    assert Path(result.artifact_paths[0]).exists()


def test_bom_command_generates_cost_estimate(tmp_path):
    agent = build_agent(tmp_path)
    result = agent.handle_task_command(
        "GENERATE_BOM",
        "Generate a BOM and cost estimate for this design.",
        active_project="6g ai-ran edge node",
    )

    assert result is not None
    assert "bom" in result.message.lower()
    assert result.facts["bom_total"] > 0
    assert Path(result.artifact_paths[0]).exists()
    assert Path(result.artifact_paths[1]).exists()


def test_design_review_and_demo_script_are_available(tmp_path):
    agent = build_agent(tmp_path)
    review = agent.handle_task_command(
        "CRITIQUE_DESIGN",
        "Critique this CAD design and tell me how to improve it.",
        active_project="6g ai-ran edge node",
    )
    demo = agent.handle_task_command(
        "DEMO_SCRIPT",
        "What should I say in the demo for this project?",
        active_project="6g ai-ran edge node",
    )

    assert review is not None
    assert demo is not None
    assert Path(review.artifact_paths[0]).exists()
    assert Path(demo.artifact_paths[0]).exists()


def test_handle_conversation_surfaces_capabilities(tmp_path):
    agent = build_agent(tmp_path)
    result = agent.handle_conversation("What can you do for this project?", active_project="6g ai-ran edge node")

    assert "draft and demo-send project emails" in result.message
    assert result.project_name == "6g ai-ran edge node"

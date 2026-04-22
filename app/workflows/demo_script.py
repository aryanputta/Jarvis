import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.agents.memory_agent import MemoryAgent
from app.utils.config import MEMORY_EXPORT_DIR


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "project"


class DemoScriptComposer:
    def __init__(self, memory_agent: MemoryAgent, export_dir: str = MEMORY_EXPORT_DIR):
        self.memory_agent = memory_agent
        self.export_dir = Path(export_dir) / "demos"
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def compose(self, request_text: str, project_name: Optional[str] = None) -> Dict[str, object]:
        target_project = (
            project_name
            or self.memory_agent.infer_project_name(request_text)
            or self.memory_agent.latest_project_name()
            or "design concept"
        )
        project_state = self.memory_agent.load_project_state(target_project) or {"project": target_project}
        payload = self._build_script(target_project, project_state)
        output_path = self._write_script_file(target_project, payload)

        self.memory_agent.store.save_memory_event(
            memory_type="demo_script",
            subject=target_project,
            content=payload["headline"],
            user_name=self.memory_agent.user_name,
            metadata={"output_path": str(output_path), "talk_track": payload["talk_track"]},
            importance=0.75,
        )
        self.memory_agent.save_project_state(target_project, {"last_demo_script_path": str(output_path)})

        payload["output_path"] = str(output_path)
        return payload

    def _build_script(self, project_name: str, project_state: Dict[str, object]) -> Dict[str, object]:
        version = project_state.get("last_version", "latest concept")
        preferred_design = project_state.get("preferred_design", "modular")
        open_tasks = project_state.get("open_tasks") or []

        talk_track = [
            f"This is JarvisOS, my personal AI agent workspace for {project_name}.",
            "I can sketch directly on the design board and Jarvis keeps the useful project context across sessions.",
            f"Jarvis remembers that this design is currently at {version} and tracks my preferred {preferred_design} direction.",
            "From the same workspace, I can ask Jarvis to draft an email, build a pitch, estimate the BOM, critique the design, or plan next steps.",
            "That means the assistant is not just answering questions. It is taking the current design context and doing real project work for me.",
        ]
        if open_tasks:
            talk_track.append(f"Right now the next steps Jarvis is tracking are {', '.join(open_tasks[:3])}.")

        return {
            "project_name": project_name,
            "headline": f"{project_name.title()} demo script",
            "talk_track": talk_track,
        }

    def _write_script_file(self, project_name: str, payload: Dict[str, object]) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = self.export_dir / f"{_slugify(project_name)}-{timestamp}.md"
        lines: List[str] = [f"# {payload['headline']}", "", "## Talk Track"]
        lines.extend([f"{idx}. {line}" for idx, line in enumerate(payload["talk_track"], start=1)])
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output_path

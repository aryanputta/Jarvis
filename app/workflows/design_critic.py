import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.agents.memory_agent import MemoryAgent
from app.utils.config import MEMORY_EXPORT_DIR


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "project"


class DesignCritic:
    def __init__(self, memory_agent: MemoryAgent, export_dir: str = MEMORY_EXPORT_DIR):
        self.memory_agent = memory_agent
        self.export_dir = Path(export_dir) / "reviews"
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def compose(self, request_text: str, project_name: Optional[str] = None) -> Dict[str, object]:
        target_project = (
            project_name
            or self.memory_agent.infer_project_name(request_text)
            or self.memory_agent.latest_project_name()
            or "design concept"
        )
        project_state = self.memory_agent.load_project_state(target_project) or {"project": target_project}
        payload = self._build_review(target_project, project_state)
        output_path = self._write_review_file(target_project, payload)

        self.memory_agent.store.save_memory_event(
            memory_type="design_review",
            subject=target_project,
            content=payload["headline"],
            user_name=self.memory_agent.user_name,
            metadata={"output_path": str(output_path), "risks": payload["risks"]},
            importance=0.77,
        )
        self.memory_agent.save_project_state(target_project, {"last_review_path": str(output_path)})

        payload["output_path"] = str(output_path)
        return payload

    def _build_review(self, project_name: str, project_state: Dict[str, object]) -> Dict[str, object]:
        preferred_design = project_state.get("preferred_design", "modular")
        version = project_state.get("last_version", "latest concept")
        budget_limit = project_state.get("budget_limit")
        open_tasks = project_state.get("open_tasks") or []

        strengths = [
            f"The project already has a defined design direction around a {preferred_design} layout.",
            f"The current {version} state is concrete enough to turn into a plan, BOM, and presentation.",
        ]
        risks = [
            "Mechanical interfaces may still be underspecified if mount locations and tolerances are not locked.",
            "Cost can drift quickly if the parts list is not validated against the actual budget.",
            "The design may be harder to pitch if the build narrative is not tied to a clear problem statement.",
        ]
        improvements = [
            "Add one slide or board section that explains the problem and why this system matters.",
            "Resolve the top 2-3 open tasks before calling the CAD design final.",
            "Capture one cleaner annotated design snapshot for sharing and demo use.",
        ]
        if budget_limit is not None:
            improvements.append(f"Keep a running BOM and trim optional components to stay under ${budget_limit}.")
        if open_tasks:
            improvements.append(f"Prioritize: {', '.join(open_tasks[:3])}.")

        return {
            "project_name": project_name,
            "headline": f"{project_name.title()} design critique",
            "strengths": strengths,
            "risks": risks,
            "improvements": improvements,
        }

    def _write_review_file(self, project_name: str, payload: Dict[str, object]) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = self.export_dir / f"{_slugify(project_name)}-{timestamp}.md"
        lines: List[str] = [f"# {payload['headline']}", "", "## Strengths"]
        lines.extend([f"- {item}" for item in payload["strengths"]])
        lines.extend(["", "## Risks"])
        lines.extend([f"- {item}" for item in payload["risks"]])
        lines.extend(["", "## Improvements"])
        lines.extend([f"- {item}" for item in payload["improvements"]])
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output_path

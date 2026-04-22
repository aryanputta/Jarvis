import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.agents.memory_agent import MemoryAgent
from app.utils.config import MEMORY_EXPORT_DIR


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "project"


class BuildPlanComposer:
    def __init__(self, memory_agent: MemoryAgent, export_dir: str = MEMORY_EXPORT_DIR):
        self.memory_agent = memory_agent
        self.export_dir = Path(export_dir) / "plans"
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def compose(self, request_text: str, project_name: Optional[str] = None) -> Dict[str, object]:
        target_project = (
            project_name
            or self.memory_agent.infer_project_name(request_text)
            or self.memory_agent.latest_project_name()
            or "design concept"
        )
        project_state = self.memory_agent.load_project_state(target_project) or {"project": target_project}
        payload = self._build_plan(target_project, project_state)
        output_path = self._write_plan_file(target_project, payload)

        self.memory_agent.store.save_memory_event(
            memory_type="build_plan",
            subject=target_project,
            content=payload["headline"],
            user_name=self.memory_agent.user_name,
            metadata={"output_path": str(output_path), "next_steps": payload["next_steps"]},
            importance=0.76,
        )
        self.memory_agent.save_project_state(target_project, {"last_plan_path": str(output_path)})

        payload["output_path"] = str(output_path)
        return payload

    def _build_plan(self, project_name: str, project_state: Dict[str, object]) -> Dict[str, object]:
        version = project_state.get("last_version", "latest concept")
        preferred_design = project_state.get("preferred_design", "modular")
        budget_limit = project_state.get("budget_limit")
        parts = project_state.get("preferred_parts") or []
        open_tasks = list(project_state.get("open_tasks") or [])

        phases = [
            {
                "phase": "Frame The Goal",
                "focus": f"Lock the purpose of {project_name} and define what a successful prototype needs to prove.",
            },
            {
                "phase": "Refine The CAD",
                "focus": f"Clean up {version}, tighten the {preferred_design} layout, and resolve missing mounts or interfaces.",
            },
            {
                "phase": "Source Parts",
                "focus": "Turn the concept into a parts list, validate availability, and align the design with the budget.",
            },
            {
                "phase": "Assemble And Integrate",
                "focus": "Build the core structure, install electronics or mechanisms, and wire up the first working system.",
            },
            {
                "phase": "Test And Present",
                "focus": "Run validation, capture a demo, and prepare the talking points for a pitch or review.",
            },
        ]

        next_steps = open_tasks[:4]
        if not next_steps:
            next_steps = ["CAD cleanup", "parts list", "prototype assembly", "demo prep"]
        if parts:
            next_steps.insert(0, f"Lock component choices around {parts[0]}")
        if budget_limit is not None:
            next_steps.append(f"Keep sourcing under ${budget_limit}")

        headline = f"{project_name.title()} build plan"
        summary = (
            f"This plan turns {project_name} from {version} into a buildable prototype by moving through design cleanup, "
            f"sourcing, assembly, and demo readiness."
        )

        return {
            "project_name": project_name,
            "headline": headline,
            "summary": summary,
            "phases": phases,
            "next_steps": next_steps[:5],
        }

    def _write_plan_file(self, project_name: str, payload: Dict[str, object]) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = self.export_dir / f"{_slugify(project_name)}-{timestamp}.md"
        lines: List[str] = [
            f"# {payload['headline']}",
            "",
            str(payload["summary"]),
            "",
            "## Phases",
        ]
        for phase in payload["phases"]:
            lines.extend([f"### {phase['phase']}", str(phase["focus"]), ""])
        lines.append("## Next Steps")
        lines.extend([f"- {step}" for step in payload["next_steps"]])
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output_path

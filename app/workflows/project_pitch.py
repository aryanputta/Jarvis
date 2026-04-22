import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.agents.memory_agent import MemoryAgent
from app.utils.config import MEMORY_EXPORT_DIR


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "project"


class ProjectPitchComposer:
    def __init__(self, memory_agent: MemoryAgent, export_dir: str = MEMORY_EXPORT_DIR):
        self.memory_agent = memory_agent
        self.export_dir = Path(export_dir) / "pitches"
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def compose(self, request_text: str, project_name: Optional[str] = None) -> Dict[str, object]:
        target_project = (
            project_name
            or self.memory_agent.infer_project_name(request_text)
            or self.memory_agent.latest_project_name()
            or "design concept"
        )
        project_state = self.memory_agent.load_project_state(target_project) or {"project": target_project}
        attachment = self._latest_attachment(target_project)
        pitch = self._build_pitch(target_project, project_state, attachment)
        output_path = self._write_pitch_file(target_project, pitch)

        self.memory_agent.store.save_memory_event(
            memory_type="project_pitch",
            subject=target_project,
            content=pitch["headline"],
            user_name=self.memory_agent.user_name,
            metadata={
                "output_path": str(output_path),
                "presentation_tips": pitch["presentation_tips"],
            },
            importance=0.74,
        )
        self.memory_agent.save_project_state(
            target_project,
            {"last_pitch_path": str(output_path)},
        )

        pitch["output_path"] = str(output_path)
        return pitch

    def _build_pitch(
        self,
        project_name: str,
        project_state: Dict[str, object],
        attachment: Optional[Dict[str, object]],
    ) -> Dict[str, object]:
        display_name = project_name.title()
        preferred_design = project_state.get("preferred_design", "modular")
        version = project_state.get("last_version", "latest concept")
        budget_limit = project_state.get("budget_limit")
        open_tasks = project_state.get("open_tasks") or []
        parts = project_state.get("preferred_parts") or []

        headline = f"{display_name}: a personal build-ready system concept"
        elevator_pitch = (
            f"{display_name} is a {preferred_design} CAD concept that turns an early idea into a buildable project "
            f"with clear next steps, reusable modules, and a path to physical prototyping."
        )
        why_it_matters = (
            f"It gives us a concrete way to explain the problem, show the architecture visually, and move from sketching "
            f"to an actual build instead of stopping at a rough mockup."
        )
        design_highlights = [
            f"Current version: {version}",
            f"Design direction: {preferred_design}",
        ]
        if budget_limit is not None:
            design_highlights.append(f"Target budget: under ${budget_limit}")
        if parts:
            design_highlights.append(f"Preferred components: {', '.join(parts[:2])}")
        if attachment:
            design_highlights.append(f"Visual reference ready: {Path(str(attachment['image_path'])).name}")

        presentation_tips = [
            "Start with the problem this project solves before showing the model.",
            "Show the CAD view early so people can anchor the pitch visually.",
            "Walk through the system in layers: purpose, structure, components, and build plan.",
            "End with a concrete next step such as a summer prototype or parts procurement plan.",
        ]
        if open_tasks:
            presentation_tips.append(f"Use the current next steps as momentum: {', '.join(open_tasks[:3])}.")

        return {
            "project_name": project_name,
            "headline": headline,
            "elevator_pitch": elevator_pitch,
            "why_it_matters": why_it_matters,
            "design_highlights": design_highlights,
            "presentation_tips": presentation_tips,
        }

    def _write_pitch_file(self, project_name: str, pitch: Dict[str, object]) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = self.export_dir / f"{_slugify(project_name)}-{timestamp}.md"
        lines: List[str] = [
            f"# {pitch['headline']}",
            "",
            "## Elevator Pitch",
            str(pitch["elevator_pitch"]),
            "",
            "## Why It Matters",
            str(pitch["why_it_matters"]),
            "",
            "## Design Highlights",
        ]
        lines.extend([f"- {item}" for item in pitch["design_highlights"]])
        lines.extend(["", "## Presentation Tips"])
        lines.extend([f"- {item}" for item in pitch["presentation_tips"]])
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output_path

    def _latest_attachment(self, project_name: str) -> Optional[Dict[str, object]]:
        matches = self.memory_agent.store.list_sketch_versions(
            user_name=self.memory_agent.user_name,
            label=project_name,
            limit=1,
        )
        if matches:
            return matches[0]

        recent = self.memory_agent.store.list_sketch_versions(
            user_name=self.memory_agent.user_name,
            limit=1,
        )
        return recent[0] if recent else None

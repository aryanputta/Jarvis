import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

from app.agents.llm_client import JarvisLLMClient
from app.agents.memory_agent import MemoryAgent
from app.utils.config import EXPORT_DIR


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "concept"


class CADDesigner:
    def __init__(
        self,
        memory_agent: MemoryAgent,
        llm_client: Optional[JarvisLLMClient] = None,
        export_dir: Optional[str] = None,
    ):
        self.memory_agent = memory_agent
        self.llm_client = llm_client or JarvisLLMClient()
        self.export_dir = Path(export_dir or (EXPORT_DIR / "cad_concepts"))
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def compose(self, request_text: str, project_name: Optional[str] = None) -> Dict[str, object]:
        target_project = (
            project_name
            or self.memory_agent.infer_project_name(request_text)
            or self.memory_agent.latest_project_name()
            or "concept build"
        )
        project_state = self.memory_agent.load_project_state(target_project) or {"project": target_project}
        relevant_memories = self.memory_agent.retrieve_relevant_memories(request_text, limit=3)
        spec = self._build_spec(request_text, target_project, project_state, relevant_memories)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base_path = self.export_dir / f"{_slugify(target_project)}-{timestamp}"
        preview_path = base_path.with_suffix(".png")
        spec_path = base_path.with_suffix(".json")
        summary_path = base_path.with_suffix(".md")

        preview = self._render_preview(spec)
        cv2.imwrite(str(preview_path), preview)
        spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        summary_path.write_text(self._build_summary(spec), encoding="utf-8")

        self.memory_agent.store.save_memory_event(
            memory_type="cad_concept",
            subject=target_project,
            content=spec["summary"],
            user_name=self.memory_agent.user_name,
            metadata={
                "preview_path": str(preview_path),
                "spec_path": str(spec_path),
                "summary_path": str(summary_path),
                "modules": spec["modules"],
            },
            importance=0.78,
        )
        self.memory_agent.save_project_state(
            target_project,
            {
                "last_cad_preview_path": str(preview_path),
                "last_version": spec["title"],
            },
        )

        return {
            "project_name": target_project,
            "title": spec["title"],
            "summary": spec["summary"],
            "modules": spec["modules"],
            "callouts": spec["callouts"],
            "preview_path": str(preview_path),
            "spec_path": str(spec_path),
            "summary_path": str(summary_path),
            "llm_used": spec.get("llm_used", False),
        }

    def _build_spec(
        self,
        request_text: str,
        project_name: str,
        project_state: Dict[str, object],
        relevant_memories: List[Dict[str, object]],
    ) -> Dict[str, object]:
        if self.llm_client.available():
            instructions = (
                "You are Jarvis, helping design a clean CAD concept. "
                "Return only valid JSON with keys: title, summary, modules, callouts. "
                "modules must be a list of 4 to 6 short component names. "
                "callouts must be a list of 3 short design notes."
            )
            prompt = json.dumps(
                {
                    "request": request_text,
                    "project_name": project_name,
                    "project_state": project_state,
                    "relevant_memories": [memory["content"] for memory in relevant_memories[:3]],
                },
                indent=2,
            )
            payload, error = self.llm_client.generate_json(instructions, prompt)
            if payload and payload.get("modules") and payload.get("summary"):
                return {
                    "title": str(payload.get("title") or f"{project_name.title()} Concept"),
                    "summary": str(payload["summary"]),
                    "modules": [str(item) for item in list(payload["modules"])[:6]],
                    "callouts": [str(item) for item in list(payload.get("callouts") or [])[:3]],
                    "llm_used": True,
                }
            if error:
                project_state["llm_error"] = error

        return self._fallback_spec(project_name, project_state)

    def _fallback_spec(self, project_name: str, project_state: Dict[str, object]) -> Dict[str, object]:
        lowered = project_name.lower()
        if "arm" in lowered:
            modules = ["Base Mount", "Shoulder Joint", "Forearm Link", "Wrist Servo", "Claw End Effector"]
            callouts = ["Compact servo routing", "Low-cost motor selection", "Stable desktop footprint"]
        elif any(token in lowered for token in {"edge", "gpu", "ran", "node"}):
            modules = ["Top Section", "Compute Tray", "Network Shelf", "Power Bay", "Cooling Channel"]
            callouts = ["Modular tray stack", "Front-service wiring", "Compact enclosed frame"]
        else:
            modules = ["Core Frame", "Control Module", "Power Section", "IO Mount", "Cooling Path"]
            callouts = ["Modular layout", "Accessible service path", "Compact build volume"]

        summary_bits = []
        preferred_design = project_state.get("preferred_design")
        if preferred_design:
            summary_bits.append(f"a {preferred_design} layout")
        budget_limit = project_state.get("budget_limit")
        if budget_limit is not None:
            summary_bits.append(f"a budget target around ${budget_limit}")
        summary = f"A concept model for {project_name} centered on " + self._join_bits(summary_bits or ["a clean modular build"])
        return {
            "title": f"{project_name.title()} Concept",
            "summary": summary + ".",
            "modules": modules,
            "callouts": callouts,
            "llm_used": False,
        }

    def _render_preview(self, spec: Dict[str, object]) -> np.ndarray:
        width, height = 960, 540
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        canvas[:] = (18, 25, 41)

        for x in range(0, width, 40):
            cv2.line(canvas, (x, 0), (x, height), (29, 41, 63), 1)
        for y in range(0, height, 40):
            cv2.line(canvas, (0, y), (width, y), (29, 41, 63), 1)

        cv2.putText(canvas, str(spec["title"])[:42], (36, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (236, 241, 255), 2)
        cv2.putText(canvas, "Jarvis CAD Concept", (36, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (123, 181, 255), 1)

        modules = list(spec["modules"])[:6]
        center_x = 470
        top_y = 140
        box_width = 230
        box_height = 42
        gap = 34

        for index, module in enumerate(modules):
            x1 = center_x - box_width // 2 + (index % 2) * 50 - 25
            y1 = top_y + index * gap
            x2 = x1 + box_width
            y2 = y1 + box_height
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (91, 140, 255), 2)
            overlay = canvas.copy()
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (57, 88, 150), -1)
            cv2.addWeighted(overlay, 0.16, canvas, 0.84, 0, canvas)
            cv2.putText(canvas, str(module)[:24], (x1 + 16, y1 + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (245, 247, 255), 1)
            if index > 0:
                prev_y = top_y + (index - 1) * gap + box_height
                cv2.line(canvas, (center_x, prev_y), (center_x, y1), (255, 209, 102), 1)

        cv2.rectangle(canvas, (36, 110), (308, 242), (32, 41, 58), -1)
        cv2.rectangle(canvas, (36, 110), (308, 242), (64, 79, 106), 1)
        cv2.putText(canvas, "Summary", (52, 136), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (255, 209, 102), 1)
        self._draw_wrapped(canvas, str(spec["summary"]), 52, 164, 28, (233, 238, 248))

        cv2.rectangle(canvas, (36, 290), (308, 468), (32, 41, 58), -1)
        cv2.rectangle(canvas, (36, 290), (308, 468), (64, 79, 106), 1)
        cv2.putText(canvas, "Callouts", (52, 318), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (255, 209, 102), 1)
        y = 344
        for item in list(spec["callouts"])[:3]:
            y = self._draw_wrapped(canvas, f"- {item}", 52, y, 26, (233, 238, 248), line_height=20) + 8

        cv2.putText(canvas, "Concept preview pinned to the board", (610, 510), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (174, 185, 205), 1)
        return canvas

    def _build_summary(self, spec: Dict[str, object]) -> str:
        lines = [
            f"# {spec['title']}",
            "",
            spec["summary"],
            "",
            "## Modules",
        ]
        lines.extend(f"- {module}" for module in spec["modules"])
        lines.extend(["", "## Callouts"])
        lines.extend(f"- {item}" for item in spec["callouts"])
        return "\n".join(lines)

    @staticmethod
    def _draw_wrapped(image: np.ndarray, text: str, x: int, y: int, width: int, color, line_height: int = 18) -> int:
        import textwrap

        for line in textwrap.wrap(text, width=max(12, width)):
            cv2.putText(image, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.46, color, 1)
            y += line_height
        return y

    @staticmethod
    def _join_bits(parts: List[str]) -> str:
        if len(parts) == 1:
            return parts[0]
        if len(parts) == 2:
            return f"{parts[0]} and {parts[1]}"
        return ", ".join(parts[:-1]) + f", and {parts[-1]}"

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.agents.memory_agent import MemoryAgent
from app.utils.config import MEMORY_EXPORT_DIR


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "project"


class BOMComposer:
    def __init__(self, memory_agent: MemoryAgent, export_dir: str = MEMORY_EXPORT_DIR):
        self.memory_agent = memory_agent
        self.export_dir = Path(export_dir) / "boms"
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def compose(self, request_text: str, project_name: Optional[str] = None) -> Dict[str, object]:
        target_project = (
            project_name
            or self.memory_agent.infer_project_name(request_text)
            or self.memory_agent.latest_project_name()
            or "design concept"
        )
        project_state = self.memory_agent.load_project_state(target_project) or {"project": target_project}
        payload = self._build_bom(target_project, project_state)
        markdown_path, json_path = self._write_files(target_project, payload)

        self.memory_agent.store.save_memory_event(
            memory_type="bom_estimate",
            subject=target_project,
            content=payload["headline"],
            user_name=self.memory_agent.user_name,
            metadata={
                "markdown_path": str(markdown_path),
                "json_path": str(json_path),
                "total_estimate": payload["total_estimate"],
            },
            importance=0.78,
        )
        self.memory_agent.save_project_state(
            target_project,
            {
                "last_bom_path": str(markdown_path),
                "last_bom_total": payload["total_estimate"],
            },
        )

        payload["output_path"] = str(markdown_path)
        payload["json_path"] = str(json_path)
        return payload

    def _build_bom(self, project_name: str, project_state: Dict[str, object]) -> Dict[str, object]:
        preferred_parts = list(project_state.get("preferred_parts") or [])
        budget_limit = project_state.get("budget_limit")
        lower = f"{project_name.lower()} {' '.join(preferred_parts).lower()}"

        if any(token in lower for token in {"arm", "servo", "claw", "robot"}):
            items = [
                {"item": preferred_parts[0] if preferred_parts else "MG996R Servo", "quantity": 3, "unit_cost": 12, "notes": "Main actuation"},
                {"item": "Arduino Nano", "quantity": 1, "unit_cost": 18, "notes": "Controller"},
                {"item": "5V/6V Power Supply", "quantity": 1, "unit_cost": 16, "notes": "Servo power"},
                {"item": "Bearing + bracket set", "quantity": 1, "unit_cost": 20, "notes": "Mechanical joints"},
                {"item": "Fasteners and wiring kit", "quantity": 1, "unit_cost": 12, "notes": "Assembly"},
            ]
        elif any(token in lower for token in {"edge", "gpu", "compute", "node", "server", "ai-ran"}):
            items = [
                {"item": preferred_parts[0] if preferred_parts else "Jetson Or Mini PC", "quantity": 1, "unit_cost": 120, "notes": "Main compute"},
                {"item": "Ethernet Switch", "quantity": 1, "unit_cost": 25, "notes": "Networking"},
                {"item": "Cooling Fan Set", "quantity": 2, "unit_cost": 9, "notes": "Thermals"},
                {"item": "Power Distribution Module", "quantity": 1, "unit_cost": 18, "notes": "Power routing"},
                {"item": "Shell, trays, and hardware", "quantity": 1, "unit_cost": 35, "notes": "Structure"},
            ]
        else:
            items = [
                {"item": preferred_parts[0] if preferred_parts else "Primary controller", "quantity": 1, "unit_cost": 25, "notes": "Core logic"},
                {"item": "Prototype frame materials", "quantity": 1, "unit_cost": 30, "notes": "Physical structure"},
                {"item": "Power module", "quantity": 1, "unit_cost": 15, "notes": "Power delivery"},
                {"item": "Wiring and connectors", "quantity": 1, "unit_cost": 12, "notes": "Integration"},
                {"item": "Fasteners and mounting hardware", "quantity": 1, "unit_cost": 10, "notes": "Assembly"},
            ]

        total = 0
        for item in items:
            subtotal = item["quantity"] * item["unit_cost"]
            item["subtotal"] = subtotal
            total += subtotal

        budget_status = "within target"
        if budget_limit is not None and total > budget_limit:
            budget_status = "over target"

        return {
            "project_name": project_name,
            "headline": f"{project_name.title()} preliminary BOM",
            "items": items,
            "total_estimate": total,
            "budget_limit": budget_limit,
            "budget_status": budget_status,
        }

    def _write_files(self, project_name: str, payload: Dict[str, object]) -> tuple[Path, Path]:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stem = f"{_slugify(project_name)}-{timestamp}"
        markdown_path = self.export_dir / f"{stem}.md"
        json_path = self.export_dir / f"{stem}.json"

        lines: List[str] = [
            f"# {payload['headline']}",
            "",
            f"Estimated total: ${payload['total_estimate']}",
        ]
        if payload["budget_limit"] is not None:
            lines.append(f"Budget target: ${payload['budget_limit']} ({payload['budget_status']})")
        lines.extend(["", "## Items"])
        for item in payload["items"]:
            lines.append(
                f"- {item['item']} x{item['quantity']} | ${item['unit_cost']} each | ${item['subtotal']} | {item['notes']}"
            )
        markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return markdown_path, json_path

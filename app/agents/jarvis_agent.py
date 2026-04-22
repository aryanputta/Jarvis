from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.memory_agent import MemoryAgent
from app.workflows.bom_generator import BOMComposer
from app.workflows.build_plan import BuildPlanComposer
from app.workflows.demo_script import DemoScriptComposer
from app.workflows.design_critic import DesignCritic
from app.workflows.email_composer import EmailComposer
from app.workflows.project_pitch import ProjectPitchComposer
from app.workflows.session_loader import SessionLoader


@dataclass
class AgentActionResult:
    message: str
    project_name: Optional[str] = None
    artifact_paths: List[str] = field(default_factory=list)
    facts: Dict[str, Any] = field(default_factory=dict)
    context: Optional[Dict[str, Any]] = None


class JarvisAgent:
    def __init__(
        self,
        memory_agent: MemoryAgent,
        email_composer: Optional[EmailComposer] = None,
        pitch_composer: Optional[ProjectPitchComposer] = None,
        build_plan_composer: Optional[BuildPlanComposer] = None,
        bom_composer: Optional[BOMComposer] = None,
        design_critic: Optional[DesignCritic] = None,
        demo_script_composer: Optional[DemoScriptComposer] = None,
    ):
        self.memory_agent = memory_agent
        self.email_composer = email_composer or EmailComposer(memory_agent)
        self.pitch_composer = pitch_composer or ProjectPitchComposer(memory_agent)
        self.build_plan_composer = build_plan_composer or BuildPlanComposer(memory_agent)
        self.bom_composer = bom_composer or BOMComposer(memory_agent)
        self.design_critic = design_critic or DesignCritic(memory_agent)
        self.demo_script_composer = demo_script_composer or DemoScriptComposer(memory_agent)
        self.session_loader = SessionLoader(memory_agent)

    def handle_task_command(
        self,
        command: str,
        request_text: str,
        active_project: Optional[str] = None,
    ) -> Optional[AgentActionResult]:
        if command == "WRITE_EMAIL":
            draft = self.email_composer.compose(request_text=request_text, project_name=active_project)
            delivery_phrase = "sent a demo email" if draft["delivery_state"] == "sent_demo" else "drafted an email"
            return AgentActionResult(
                message=(
                    f"I {delivery_phrase} to {', '.join(draft['recipients'])} with the latest design attached. "
                    f"Saved {Path(str(draft['eml_path'])).name} in the outbox."
                ),
                project_name=str(draft["project_name"]),
                artifact_paths=[
                    str(draft["eml_path"]),
                    *([str(draft["json_path"])] if draft.get("json_path") else []),
                ],
                facts={
                    "email_recipients": ", ".join(draft["recipients"]),
                    "email_delivery_state": draft["delivery_state"],
                    "email_attachment": Path(draft["attachments"][0]).name if draft["attachments"] else "",
                },
            )

        if command == "PITCH_PROJECT":
            pitch = self.pitch_composer.compose(request_text=request_text, project_name=active_project)
            return AgentActionResult(
                message=(
                    f"I wrote a pitch for {pitch['project_name']}. Present it as problem, design, build plan, and next steps."
                ),
                project_name=str(pitch["project_name"]),
                artifact_paths=[str(pitch["output_path"])],
                facts={"pitch_headline": pitch["headline"]},
            )

        if command == "BUILD_PLAN":
            plan = self.build_plan_composer.compose(request_text=request_text, project_name=active_project)
            return AgentActionResult(
                message=(
                    f"I built a plan for {plan['project_name']} with {len(plan['phases'])} phases and clear next steps."
                ),
                project_name=str(plan["project_name"]),
                artifact_paths=[str(plan["output_path"])],
                facts={"plan_headline": plan["headline"], "next_step": plan["next_steps"][0]},
            )

        if command == "GENERATE_BOM":
            bom = self.bom_composer.compose(request_text=request_text, project_name=active_project)
            return AgentActionResult(
                message=(
                    f"I generated a preliminary BOM for {bom['project_name']} at about ${bom['total_estimate']}."
                ),
                project_name=str(bom["project_name"]),
                artifact_paths=[str(bom["output_path"]), str(bom["json_path"])],
                facts={"bom_total": bom["total_estimate"], "bom_status": bom["budget_status"]},
            )

        if command == "CRITIQUE_DESIGN":
            review = self.design_critic.compose(request_text=request_text, project_name=active_project)
            return AgentActionResult(
                message=(
                    f"I reviewed {review['project_name']} and pulled out the biggest strengths, risks, and improvements."
                ),
                project_name=str(review["project_name"]),
                artifact_paths=[str(review["output_path"])],
                facts={"review_headline": review["headline"], "top_risk": review["risks"][0]},
            )

        if command == "DEMO_SCRIPT":
            script = self.demo_script_composer.compose(request_text=request_text, project_name=active_project)
            return AgentActionResult(
                message=(
                    f"I wrote a demo talk track for {script['project_name']} so you can explain the board, memory, and agent actions clearly."
                ),
                project_name=str(script["project_name"]),
                artifact_paths=[str(script["output_path"])],
                facts={"demo_script_headline": script["headline"]},
            )

        return None

    def handle_conversation(
        self,
        text: str,
        active_project: Optional[str] = None,
    ) -> AgentActionResult:
        context = self.session_loader.load(text, project_name=active_project)
        project_name = context["project_name"] or active_project
        normalized = text.lower().strip()

        if any(token in normalized for token in {"what can you do", "capabilities", "how can you help"}):
            capabilities = self.capabilities_for_project(project_name)
            message = "I can " + ", ".join(capabilities[:-1]) + f", and {capabilities[-1]}."
        else:
            message = self.memory_agent.generate_response(
                text,
                project_name=project_name,
                context=context,
            )
            if project_name and any(token in normalized for token in {"project", "design", "build", "next"}):
                message += " I can also build the plan, BOM, critique, pitch, demo script, or email for this project."

        return AgentActionResult(
            message=message,
            project_name=project_name,
            context=context,
        )

    def capabilities_for_project(self, project_name: Optional[str] = None) -> List[str]:
        subject = project_name or "your current project"
        return [
            f"remember the important context for {subject}",
            "draft and demo-send project emails",
            "write project pitches",
            "build a step-by-step project plan",
            "estimate a BOM and cost",
            "critique the design",
            "write your demo script",
        ]

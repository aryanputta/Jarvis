import json
import mimetypes
import re
import shutil
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, List, Optional

from app.agents.llm_client import JarvisLLMClient
from app.agents.memory_agent import MemoryAgent
from app.utils.config import EMAIL_OUTBOX_DIR, EMAIL_SENT_DIR


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "project"


class EmailComposer:
    def __init__(
        self,
        memory_agent: MemoryAgent,
        llm_client: Optional[JarvisLLMClient] = None,
        outbox_dir: str = EMAIL_OUTBOX_DIR,
        sent_dir: str = EMAIL_SENT_DIR,
    ):
        self.memory_agent = memory_agent
        self.llm_client = llm_client or JarvisLLMClient()
        self.outbox_dir = Path(outbox_dir)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        self.sent_dir = Path(sent_dir)
        self.sent_dir.mkdir(parents=True, exist_ok=True)

    def compose(self, request_text: str, project_name: Optional[str] = None) -> Dict[str, object]:
        target_project = (
            project_name
            or self.memory_agent.infer_project_name(request_text)
            or self.memory_agent.latest_project_name()
            or "design concept"
        )
        project_state = self.memory_agent.load_project_state(target_project) or {"project": target_project}
        recipients = self._extract_recipients(request_text)
        attachment = self._latest_attachment(target_project)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        send_requested = self._send_requested(request_text)
        style = self._detect_style(request_text, recipients)
        llm_draft = self._draft_with_llm(
            request_text=request_text,
            project_name=target_project,
            project_state=project_state,
            recipients=recipients,
            attachment=attachment,
            style=style,
        )
        subject = llm_draft["subject"] if llm_draft else self._build_subject(request_text, target_project)
        body = (
            llm_draft["body"]
            if llm_draft
            else self._build_body(request_text, target_project, project_state, attachment, recipients, style)
        )
        outbox_base = self.outbox_dir / f"{_slugify(target_project)}-{timestamp}"

        eml_path = outbox_base.with_suffix(".eml")
        json_path = outbox_base.with_suffix(".json")

        email_message = EmailMessage()
        email_message["Subject"] = subject
        email_message["To"] = ", ".join(recipients)
        email_message["From"] = self.memory_agent.user_name
        email_message.set_content(body)

        attachments = []
        if attachment:
            attachment_path = Path(attachment["image_path"])
            if attachment_path.exists():
                mime_type, _ = mimetypes.guess_type(str(attachment_path))
                if mime_type:
                    maintype, subtype = mime_type.split("/", 1)
                else:
                    maintype, subtype = "application", "octet-stream"
                email_message.add_attachment(
                    attachment_path.read_bytes(),
                    maintype=maintype,
                    subtype=subtype,
                    filename=attachment_path.name,
                )
                attachments.append(str(attachment_path))

        eml_path.write_bytes(email_message.as_bytes())
        payload = {
            "project_name": target_project,
            "recipients": recipients,
            "subject": subject,
            "body": body,
            "style": style,
            "attachments": attachments,
            "request_text": request_text,
            "delivery_state": "draft_ready",
            "created_at": timestamp,
            "eml_path": str(eml_path),
        }
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if send_requested:
            payload["delivery_state"] = "sent_demo"
            json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            sent_eml_path, sent_json_path = self._archive_demo_send(eml_path, json_path)
            payload["sent_eml_path"] = str(sent_eml_path)
            payload["sent_json_path"] = str(sent_json_path)
            json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            sent_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        self.memory_agent.store.save_memory_event(
            memory_type="email_draft",
            subject=target_project,
            content=subject,
            user_name=self.memory_agent.user_name,
            metadata={
                "recipients": recipients,
                "attachments": attachments,
                "eml_path": str(eml_path),
                "json_path": str(json_path),
                "delivery_state": payload["delivery_state"],
            },
            importance=0.72,
        )
        self.memory_agent.save_project_state(
            target_project,
            {
                "last_email_subject": subject,
                "last_email_draft_path": str(eml_path),
            },
        )

        payload["json_path"] = str(json_path)
        return payload

    def _archive_demo_send(self, eml_path: Path, json_path: Path) -> tuple[Path, Path]:
        sent_eml_path = self.sent_dir / eml_path.name
        sent_json_path = self.sent_dir / json_path.name
        shutil.copyfile(eml_path, sent_eml_path)
        if json_path.exists():
            shutil.copyfile(json_path, sent_json_path)
        return sent_eml_path, sent_json_path

    def _extract_recipients(self, request_text: str) -> List[str]:
        lowered = request_text.lower()
        recipients: List[str] = []
        match = re.search(r"\bto\s+(.+?)(?:\s+(?:about|saying|say|that)\b|[.?!]|$)", lowered)
        if match:
            raw_segment = match.group(1)
            raw_segment = raw_segment.replace("my friend", "")
            raw_segment = raw_segment.replace("and me", f"and {self.memory_agent.user_name}")
            for part in re.split(r",| and ", raw_segment):
                cleaned = part.strip(" .,!?")
                if not cleaned:
                    continue
                if cleaned in {"me", "myself"}:
                    recipients.append(self.memory_agent.user_name)
                else:
                    recipients.append(cleaned.title())

        if not recipients:
            recipients.append(self.memory_agent.user_name)

        normalized: List[str] = []
        for recipient in recipients:
            if recipient not in normalized:
                normalized.append(recipient)
        return normalized

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

    def _build_subject(self, request_text: str, project_name: str) -> str:
        lowered = request_text.lower()
        if "summer" in lowered:
            return f"Want to build {project_name.title()} over the summer?"
        if "cad" in lowered:
            return f"Latest CAD concept for {project_name.title()}"
        return f"Design update for {project_name.title()}"

    def _build_body(
        self,
        request_text: str,
        project_name: str,
        project_state: Dict[str, object],
        attachment: Optional[Dict[str, object]],
        recipients: List[str],
        style: str,
    ) -> str:
        greeting = f"Hi {self._join_names(recipients)},"
        lines = [greeting, ""]
        project_title = project_name.title()
        lowered = request_text.lower()
        mention_cad = "cad" in lowered
        last_version = project_state.get("last_version")
        preferred_design = project_state.get("preferred_design")
        budget_limit = project_state.get("budget_limit")
        open_tasks = project_state.get("open_tasks") or []
        lead = self._lead_sentence(project_title, mention_cad, style)
        lines.append(lead)

        context_bits = []
        if last_version:
            context_bits.append(f"the latest version is based on {last_version}")
        if preferred_design:
            context_bits.append(f"I'm leaning toward a {preferred_design} layout")
        if budget_limit is not None:
            context_bits.append(f"I'm trying to keep the build around ${budget_limit}")
        if context_bits:
            lines.append(self._join_bits(context_bits).capitalize() + ".")

        if attachment:
            attachment_name = Path(str(attachment["image_path"])).name
            lines.append(f"I attached the latest design snapshot so you can see where it stands right now ({attachment_name}).")

        if "summer" in lowered:
            lines.append("I think this would be a really solid project to build over the summer, and I want to keep pushing it toward a real working system.")
        else:
            lines.append("I want to keep iterating on it until it turns into something we can actually build.")

        if open_tasks:
            lines.append(f"My next steps are {', '.join(open_tasks[:3])}, but I'd love your take before I lock anything in.")
        else:
            lines.append("I'd love your take on the design direction before I go much further with it.")

        lines.extend(["", self._closing(style), "", self._signature(style)])
        return "\n".join(lines)

    def _detect_style(self, request_text: str, recipients: List[str]) -> str:
        lowered = request_text.lower()
        saved_style = self.memory_agent.load_preferences().get("default_email_style")
        if "professional" in lowered:
            return "professional"
        if any(token in lowered for token in {"friend", "summer", "build this with me", "what do you think"}):
            return "collaborative"
        if len(recipients) > 1 and self.memory_agent.user_name in recipients:
            return "collaborative"
        if saved_style:
            return str(saved_style)
        return "friendly"

    @staticmethod
    def _lead_sentence(project_title: str, mention_cad: bool, style: str) -> str:
        if style == "professional":
            if mention_cad:
                return f"I wanted to share the latest CAD design for {project_title} and get your feedback."
            return f"I wanted to share the latest design update for {project_title} and get your feedback."
        if mention_cad:
            return f"I wanted to send over the latest CAD design for {project_title} because I think it's starting to come together."
        return f"I wanted to send over the latest design update for {project_title} because it's starting to take shape."

    @staticmethod
    def _closing(style: str) -> str:
        if style == "professional":
            return "I'd appreciate any feedback you have, especially on the design direction and what I should tighten up next."
        if style == "collaborative":
            return "Let me know what you think, and if you're down, I'd love to build on this together."
        return "Let me know what you think. I'm happy to keep iterating on it."

    def _signature(self, style: str) -> str:
        if style == "professional":
            return f"Best,\n{self.memory_agent.user_name}"
        return f"{self.memory_agent.user_name}"

    def _draft_with_llm(
        self,
        request_text: str,
        project_name: str,
        project_state: Dict[str, object],
        recipients: List[str],
        attachment: Optional[Dict[str, object]],
        style: str,
    ) -> Optional[Dict[str, str]]:
        if not self.llm_client.available():
            return None

        instructions = (
            "You are Jarvis drafting a natural, human-sounding email for a student builder. "
            "Sound warm, confident, and specific. Avoid robotic phrasing. "
            "Return only valid JSON with keys subject and body."
        )
        prompt = json.dumps(
            {
                "user_name": self.memory_agent.user_name,
                "request": request_text,
                "project_name": project_name,
                "project_state": project_state,
                "recipients": recipients,
                "attachment_name": Path(str(attachment["image_path"])).name if attachment else None,
                "style": style,
                "constraints": [
                    "Keep it concise and natural",
                    "Reference the project concretely",
                    "If the request mentions summer, mention wanting to build it over the summer",
                    "End like a real person, not a bot",
                ],
            },
            indent=2,
        )
        payload, _error = self.llm_client.generate_json(instructions, prompt, max_output_tokens=700)
        if not payload:
            return None

        subject = str(payload.get("subject") or "").strip()
        body = str(payload.get("body") or "").strip()
        if not subject or not body:
            return None
        return {"subject": subject, "body": body}

    @staticmethod
    def _send_requested(request_text: str) -> bool:
        lowered = request_text.lower()
        return "send" in lowered

    @staticmethod
    def _join_bits(parts: List[str]) -> str:
        if len(parts) == 1:
            return parts[0]
        if len(parts) == 2:
            return f"{parts[0]} and {parts[1]}"
        return ", ".join(parts[:-1]) + f", and {parts[-1]}"

    @staticmethod
    def _join_names(names: List[str]) -> str:
        if len(names) == 1:
            return names[0]
        if len(names) == 2:
            return f"{names[0]} and {names[1]}"
        return ", ".join(names[:-1]) + f", and {names[-1]}"

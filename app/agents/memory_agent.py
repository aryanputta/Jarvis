import re
from typing import Any, Dict, List, Optional

from app.db.retriever import MemoryRetriever
from app.db.store import MemoryStore
from app.utils.config import DEFAULT_USER_NAME


def _append_unique(values: List[str], item: str) -> List[str]:
    normalized = item.strip()
    if not normalized:
        return values
    if normalized not in values:
        values.append(normalized)
    return values


class MemoryAgent:
    def __init__(
        self,
        user_name: str = DEFAULT_USER_NAME,
        store: Optional[MemoryStore] = None,
        retriever: Optional[MemoryRetriever] = None,
    ):
        self.user_name = user_name
        self.store = store or MemoryStore(default_user=user_name)
        self.retriever = retriever or MemoryRetriever(self.store)

    def save_preference(self, key: str, value: Any) -> Dict[str, Any]:
        return self.store.save_preference(key=key, value=value, user_name=self.user_name)

    def load_preferences(self) -> Dict[str, Any]:
        return self.store.load_preferences(user_name=self.user_name)

    def save_project_state(self, project_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
        return self.store.save_project_state(project_name=project_name, state=state, user_name=self.user_name)

    def load_project_state(self, project_name: str) -> Optional[Dict[str, Any]]:
        return self.store.load_project_state(project_name=project_name, user_name=self.user_name)

    def save_session_summary(
        self,
        text: str,
        facts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        return self.store.save_session_summary(text=text, facts=facts, user_name=self.user_name)

    def retrieve_relevant_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        return self.retriever.retrieve(query=query, user_name=self.user_name, limit=limit)

    def save_sketch_snapshot(
        self,
        image: Any,
        label: str,
        detected_object: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.store.save_sketch_snapshot(
            image=image,
            label=label,
            detected_object=detected_object,
            metadata=metadata,
            user_name=self.user_name,
        )

    def clear_memory(self) -> bool:
        return self.store.clear_memory(user_name=self.user_name)

    def export_memory(self) -> Dict[str, Any]:
        output_path = self.store.build_export_path(self.user_name)
        return self.store.export_memory(user_name=self.user_name, output_path=output_path)

    def delete_project_memory(self, project_name: str) -> bool:
        return self.store.delete_project_memory(project_name=project_name, user_name=self.user_name)

    def set_learning_mode(self, enabled: bool) -> bool:
        return self.store.set_learning_mode(enabled=enabled, user_name=self.user_name)

    def learning_mode_enabled(self) -> bool:
        return self.store.get_learning_mode(user_name=self.user_name)

    def latest_project_name(self) -> Optional[str]:
        projects = self.store.list_recent_projects(user_name=self.user_name, limit=1)
        if not projects:
            return None
        return str(projects[0]["name"])

    def infer_project_name(self, text: str, active_project: Optional[str] = None) -> Optional[str]:
        lowered = text.lower().strip()
        known_projects = [project["name"] for project in self.store.list_recent_projects(self.user_name, limit=20)]
        for project_name in known_projects:
            if project_name.lower() in lowered:
                return project_name

        if active_project and any(token in lowered for token in {"continue", "resume", "this", "that"}):
            return active_project

        patterns = [
            r"(?:help me build|build|continue|resume|work on|start)\s+(?:my|a|an|the)?\s*([a-z0-9][a-z0-9 \-]{2,40})",
            r"(?:project|design)\s+(?:called|named)\s+([a-z0-9][a-z0-9 \-]{2,40})",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if not match:
                continue
            candidate = match.group(1).strip(" .,!?")
            candidate = re.sub(r"\b(now|again|please)\b", "", candidate).strip()
            candidate = re.sub(r"\b(over|during)\s+the\s+summer\b", "", candidate).strip()
            candidate = re.sub(r"\bthis\s+summer\b", "", candidate).strip()
            if candidate and candidate not in {"email", "board", "canvas"}:
                return candidate
        return active_project

    def observe_text(self, text: Optional[str], active_project: Optional[str] = None) -> Dict[str, Any]:
        if not text:
            return {"saved": False, "project_name": active_project, "facts": []}
        if not self.learning_mode_enabled():
            return {"saved": False, "project_name": active_project, "facts": []}

        normalized = text.strip()
        lowered = normalized.lower()
        project_name = self.infer_project_name(normalized, active_project=active_project)
        preferences: Dict[str, Any] = {}
        project_updates: Dict[str, Any] = {}
        facts: List[Dict[str, Any]] = []
        meaningful = False

        name_match = re.search(r"\bmy name is\s+([a-z][a-z\-]+)\b", lowered)
        if name_match:
            name = name_match.group(1).title()
            preferences["name"] = name
            facts.append({"label": "name", "value": name})
            meaningful = True

        budget_match = re.search(
            r"\b(?:under|below|within|budget(?: is)?|for)\s+\$?(\d{1,5})\b",
            lowered,
        )
        if budget_match:
            budget = int(budget_match.group(1))
            preferences["budget_limit"] = budget
            facts.append({"label": "budget_limit", "value": budget})
            meaningful = True
            if project_name:
                project_updates["budget_limit"] = budget

        if "professional" in lowered and "email" in lowered:
            preferences["default_email_style"] = "professional"
            facts.append({"label": "default_email_style", "value": "professional"})
            meaningful = True

        if "concise" in lowered:
            preferences["preferred_response_style"] = "concise"
            facts.append({"label": "preferred_response_style", "value": "concise"})
            meaningful = True

        design_preferences = {
            "compact": "compact",
            "small": "compact",
            "lightweight": "lightweight",
            "modular": "modular",
        }
        for token, label in design_preferences.items():
            if token in lowered and "design" in lowered:
                project_updates["preferred_design"] = label
                facts.append({"label": "preferred_design", "value": label})
                meaningful = True
                break

        part_match = re.search(
            r"\bprefer(?:red)?\s+([a-z0-9\- ]{2,40}?)(?:\s+(?:for|and|but)\b|[.,!?]|$)",
            normalized,
            re.IGNORECASE,
        )
        if part_match:
            preferred_part = part_match.group(1).strip(" .,!?")
            if preferred_part:
                existing_parts = []
                if project_name:
                    existing_state = self.load_project_state(project_name) or {}
                    existing_parts = list(existing_state.get("preferred_parts", []))
                project_updates["preferred_parts"] = _append_unique(existing_parts, preferred_part)
                facts.append({"label": "preferred_part", "value": preferred_part})
                meaningful = True

        if any(token in lowered for token in {"too expensive", "cheaper", "budget alternative", "lower cost"}):
            preferences["avoid_high_cost_parts"] = True
            facts.append({"label": "avoid_high_cost_parts", "value": True})
            self.store.save_memory_event(
                memory_type="rejected_suggestion",
                subject=project_name or "general",
                content=normalized,
                user_name=self.user_name,
                metadata={"reason": "cost"},
                importance=0.85,
            )
            meaningful = True

        if any(token in lowered for token in {"looks good", "sounds good", "accepted", "let's use"}):
            self.store.save_memory_event(
                memory_type="accepted_suggestion",
                subject=project_name or "general",
                content=normalized,
                user_name=self.user_name,
                metadata={"source": "conversation"},
                importance=0.75,
            )
            meaningful = True

        if project_name and any(token in lowered for token in {"build", "continue", "resume", "work on", "design"}):
            project_updates["project"] = project_name
            project_updates["last_request"] = normalized
            meaningful = True

        if not meaningful:
            return {"saved": False, "project_name": project_name, "facts": []}

        for key, value in preferences.items():
            self.save_preference(key, value)

        if project_name:
            self.save_project_state(project_name, project_updates)
            note = project_updates.get("last_request")
            if note:
                self.store.save_memory_event(
                    memory_type="project_history",
                    subject=project_name,
                    content=note,
                    user_name=self.user_name,
                    metadata={"project_state": project_updates},
                    importance=0.7,
                )

        return {
            "saved": True,
            "project_name": project_name,
            "preferences": preferences,
            "project_updates": project_updates,
            "facts": facts,
        }

    def generate_response(
        self,
        text: str,
        project_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        normalized = text.lower().strip()
        preferences = self.load_preferences()
        context = context or {}
        project_name = project_name or context.get("project_name") or self.infer_project_name(text)
        project_state = context.get("project_state") or (self.load_project_state(project_name) if project_name else None)
        relevant_memories = context.get("relevant_memories") or self.retrieve_relevant_memories(text, limit=3)

        if "email" in normalized:
            style_parts = []
            email_style = preferences.get("default_email_style")
            response_style = preferences.get("preferred_response_style")
            if email_style:
                style_parts.append(str(email_style))
            if response_style and response_style not in style_parts:
                style_parts.append(str(response_style))
            if style_parts:
                return f"I'll draft this in your usual {' '.join(style_parts)} style and keep it sounding natural."
            return "I'll draft a natural email about this and keep it sounding like you."

        if any(token in normalized for token in {"cad model", "3d model", "show the cad", "show me the cad"}):
            return "I'll generate a concept model and pin it to the board so you can react to it right away."

        if project_state and any(token in normalized for token in {"continue", "resume", "build", "work on"}):
            fragments = []
            last_version = project_state.get("last_version")
            if last_version:
                fragments.append(f"Loading your last {last_version} {project_name} design.")
            else:
                fragments.append(f"Continuing your {project_name} workspace.")

            detail_bits = []
            preferred_parts = project_state.get("preferred_parts", [])
            if preferred_parts:
                detail_bits.append(f"you preferred {preferred_parts[0]}")
            preferred_design = project_state.get("preferred_design")
            if preferred_design:
                detail_bits.append(f"a {preferred_design} layout")
            if detail_bits:
                fragments.append(f"Last time {self._join_bits(detail_bits)}.")

            budget = project_state.get("budget_limit") or preferences.get("budget_limit")
            if budget is not None:
                fragments.append(f"I'll keep suggestions under your ${budget} limit.")
            return " ".join(fragments)

        if preferences.get("budget_limit") is not None and any(
            token in normalized for token in {"parts", "part", "options", "build"}
        ):
            return f"I'll keep the options under your ${preferences['budget_limit']} limit."

        if relevant_memories:
            top_memory = relevant_memories[0]
            if top_memory["memory_type"] == "project":
                return f"I found your {top_memory['subject']} context and can continue from that version."
            if top_memory["memory_type"] == "preference":
                return f"I remember your {top_memory['subject']} preference and will use it here."

        return self.session_greeting()

    def session_greeting(self) -> str:
        dashboard = self.store.get_dashboard(user_name=self.user_name, limit=1)
        recent_projects = dashboard["recent_projects"]
        if recent_projects:
            project = recent_projects[0]
            project_state = project["state"]
            last_version = project_state.get("last_version")
            if last_version:
                return f"Last time you worked on {project['name']} with {last_version}. Continue from there?"
            return f"Last time you worked on {project['name']}. Continue that session?"
        return "Memory online. Start a project and I'll keep the useful parts."

    @staticmethod
    def _join_bits(parts: List[str]) -> str:
        if len(parts) == 1:
            return parts[0]
        return ", ".join(parts[:-1]) + f" and {parts[-1]}"

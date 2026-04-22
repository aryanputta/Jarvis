from typing import Any, Dict, List, Optional

from app.agents.memory_agent import MemoryAgent


class SessionLoader:
    def __init__(self, memory_agent: MemoryAgent):
        self.memory_agent = memory_agent

    def load(self, query: str = "", project_name: Optional[str] = None) -> Dict[str, Any]:
        inferred_project = project_name or self.memory_agent.infer_project_name(query)
        project_state = self.memory_agent.load_project_state(inferred_project) if inferred_project else None
        relevant_memories = self.memory_agent.retrieve_relevant_memories(query, limit=5) if query else []
        dashboard = self.memory_agent.store.get_dashboard(user_name=self.memory_agent.user_name)
        return {
            "project_name": inferred_project,
            "project_state": project_state,
            "preferences": self.memory_agent.load_preferences(),
            "relevant_memories": relevant_memories,
            "dashboard": dashboard,
            "continue_label": self._continue_label(inferred_project, project_state, dashboard),
            "greeting": self.memory_agent.session_greeting(),
        }

    def build_panel(
        self,
        latest_text: Optional[str] = None,
        latest_response: Optional[str] = None,
        project_name: Optional[str] = None,
        voice_status: Optional[str] = None,
        latest_heard: Optional[str] = None,
    ) -> Dict[str, Any]:
        context = self.load(query=latest_text or "", project_name=project_name)
        dashboard = context["dashboard"]
        return {
            "header": f"Jarvis Memory | {self.memory_agent.user_name}",
            "recent_projects": [project["name"] for project in dashboard["recent_projects"]],
            "preferences": self._format_preferences(dashboard["preferences"]),
            "continue": context["continue_label"],
            "recent_actions": dashboard.get("recent_actions", []),
            "saved_designs": [
                f"{sketch['label']} v{sketch['version']}"
                for sketch in dashboard["saved_designs"]
            ],
            "latest_text": latest_text,
            "latest_response": latest_response or context["greeting"],
            "learning_mode": dashboard["learning_mode"],
            "voice_status": voice_status or "voice ready",
            "latest_heard": latest_heard,
        }

    @staticmethod
    def _format_preferences(preferences: List[Dict[str, Any]]) -> List[str]:
        formatted = []
        for item in preferences:
            key = item["key"].replace("_", " ")
            value = item["value"]
            if isinstance(value, bool):
                value = "yes" if value else "no"
            formatted.append(f"{key}: {value}")
        return formatted

    @staticmethod
    def _continue_label(
        project_name: Optional[str],
        project_state: Optional[Dict[str, Any]],
        dashboard: Dict[str, Any],
    ) -> str:
        if project_name and project_state:
            version = project_state.get("last_version")
            if version:
                return f"{project_name} | {version}"
            summary = project_state.get("last_session_summary")
            if summary:
                return f"{project_name} | {summary}"
            return f"{project_name} | resume project"

        recent_projects = dashboard["recent_projects"]
        if recent_projects:
            project = recent_projects[0]
            version = project["state"].get("last_version")
            if version:
                return f"{project['name']} | {version}"
            return f"{project['name']} | recent project"
        return "No prior session loaded"

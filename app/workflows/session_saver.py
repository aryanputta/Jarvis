from typing import Any, Dict, List, Optional

from app.agents.memory_agent import MemoryAgent


class SessionSaver:
    def __init__(self, memory_agent: MemoryAgent):
        self.memory_agent = memory_agent
        self.turns: List[Dict[str, str]] = []
        self.tool_events: List[Dict[str, Any]] = []
        self.facts: List[Dict[str, Any]] = []

    def record_user_text(self, text: Optional[str]) -> None:
        if text:
            self.turns.append({"role": "user", "text": text.strip()})

    def record_assistant_response(self, text: Optional[str]) -> None:
        if text:
            self.turns.append({"role": "assistant", "text": text.strip()})

    def record_tool_usage(self, tool_name: str, context: Optional[Dict[str, Any]] = None) -> None:
        event = {"tool_name": tool_name, "context": context or {}}
        self.tool_events.append(event)
        self.memory_agent.store.record_tool_usage(
            tool_name=tool_name,
            user_name=self.memory_agent.user_name,
            context=context,
        )

    def record_fact(self, label: str, value: Any) -> None:
        fact = {"label": label, "value": value}
        if fact not in self.facts:
            self.facts.append(fact)

    def finalize(self, project_name: Optional[str] = None) -> Optional[str]:
        summary = self._build_summary(project_name)
        if not summary:
            return None

        self.memory_agent.save_session_summary(summary, facts=self.facts)

        if project_name:
            state_update: Dict[str, Any] = {"last_session_summary": summary}
            if self.tool_events:
                state_update["recent_tools"] = [
                    event["tool_name"] for event in self.tool_events[-3:]
                ]
            self.memory_agent.save_project_state(project_name, state_update)

        return summary

    def _build_summary(self, project_name: Optional[str]) -> Optional[str]:
        user_turns = [turn["text"] for turn in self.turns if turn["role"] == "user"]
        if not user_turns and not self.facts and not self.tool_events:
            return None

        parts: List[str] = []
        if project_name:
            parts.append(f"Worked on {project_name}.")
        if user_turns:
            parts.append(f"Last request: {user_turns[-1]}.")
        if self.facts:
            fact_text = ", ".join(
                f"{fact['label']}={fact['value']}"
                for fact in self.facts[:4]
            )
            parts.append(f"Key facts: {fact_text}.")
        if self.tool_events:
            tools = ", ".join(event["tool_name"] for event in self.tool_events[-4:])
            parts.append(f"Tools used: {tools}.")
        return " ".join(parts)

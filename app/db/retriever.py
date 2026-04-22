import re
from typing import Any, Dict, Iterable, List, Optional

from app.db.store import MemoryStore


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    return str(value)


class MemoryRetriever:
    def __init__(self, store: MemoryStore):
        self.store = store

    def _candidates(self, user_name: Optional[str] = None) -> Iterable[Dict[str, Any]]:
        for preference in self.store.list_preferences(user_name=user_name, limit=50):
            yield {
                "memory_type": "preference",
                "subject": preference["key"],
                "content": f"{preference['key']} {_flatten(preference['value'])}",
                "importance": 0.7,
                "updated_at": preference["updated_at"],
                "metadata": {"source": preference["source"]},
            }

        for project in self.store.list_recent_projects(user_name=user_name, limit=50):
            state_text = _flatten(project["state"])
            yield {
                "memory_type": "project",
                "subject": project["name"],
                "content": f"{project['name']} {state_text} {project['summary']}",
                "importance": 0.9,
                "updated_at": project["updated_at"],
                "metadata": project["state"],
            }

        for task in self.store.list_tasks(user_name=user_name):
            yield {
                "memory_type": "task",
                "subject": task["project_name"],
                "content": f"{task['project_name']} {task['description']} {task['status']}",
                "importance": 0.6,
                "updated_at": task["updated_at"],
                "metadata": {"status": task["status"], "recurrence": task["recurrence"]},
            }

        for session in self.store.list_recent_sessions(user_name=user_name, limit=50):
            yield {
                "memory_type": "session",
                "subject": "session_summary",
                "content": session["summary"],
                "importance": 0.8,
                "updated_at": session["updated_at"],
                "metadata": {"facts": session["facts"]},
            }

        for sketch in self.store.list_sketch_versions(user_name=user_name, limit=50):
            yield {
                "memory_type": "sketch",
                "subject": sketch["label"],
                "content": f"{sketch['label']} {sketch['detected_object'] or ''} version {sketch['version']}",
                "importance": 0.7,
                "updated_at": sketch["created_at"],
                "metadata": sketch["metadata"],
            }

        for event in self.store.list_memory_events(user_name=user_name, limit=100):
            yield {
                "memory_type": event["memory_type"],
                "subject": event["subject"],
                "content": event["content"],
                "importance": event["importance"],
                "updated_at": event["created_at"],
                "metadata": event["metadata"],
            }

        for tool in self.store.load_tool_usage_patterns(user_name=user_name, limit=50):
            yield {
                "memory_type": "tool_usage",
                "subject": tool["tool_name"],
                "content": f"{tool['tool_name']} usage count {tool['usage_count']}",
                "importance": min(1.0, 0.4 + (tool["usage_count"] * 0.05)),
                "updated_at": tool["updated_at"],
                "metadata": tool["context"],
            }

    def _score(self, query_tokens: List[str], candidate: Dict[str, Any]) -> float:
        content = f"{candidate['subject']} {candidate['content']}".lower()
        content_tokens = set(_tokenize(content))
        query_set = set(query_tokens)
        overlap = len(query_set & content_tokens)
        if overlap == 0:
            return 0.0
        exact_phrase_bonus = 0.35 if " ".join(query_tokens) in content else 0.0
        density = overlap / max(1, len(query_set))
        importance = float(candidate.get("importance", 0.5)) * 0.25
        return density + exact_phrase_bonus + importance

    def retrieve(
        self,
        query: str,
        user_name: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scored: List[Dict[str, Any]] = []
        seen = set()
        for candidate in self._candidates(user_name=user_name):
            key = (candidate["memory_type"], candidate["subject"], candidate["content"])
            if key in seen:
                continue
            seen.add(key)

            score = self._score(query_tokens, candidate)
            if score <= 0:
                continue

            item = dict(candidate)
            item["score"] = round(score, 4)
            scored.append(item)

        scored.sort(key=lambda item: (item["score"], item["updated_at"]), reverse=True)
        return scored[:limit]

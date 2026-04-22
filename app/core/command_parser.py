class CommandParser:
    def parse(self, text):
        if text is None:
            return None

        text = text.lower().strip()
        if not text:
            return None

        if "email" in text and any(word in text for word in {"write", "draft", "send", "share"}):
            return "WRITE_EMAIL"
        elif any(word in text for word in {"bom", "bill of materials", "parts list", "cost estimate", "budget estimate"}):
            return "GENERATE_BOM"
        elif any(word in text for word in {"critique", "review", "improve"}) and any(
            word in text for word in {"cad", "model", "design", "project"}
        ):
            return "CRITIQUE_DESIGN"
        elif any(word in text for word in {"demo", "present", "say"}) and any(
            word in text for word in {"script", "talk", "presentation", "show"}
        ):
            return "DEMO_SCRIPT"
        elif any(word in text for word in {"plan", "roadmap", "next steps"}) and any(
            word in text for word in {"build", "project", "design", "cad"}
        ):
            return "BUILD_PLAN"
        elif any(word in text for word in {"pitch", "present", "presentation"}) and any(
            word in text for word in {"cad", "model", "design", "project"}
        ):
            return "PITCH_PROJECT"
        elif "clear memory" in text or "forget everything" in text:
            return "CLEAR_MEMORY"
        elif "export memory" in text or "backup memory" in text:
            return "EXPORT_MEMORY"
        elif "disable learning" in text or "stop learning" in text:
            return "DISABLE_LEARNING"
        elif "enable learning" in text or "resume learning" in text:
            return "ENABLE_LEARNING"
        elif "delete project memory" in text:
            return "DELETE_PROJECT_MEMORY"
        elif ("close" in text or "hide" in text) and ("board" in text or "canvas" in text):
            return "CLOSE_BOARD"
        elif "open" in text and ("board" in text or "canvas" in text or "whiteboard" in text):
            return "OPEN_BOARD"
        elif "clear" in text or "erase" in text:
            return "CLEAR"
        elif "save" in text:
            return "SAVE"
        elif "switch" in text or "tool" in text:
            return "SWITCH_TOOL"
        elif "stop" in text:
            return "STOP"

        # add new commands in here — elif "word" in text: return "COMMAND"

        return None

class CommandParser:
    def parse(self, text):
        if text is None:
            return None

        text = text.lower().strip()

        if "open" in text and ("board" in text or "canvas" in text):
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

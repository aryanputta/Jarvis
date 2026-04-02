import pytest
from app.core.command_parser import CommandParser


@pytest.fixture
def parser():
    return CommandParser()


def test_none_input(parser):
    assert parser.parse(None) is None


def test_empty_string(parser):
    assert parser.parse("") is None


def test_open_board(parser):
    assert parser.parse("open board") == "OPEN_BOARD"


def test_open_canvas(parser):
    assert parser.parse("open canvas") == "OPEN_BOARD"


def test_open_board_case_insensitive(parser):
    assert parser.parse("Open Board") == "OPEN_BOARD"


def test_clear(parser):
    assert parser.parse("clear") == "CLEAR"


def test_erase(parser):
    assert parser.parse("erase") == "CLEAR"


def test_save(parser):
    assert parser.parse("save") == "SAVE"


def test_switch(parser):
    assert parser.parse("switch") == "SWITCH_TOOL"


def test_tool(parser):
    assert parser.parse("tool") == "SWITCH_TOOL"


def test_stop(parser):
    assert parser.parse("stop") == "STOP"


def test_unrecognized_returns_none(parser):
    assert parser.parse("hello world") is None


def test_whitespace_stripped(parser):
    assert parser.parse("  save  ") == "SAVE"

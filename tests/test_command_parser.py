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


def test_clear_memory(parser):
    assert parser.parse("clear memory") == "CLEAR_MEMORY"


def test_write_email(parser):
    assert parser.parse("write an email about this CAD design and send it to me and Shrihan") == "WRITE_EMAIL"


def test_pitch_project(parser):
    assert parser.parse("give me a pitch on this CAD model and how to present it") == "PITCH_PROJECT"


def test_build_plan(parser):
    assert parser.parse("make a build plan for this CAD project") == "BUILD_PLAN"


def test_generate_bom(parser):
    assert parser.parse("generate a BOM and cost estimate for this design") == "GENERATE_BOM"


def test_critique_design(parser):
    assert parser.parse("critique this CAD model and improve the design") == "CRITIQUE_DESIGN"


def test_demo_script(parser):
    assert parser.parse("what should i say in the demo presentation for this project") == "DEMO_SCRIPT"


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


def test_disable_learning(parser):
    assert parser.parse("disable learning") == "DISABLE_LEARNING"


def test_unrecognized_returns_none(parser):
    assert parser.parse("hello world") is None


def test_whitespace_stripped(parser):
    assert parser.parse("  save  ") == "SAVE"

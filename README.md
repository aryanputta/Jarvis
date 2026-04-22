# JarvisOS v3

We built JarvisOS v3 as a personal AI agent workspace.

The point is not to make another chatbot that forgets everything. The point is to give one user their own agent that can watch the workspace, help design ideas visually, remember useful context, and do follow-up tasks for them.

## What It Is

JarvisOS v3 combines:

- OpenCV for the live visual workspace
- a fingertip-driven drawing board for sketching ideas
- voice input for natural commands
- persistent SQLite memory so projects do not reset every session
- task-aware workflows for design follow-up, summaries, pitches, BOMs, critiques, demo scripts, and email drafting

The experience we are aiming for is:

- sketch an idea
- talk to Jarvis about it
- save versions
- come back later and continue from the right context
- ask Jarvis to do a task from that design context

## Why This Matters

A normal chatbot forgets everything the next time you open it.

JarvisOS keeps the useful parts:

- what project you were building
- what design direction you liked
- what constraints mattered
- what suggestions you rejected
- what board versions you saved
- what follow-up tasks Jarvis should help with

That makes it feel like your own agent instead of a blank slate every time.

## Core Product Direction

Jarvis should feel like the user’s own AI agent.

That means it should be able to:

- help design with the drawing board
- use OpenCV to stay aware of the live workspace
- remember project context over time
- draft artifacts from that context
- help with real tasks after the design work

One example is email follow-up from a design session.

If the user says:

`Jarvis write an email about this CAD design and send it to me and Shrihan. Mention that I want to build it over the summer.`

Jarvis can now:

- pull the active project context
- grab the latest saved design snapshot
- generate a share-ready email draft
- package the draft into the local outbox

The current implementation creates a ready-to-send draft package with the attachment included. The next layer would be wiring that outbox into Gmail, SMTP, or another provider.

The same agent layer can also:

- build a project plan from the current design state
- generate a preliminary BOM and cost estimate
- critique the design and suggest improvements
- write a pitch and a demo talk track for the project

## Current Features

### Persistent Memory

Jarvis stores meaningful context in SQLite:

- user preferences
- project state
- recurring tasks
- session summaries
- sketch versions
- accepted and rejected suggestions
- tool usage patterns

It does not try to save every sentence.

### Design Board

The design board is the visual thinking surface.

- `open board` opens the whiteboard
- fingertip tracking draws on the board
- `switch tool` toggles pen and eraser
- `clear` clears the board
- `save` versions the current design snapshot

The board keeps a pinned brief with the active project, constraints, tasks, and recent context from memory.

### Task Workflows

Jarvis is not just supposed to answer questions. It should do things for the user.

Right now the repo supports:

- continuing a saved project
- loading useful memory for that project
- saving board versions
- exporting memory
- drafting project emails with the latest design attached
- writing project pitches
- building project plans
- generating BOM and cost estimates
- reviewing the design
- writing a demo script

### Privacy Controls

We kept privacy controls explicit:

- `clear memory`
- `export memory`
- `delete project memory`
- `disable learning`
- `enable learning`

## Code Structure

```text
app/
  agents/
    jarvis_agent.py
    memory_agent.py
  core/
    command_parser.py
    design_board.py
    hand_detection.py
    video_pipeline.py
    voice_input.py
  db/
    retriever.py
    schema.sql
    store.py
  workflows/
    bom_generator.py
    build_plan.py
    demo_runner.py
    demo_script.py
    design_critic.py
    email_composer.py
    project_pitch.py
    session_loader.py
    session_saver.py
  utils/
    config.py
    helpers.py
```

## Running It

```bash
pip install -r requirements.txt
python3 -m app.core.video_pipeline
```

Press `ESC` to quit.

## Commands

Design commands:

- `open board`
- `clear`
- `save`
- `switch tool`

Agent and memory commands:

- `write an email about this CAD design and send it to me and Shrihan`
- `give me a pitch on this CAD model and how to present it`
- `make a build plan for this CAD project`
- `generate a BOM and cost estimate for this design`
- `critique this CAD model and improve the design`
- `what should I say in the demo presentation for this project`
- `clear memory`
- `export memory`
- `delete project memory`
- `disable learning`
- `enable learning`
- `stop`

## Tests

```bash
python3 -m pytest tests/ -v
```

The tests cover:

- preference save/load
- project retrieval
- session summaries
- duplicate memory handling
- memory ranking relevance
- email draft generation with attachments
- build plan, BOM, critique, and demo script generation
- parser coverage for memory and agent commands

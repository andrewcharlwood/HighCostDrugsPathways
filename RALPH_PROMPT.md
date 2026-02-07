# Ralph Wiggum Loop — Dash Application: Additional Analytics Charts

You are operating inside an automated loop adding analytics charts to an NHS patient pathway analysis tool built with Dash (Plotly) + Dash Mantine Components. Each iteration you receive fresh context — you have NO memory of previous iterations. Your only memory is the filesystem.

**Current Focus**: Phase 9 — Add 7 new analytics chart tabs alongside the existing icicle chart. Tab bar in chart_card.py, lazy rendering, shared query/figure functions in `src/`. See IMPLEMENTATION_PLAN.md Phase 9 for full task list.

## First Actions Every Iteration

Read these files in this order before doing anything else:

1. `progress.txt` — What previous iterations accomplished, what's blocked, and what to do next.
2. `IMPLEMENTATION_PLAN.md` — Task list with status markers, architecture overview, and completion criteria.
3. `guardrails.md` — Known failure patterns to avoid. You MUST read and follow these.
4. `CLAUDE.md` — Project architecture and backend code patterns.

Then run `git log --oneline -5` to see recent commits.

## Reading the Design Reference

**When building ANY UI component**, read `01_nhs_classic.html` first:
- It contains the exact CSS classes, HTML structure, and visual layout you must replicate
- CSS lives in the `<style>` block (lines 8-314) — this becomes `dash_app/assets/nhs.css`
- HTML structure (lines 316-480+) shows the component hierarchy and class usage
- Match the design as closely as possible — `className` in Dash = `class` in HTML

**When building data loading or chart callbacks**, reference the shared functions in `src/`:
- `src/data_processing/pathway_queries.py`: `load_initial_data()`, `load_pathway_nodes()`, and 7 new chart-specific query functions (Phase 9)
- `src/visualization/plotly_generator.py`: `create_icicle_from_nodes()` — icicle chart from list-of-dicts. Add new figure functions here for each chart type.
- `dash_app/data/queries.py`: Thin wrapper calling shared functions with correct DB path
- The original logic is archived in `archive/pathways_app/pathways_app.py` for reference.

**When building new analytics charts (Phase 9)**, also read:
- `AdditionalAnalytics.md` — Full specification for each chart: data source, visualization type, interaction, parsing requirements
- `src/data_processing/pathway_queries.py` — Existing query patterns to follow. All new queries go here.
- Key data columns: `level` (0=root, 1=trust, 2=directory, 3=drug, 4+=pathway), `ids` (hierarchy path), `cost_pp_pa`, `avg_days`, `average_spacing`, `average_administered`

## Narration

Narrate your work as you go. Your output is the only visibility the operator has into what's happening. For every significant action, explain what you're doing and why:

- **Reading files**: "Reading 01_nhs_classic.html to get CSS classes for the header component..."
- **Creating code**: "Creating dash_app/components/header.py with make_header() function..."
- **Debugging**: "Import error for dmc.Drawer — checking dash-mantine-components version..."
- **Testing**: "Running python run_dash.py to verify the app starts..."
- **Making decisions**: "The guardrails say to use className from nhs.css, not inline styles."
- **Committing**: "Committing header and sidebar components."

Do NOT just output a summary at the end. Narrate throughout.

## Task Selection

1. Read ALL tasks in IMPLEMENTATION_PLAN.md — understand the full picture
2. Skip any marked `[x]` (complete) or `[B]` (blocked)
3. Check progress.txt for guidance — the previous iteration may have recommendations
4. **Choose a task** based on:
   - Dependencies (scaffolding before components, components before callbacks)
   - Logical flow (Phase 0 → 1 → 2 → 3 → 4 → 5)
   - Previous iteration's recommendations
5. **Document your reasoning**: Before starting, explain WHY you chose this task
6. Mark your chosen task `[~]` (in progress) in IMPLEMENTATION_PLAN.md

If your chosen task is blocked:
- Mark it `[B]` with a reason
- Document the blocker in progress.txt
- Move to a different ready task

## Development

Work on ONE task per iteration. Build incrementally and verify as you go.

### Key Technologies

- **Dash 2.x**: `from dash import Dash, html, dcc, Input, Output, State, callback_context, ALL`
- **Dash Mantine Components 0.14.x**: `import dash_mantine_components as dmc` — needs `dmc.MantineProvider` wrapping the layout
- **Plotly**: `import plotly.graph_objects as go` — for the icicle chart
- **SQLite**: `import sqlite3` — read-only access to `data/pathways.db`
- **CSS**: All in `dash_app/assets/nhs.css` — auto-served by Dash

### Dash Component Patterns

```python
# HTML elements use dash.html
from dash import html
html.Div(className="top-header", children=[...])

# Mantine components for rich UI
import dash_mantine_components as dmc
dmc.Modal(id="drug-modal", opened=False, centered=True, size="lg", children=[...])
dmc.Accordion(children=[dmc.AccordionItem(...)])
dmc.ChipGroup(id="all-drugs-chips", multiple=True, children=[dmc.Chip(...)])

# State management
dcc.Store(id="app-state", storage_type="session", data={})

# Callbacks
@app.callback(
    Output("chart-data", "data"),
    Input("app-state", "data"),
)
def load_pathway_data(app_state):
    ...
```

### Important: Use frontend-developer agent for UX decisions
When building modals, filter bar layout, or other UX-sensitive components, spawn the `frontend-developer` agent to review data shapes and recommend optimal patterns. Data shapes: 42 drugs, 7 trusts, 19 directorates × 163 indications.

### Database Access Pattern

```python
from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "pathways.db"

def load_pathway_data(filter_id, chart_type, selected_drugs=None, selected_directorates=None):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # ... query with parameterized WHERE ...
    conn.close()
    return result_dict
```

### Verification Steps

After writing code, ALWAYS verify:

1. **Import check**: `python -c "from dash_app.app import app"` (or specific module)
2. **App starts**: `python run_dash.py` — must start without errors
3. **Visual check** (when building UI): describe what you expect to see at localhost:8050
4. **For callbacks**: verify the callback chain fires correctly (add temporary `print()` statements if needed)

If any step fails, fix the issue before proceeding.

## Validation Protocol

Every task MUST pass validation before being marked complete:

### Tier 1: Code Validation (MANDATORY)
- Code compiles without Python syntax errors
- Imports work without errors
- `python run_dash.py` starts without exceptions

### Tier 2: Layout Validation (for UI component tasks)
- Component renders in the browser
- CSS classes match 01_nhs_classic.html
- Layout structure matches the HTML concept

### Tier 3: Functional Validation (for callback tasks)
- Callbacks fire when inputs change
- Data flows correctly through dcc.Store chain
- Chart renders with real data from SQLite

### Validation Failure

If any tier fails:
- DO NOT mark the task complete
- Document the failure in progress.txt
- Fix the issue within this iteration if possible
- If you cannot fix it, mark the task `[B]` with details

## Quality Gates

Before marking ANY task `[x]`, ALL of these must be true:

1. Code is saved to the appropriate file(s)
2. Tier 1 validation passed (imports + app starts)
3. Tier 2/3 validation passed (as applicable)
4. All changes committed to git with a descriptive message

These are non-negotiable.

## Update Progress

After completing your work, append to progress.txt using this format:

```
## Iteration [N] — [YYYY-MM-DD]
### Task: [which task you worked on]
### Why this task:
- [Brief explanation of why you chose this task over others]
### Status: COMPLETE | BLOCKED | IN PROGRESS
### What was done:
- [Specific actions taken]
### Validation results:
- Tier 1 (Code): [import check, app starts]
- Tier 2 (Layout): [renders correctly, CSS matches]
- Tier 3 (Functional): [callbacks fire, data flows]
### Files changed:
- [list of files created/modified]
### Committed: [git hash] "[commit message]"
### Patterns discovered:
- [Any reusable learnings — Dash patterns, DMC quirks, CSS gotchas]
### Next iteration should:
- [Explicit guidance for what the next fresh instance should do first]
- [Note any context that would be lost without writing it here]
### Blocked items:
- [Any tasks that are blocked and why]
```

If you discover a failure pattern, add it to `guardrails.md`.

## Commit Changes

1. Stage changed files
2. Use a descriptive commit message referencing the task (e.g., "feat: create dash_app skeleton with nhs.css (Task 0.1 + 0.2)")
3. Commit after your task is validated and complete
4. If you updated progress.txt with a blocked status, commit that too

## Completion Check

If ALL tasks in IMPLEMENTATION_PLAN.md are marked `[x]`:

1. Run `python run_dash.py` to verify app starts cleanly
2. Verify all completion criteria at the bottom of IMPLEMENTATION_PLAN.md are satisfied
3. Only then output the completion signal on its own line:

```
<promise>COMPLETE</promise>
```

DO NOT output this string under any other circumstances.
DO NOT output it if any task is still `[ ]` or `[B]` or `[~]`.

## Rules

- Complete ONE task per iteration, then update progress and stop
- ALWAYS read progress.txt, guardrails.md before starting work
- **Read 01_nhs_classic.html** when building ANY visual component
- **Read src/data_processing/pathway_queries.py and src/visualization/plotly_generator.py** when building data logic or chart callbacks
- **DO NOT modify pipeline/analysis logic** in src/ (pathway_pipeline, transforms, diagnosis_lookup, pathway_analyzer, refresh_pathways)
- **DO add shared utilities** to src/ (visualization/plotly_generator.py, data_processing/database.py) rather than duplicating logic in dash_app/
- **Use className from nhs.css** — not inline styles
- **dcc.Store for state** — no server-side globals
- **Unidirectional callbacks** — app-state → chart-data → UI
- **Port icicle_figure exactly** — same customdata, colorscale, templates
- **Lazy tab rendering** — only compute the active tab's chart, not all 8
- **New figure functions** go in `src/visualization/`, not in `dash_app/callbacks/`
- **New query functions** go in `src/data_processing/pathway_queries.py` with thin wrappers in `dash_app/data/queries.py`
- Keep commits atomic and well-described
- If stuck for 2+ attempts, document in progress.txt and move on
- `python run_dash.py` must work after every task

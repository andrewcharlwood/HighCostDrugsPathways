# Ralph Wiggum Loop — Dashboard Visualization Improvements

You are operating inside an automated loop improving Plotly charts in an NHS patient pathway analysis Dash application. Each iteration you receive fresh context — you have NO memory of previous iterations. Your only memory is the filesystem.

**Current Focus**: Phase E — Redesign temporal trends as a standalone 3rd view with directorate overview + drug drill-down, fix chart height, rename cost labels. See IMPLEMENTATION_PLAN.md for the full task list organized into Phases A–E.

## First Actions Every Iteration

Read these files in this order before doing anything else:

1. `progress.txt` — What previous iterations accomplished, what's blocked, and what to do next.
2. `IMPLEMENTATION_PLAN.md` — Task list with status markers, architecture overview, and completion criteria.
3. `guardrails.md` — Known failure patterns to avoid. You MUST read and follow these.
4. `CLAUDE.md` — Project architecture and backend code patterns.

Then run `git log --oneline -5` to see recent commits.

## Key Files for This Phase

**When modifying chart functions**, always read first:
- `src/visualization/plotly_generator.py` — PRIMARY file. All chart generation functions live here (~1782 lines).
- `dash_app/callbacks/chart.py` — Patient Pathways tab dispatch and chart rendering helpers.
- `dash_app/callbacks/trust_comparison.py` — Trust Comparison 6-chart callbacks.

**When adding new analytics charts**, also read:
- `src/data_processing/pathway_queries.py` — All SQLite query functions. New queries go here.
- `dash_app/data/queries.py` — Thin wrappers. Add wrapper for each new query.
- `dash_app/components/chart_card.py` — TAB_DEFINITIONS for Patient Pathways tabs.

**When working on the Trends view** (Phase E), also read:
- `dash_app/components/trends.py` — Trends landing + detail components (create if doesn't exist)
- `dash_app/callbacks/trends.py` — Trends view callbacks (create if doesn't exist)
- `dash_app/components/sidebar.py` — Sidebar navigation (3 items: Patient Pathways, Trust Comparison, Trends)
- `dash_app/callbacks/navigation.py` — View switching (3-way)
- `dash_app/callbacks/filters.py` — `update_app_state()` handles nav clicks
- `dash_app/app.py` — Layout with 3 view containers + app-state initial data

**When modifying UI components**, read:
- `dash_app/components/trust_comparison.py` — TC landing + dashboard layout (reference for Trends landing/detail pattern).
- `dash_app/assets/nhs.css` — All CSS styles.

## Narration

Narrate your work as you go. Your output is the only visibility the operator has into what's happening. For every significant action, explain what you're doing and why:

- **Reading files**: "Reading plotly_generator.py to locate the heatmap colorscale..."
- **Creating code**: "Adding _base_layout() helper to DRY shared layout properties..."
- **Debugging**: "Chart title color is #003087 instead of CHART_TITLE_COLOR..."
- **Testing**: "Running python run_dash.py to verify the app starts..."
- **Committing**: "Committing heatmap fixes."

Do NOT just output a summary at the end. Narrate throughout.

## Task Selection

1. Read ALL tasks in IMPLEMENTATION_PLAN.md — understand the full picture
2. Skip any marked `[x]` (complete) or `[B]` (blocked)
3. Check progress.txt for guidance — the previous iteration may have recommendations
4. **Choose a task** based on:
   - Dependencies (A.1 shared constants before A.2-A.4 which use them)
   - Phase ordering (Phase A before B, B before C, C before D)
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

- **Dash 4.0.0**: `from dash import Dash, html, dcc, Input, Output, State, ctx, ALL`
- **Dash Mantine Components 2.5.1**: `import dash_mantine_components as dmc` — `MantineProvider` wraps layout
- **Plotly**: `import plotly.graph_objects as go` — all chart figures
- **SQLite**: `import sqlite3` — read-only access to `data/pathways.db`
- **CSS**: All in `dash_app/assets/nhs.css` — auto-served by Dash

### Plotly Skill

**IMPORTANT**: When creating or modifying chart functions in `plotly_generator.py`, invoke the `/plotly` skill first. This loads Plotly reference documentation (chart types, graph objects, layouts, interactivity) that helps produce better chart code. Use it before writing any Plotly figure code.

### plotly_generator.py Patterns

All chart functions follow the same pattern:
```python
def create_CHART_figure(data: list[dict], title: str = "", ...) -> go.Figure:
    """Create CHART from prepared data."""
    if not data:
        return go.Figure()

    # Build traces from data
    fig = go.Figure(data=traces)

    # Apply layout
    layout = _base_layout(display_title)
    layout.update({...chart-specific overrides...})
    fig.update_layout(**layout)

    return fig
```

### Adding a New Chart Tab

1. Add query function to `src/data_processing/pathway_queries.py` (accept `db_path` param)
2. Add thin wrapper to `dash_app/data/queries.py` (resolve DB_PATH and delegate)
3. Add figure function to `src/visualization/plotly_generator.py`
4. Add tab to `TAB_DEFINITIONS` in `dash_app/components/chart_card.py`
5. Add `_render_*()` helper in `dash_app/callbacks/chart.py`
6. Add elif case in `update_chart()` callback

### Database Access Pattern

```python
# In src/data_processing/pathway_queries.py
def get_something(db_path: Path, filter_id: str, chart_type: str, ...) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT ... WHERE date_filter_id = ? AND chart_type = ?", [filter_id, chart_type])
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

# In dash_app/data/queries.py (thin wrapper)
from data_processing.pathway_queries import get_something as _get_something
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "pathways.db"

def get_something(filter_id="all_6mo", chart_type="directory", ...):
    return _get_something(DB_PATH, filter_id, chart_type, ...)
```

### Verification Steps

After writing code, ALWAYS verify:

1. **Import check**: `python -c "from dash_app.app import app"` (or specific module)
2. **App starts**: `python run_dash.py` — must start without errors
3. **Visual check** (when modifying charts): describe what you expect to see at localhost:8050
4. **For callbacks**: verify the callback chain fires correctly

If any step fails, fix the issue before proceeding.

## Validation Protocol

Every task MUST pass validation before being marked complete:

### Tier 1: Code Validation (MANDATORY)
- Code compiles without Python syntax errors
- Imports work without errors
- `python run_dash.py` starts without exceptions

### Tier 2: Visual Validation (for chart modification tasks)
- Chart renders in the browser
- Colors, labels, legend layout match expectations
- No overflow or overlap issues

### Tier 3: Functional Validation (for callback/toggle tasks)
- Callbacks fire when inputs change
- Metric toggles switch correctly
- New tabs appear and render data

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
- Tier 2 (Visual): [chart renders, colors correct]
- Tier 3 (Functional): [callbacks fire, toggles work]
### Files changed:
- [list of files created/modified]
### Committed: [git hash] "[commit message]"
### Patterns discovered:
- [Any reusable learnings — Plotly quirks, layout gotchas, Dash patterns]
### Next iteration should:
- [Explicit guidance for what the next fresh instance should do first]
- [Note any context that would be lost without writing it here]
### Blocked items:
- [Any tasks that are blocked and why]
```

If you discover a failure pattern, add it to `guardrails.md`.

## Commit Changes

1. Stage changed files
2. Use a descriptive commit message referencing the task (e.g., "fix: heatmap colorscale + cell annotations (Task A.2)")
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
- **Read plotly_generator.py** when modifying ANY chart function (line numbers shift!)
- **DO NOT modify pipeline/analysis logic** in src/ (pathway_pipeline, transforms, diagnosis_lookup, pathway_analyzer, refresh_pathways)
- **DO add/modify** chart functions in `src/visualization/plotly_generator.py`
- **DO add** new query functions in `src/data_processing/pathway_queries.py`
- **New figure functions** go in `src/visualization/`, not in `dash_app/callbacks/`
- **New query functions** go in `src/data_processing/pathway_queries.py` with thin wrappers in `dash_app/data/queries.py`
- **dcc.Store for state** — no server-side globals
- **Lazy tab rendering** — only compute the active tab's chart
- **3-view architecture** — Patient Pathways, Trust Comparison, Trends (Phase E). View switching via `active_view` in app-state.
- Keep commits atomic and well-described
- If stuck for 2+ attempts, document in progress.txt and move on
- `python run_dash.py` must work after every task

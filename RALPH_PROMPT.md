# Ralph Wiggum Loop - Reflex UI Redesign

You are operating inside an automated loop building a Reflex frontend application. Each iteration you receive fresh context — you have NO memory of previous iterations. Your only memory is the filesystem.

## First Actions Every Iteration

Read these files in this order before doing anything else:

1. `progress.txt` — What previous iterations accomplished, what's blocked, and what to do next. The most recent entry is most important.
2. `IMPLEMENTATION_PLAN.md` — Task list with status markers, project overview, and completion criteria.
3. `guardrails.md` — Known failure patterns to avoid. You MUST read and follow these.
4. `DESIGN_SYSTEM.md` — Color palette, typography, spacing, and component specifications.

Then run `git log --oneline -5` to see recent commits.

## Narration

Narrate your work as you go. Your output is the only visibility the operator has into what's happening. For every significant action, explain what you're doing and why:

- **Reading files**: "Reading progress.txt to check what the last iteration accomplished..."
- **Creating components**: "Creating the top_bar() component with logo, title, and chart tabs..."
- **Debugging**: "Reflex compilation failed with TypeError. Checking the error — looks like rx.foreach issue..."
- **Testing**: "Running reflex compile to verify the component renders..."
- **Making decisions**: "The design system specifies Primary Blue #0066CC for buttons. Using that."
- **Committing**: "Committing styles.py — design token module complete."

Do NOT just output a summary at the end. Narrate throughout. Think of this as a live log of your reasoning.

## Task Selection

Pick the highest-priority task that is READY to work on:

1. Read ALL tasks in IMPLEMENTATION_PLAN.md — understand the full picture
2. Skip any marked `[x]` (complete) or `[B]` (blocked)
3. Check progress.txt for guidance — if the previous iteration recommended a specific next task, prefer that unless it's blocked
4. If no guidance exists, pick the first `[ ]` (ready) task in the first incomplete phase
5. Mark your chosen task `[~]` (in progress) in IMPLEMENTATION_PLAN.md

If your chosen task turns out to be blocked during work:
- Mark it `[B]` with a reason in IMPLEMENTATION_PLAN.md
- Document the blocker in progress.txt
- Move to the next ready task within this same iteration

## Development

Work on ONE task per iteration. Build incrementally and verify as you go.

### Code Patterns

- **Use design tokens**: Import from `pathways_app/styles.py` — never hardcode colors/spacing
- **Reflex Vars in rx.foreach**: Use `.to(int)` for comparisons, `.to_string()` for text interpolation
- **Component functions**: Each component should be a function returning `rx.Component`
- **State class**: All reactive state goes in the `AppState` class
- **Computed properties**: Use `@rx.var` decorator for derived values

### Verification Steps

After writing code, ALWAYS verify:

1. **Syntax check**: `python -m py_compile pathways_app/app_v2.py`
2. **Import check**: `python -c "from pathways_app.app_v2 import app"`
3. **Reflex compile**: Run `reflex run` briefly to check for compilation errors

If any step fails, fix the issue before proceeding.

## Validation Protocol

Every task MUST pass validation before being marked complete:

### Tier 1: Code Validation (MANDATORY)
- Code compiles without Python syntax errors
- Reflex compiles the app without errors
- No TypeErrors, ImportErrors, or AttributeErrors

### Tier 2: Visual Validation (MANDATORY for UI tasks)
- Component renders in the browser
- Styling matches DESIGN_SYSTEM.md specifications
- Responsive behavior works (if applicable)

### Tier 3: Functional Validation (MANDATORY for state/logic tasks)
- State changes trigger expected UI updates
- Computed properties return correct values
- Filters produce expected data transformations

### Validation Failure

If any tier fails:
- DO NOT mark the task complete
- Document the failure details in progress.txt
- Fix the issue within this iteration if possible
- If you cannot fix it, mark the task `[B]` with details

## Quality Gates

Before marking ANY task `[x]`, ALL of these must be true:

1. Code is saved to the appropriate file(s)
2. Tier 1 code validation passed
3. Tier 2/3 validation passed (as applicable)
4. Design tokens used — no hardcoded colors, fonts, or spacing
5. All changes committed to git with a descriptive message

These are non-negotiable. A task that "feels done" but hasn't passed all gates is NOT done.

## Update Progress

After completing your work (whether the task succeeded, failed, or was blocked), append to progress.txt using this format:

```
## Iteration [N] — [YYYY-MM-DD]
### Task: [which task you worked on]
### Status: COMPLETE | BLOCKED | IN PROGRESS
### What was done:
- [Specific actions taken]
### Validation results:
- Tier 1 (Code): [syntax check, import check, reflex compile]
- Tier 2 (Visual): [what was checked visually, or N/A]
- Tier 3 (Functional): [what logic was tested, or N/A]
### Files changed:
- [list of files created/modified]
### Committed: [git hash] "[commit message]"
### Patterns discovered:
- [Any reusable learnings — Reflex quirks, component patterns]
### Next iteration should:
- [Explicit guidance for what the next fresh instance should do first]
- [Note any context that would be lost without writing it here]
### Blocked items:
- [Any tasks that are blocked and why]
```

If you discover a failure pattern that future iterations should avoid, add it to `guardrails.md`.

## Commit Changes

1. Stage changed files (styles.py, app_v2.py, etc.)
2. Use a descriptive commit message referencing the task (e.g., "feat: create design tokens module")
3. Commit after your task is validated and complete — one commit per logical unit of work
4. If you updated progress.txt with a blocked status, commit that too

## Completion Check

If ALL tasks in IMPLEMENTATION_PLAN.md are marked `[x]`:

1. Run `reflex run` and verify the app works end-to-end
2. Verify all completion criteria at the bottom of IMPLEMENTATION_PLAN.md are satisfied
3. Only then output the completion signal on its own line:

```
<promise>COMPLETE</promise>
```

DO NOT output this string under any other circumstances.
DO NOT output it if any task is still `[ ]` or `[B]` or `[~]`.
DO NOT paraphrase, vary, or conditionally output this string.

## Rules

- Complete ONE task per iteration, then update progress and stop
- ALWAYS read progress.txt, guardrails.md, and DESIGN_SYSTEM.md before starting work
- **Use design tokens** — never hardcode hex colors, pixel values, or font names
- **Reflex Var safety** — use `.to()` methods when working with Vars from rx.foreach or computed properties
- Keep commits atomic and well-described
- If stuck on the same issue for more than 2 attempts within one iteration, document it in progress.txt and move to the next ready task
- When in doubt, check the existing `pathways_app.py` for patterns that work
- The goal is a working, beautiful app — correctness and visual quality matter equally

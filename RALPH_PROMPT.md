# Ralph Wiggum Loop - Drug-Aware Indication Matching

You are operating inside an automated loop extending a pathway analysis application with drug-aware indication matching. Each iteration you receive fresh context — you have NO memory of previous iterations. Your only memory is the filesystem.

**Current Focus**: Update indication charts so that patient indications are matched **per drug**, not just per patient. Each drug must be validated against the patient's GP diagnoses AND the drug-to-indication mapping from DimSearchTerm.csv.

## First Actions Every Iteration

Read these files in this order before doing anything else:

1. `progress.txt` — What previous iterations accomplished, what's blocked, and what to do next. The most recent entry is most important.
2. `IMPLEMENTATION_PLAN.md` — Task list with status markers, project overview, and completion criteria.
3. `guardrails.md` — Known failure patterns to avoid. You MUST read and follow these.
4. `CLAUDE.md` — Project architecture and code patterns.

Then run `git log --oneline -5` to see recent commits.

## Narration

Narrate your work as you go. Your output is the only visibility the operator has into what's happening. For every significant action, explain what you're doing and why:

- **Reading files**: "Reading progress.txt to check what the last iteration accomplished..."
- **Creating code**: "Adding assign_drug_indications() function to diagnosis_lookup.py..."
- **Debugging**: "Drug matching returned 0 results for ADALIMUMAB. Checking DimSearchTerm lookup..."
- **Testing**: "Running import check to verify the new function is accessible..."
- **Making decisions**: "The guardrails say to use substring matching for drug fragments."
- **Committing**: "Committing drug-indication matching logic."

Do NOT just output a summary at the end. Narrate throughout. Think of this as a live log of your reasoning.

## Task Selection

You have flexibility to choose which task to work on. Use your judgement, but document your reasoning.

1. Read ALL tasks in IMPLEMENTATION_PLAN.md — understand the full picture
2. Skip any marked `[x]` (complete) or `[B]` (blocked)
3. Check progress.txt for guidance — the previous iteration may have recommendations
4. **Choose a task** based on:
   - Dependencies (some tasks require others to be done first)
   - Logical flow (query changes before matching logic, matching before pipeline integration)
   - Your assessment of what would be most valuable to tackle next
   - Previous iteration's recommendations (consider but don't blindly follow)
5. **Document your reasoning**: Before starting work, briefly explain WHY you chose this task over others
6. Mark your chosen task `[~]` (in progress) in IMPLEMENTATION_PLAN.md

If your chosen task turns out to be blocked during work:
- Mark it `[B]` with a reason in IMPLEMENTATION_PLAN.md
- Document the blocker in progress.txt
- Move to a different ready task within this same iteration

## Development

Work on ONE task per iteration. Build incrementally and verify as you go.

### Key Concepts

**Drug-Indication Matching Flow:**
1. Get patient's GP-matched Search_Terms from Snowflake (ALL matches, not just most recent, with code_frequency)
   - Only count GP codes from MIN(Intervention Date) onwards (the HCD data window)
2. Load DimSearchTerm.csv to get which drugs belong to which Search_Terms
3. For each patient-drug pair: intersection of (Search_Terms listing this drug) AND (patient's GP matches)
   - If multiple matches: pick highest code_frequency (most GP coding = most likely indication)
4. Modify UPID to include matched indication: `{UPID}|{search_term}`
5. Drugs sharing the same indication for the same patient → same modified UPID → same pathway
6. Drugs under different indications → different modified UPIDs → separate pathways

**DimSearchTerm.csv:**
- `Search_Term`: Clinical condition (e.g., "rheumatoid arthritis")
- `CleanedDrugName`: Pipe-separated drug fragments (e.g., "ADALIMUMAB|GOLIMUMAB|...")
- `PrimaryDirectorate`: The directorate for this condition
- Drug matching: check if any fragment is a substring of the HCD drug name (case-insensitive)

**Modified UPID Format:**
- Original: `RMV12345` (Provider Code[:3] + PersonKey)
- Modified: `RMV12345|rheumatoid arthritis`
- Fallback: `RMV12345|RHEUMATOLOGY (no GP dx)`
- The existing pathway analyzer treats UPID as an opaque identifier — this works transparently

### Code Patterns

- **Snowflake queries**: Use parameterized queries, embed the cluster CTE from CLUSTER_MAPPING_SQL
- **GP record matching**: Return ALL matches per patient (not just most recent)
- **Drug mapping**: Load from `data/DimSearchTerm.csv`, match drug name fragments
- **Pathway pipeline**: Use existing functions — modified UPIDs flow through naturally
- **Reflex state**: No changes expected — indication charts already work, just with better matching

### Key Data Structures

**GP Matches (from Snowflake) — updated to return ALL matches with frequency:**
```python
# Multiple rows per patient (one per matched Search_Term)
# code_frequency = COUNT of matching SNOMED codes (used as tiebreaker)
# Only counts codes from MIN(Intervention Date) onwards
DataFrame with: PatientPseudonym, Search_Term, code_frequency
```

**Drug-to-Indication Mapping (from DimSearchTerm.csv):**
```python
# search_term → list of drug fragments
{"rheumatoid arthritis": ["ABATACEPT", "ADALIMUMAB", "ANAKINRA", ...]}
```

**Modified HCD Data:**
```python
# Original UPID replaced with indication-aware UPID
df["UPID"] = "RMV12345|rheumatoid arthritis"  # for matched drugs
df["UPID"] = "RMV12345|RHEUMATOLOGY (no GP dx)"  # for unmatched drugs
```

**Indication DataFrame:**
```python
# Maps modified UPID → Search_Term (for pathway hierarchy level 2)
indication_df = pd.DataFrame({
    'Directory': ['rheumatoid arthritis', 'asthma', 'CARDIOLOGY (no GP dx)']
}, index=['RMV12345|rheumatoid arthritis', 'RMV12345|asthma', 'RMV67890|CARDIOLOGY (no GP dx)'])
```

### Verification Steps

After writing code, ALWAYS verify:

1. **Syntax check**: `python -m py_compile <file.py>`
2. **Import check**: `python -c "from module import function"`
3. **For database changes**: Test with query against pathways.db
4. **For Reflex changes**: `python -m reflex compile`

If any step fails, fix the issue before proceeding.

## Validation Protocol

Every task MUST pass validation before being marked complete:

### Tier 1: Code Validation (MANDATORY)
- Code compiles without Python syntax errors
- Imports work without errors
- No TypeErrors, ImportErrors, or AttributeErrors

### Tier 2: Data Validation (for data/pipeline tasks)
- Queries return expected row counts
- Data structures have correct columns/types
- Drug-indication matching produces valid results
- Modified UPIDs have correct format

### Tier 3: Functional Validation (for UI/integration tasks)
- Reflex compiles the app without errors
- State changes trigger expected behavior
- Both chart types render correctly

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
4. All changes committed to git with a descriptive message

These are non-negotiable. A task that "feels done" but hasn't passed all gates is NOT done.

## Update Progress

After completing your work (whether the task succeeded, failed, or was blocked), append to progress.txt using this format:

```
## Iteration [N] — [YYYY-MM-DD]
### Task: [which task you worked on]
### Why this task:
- [Brief explanation of why you chose this task over others]
- [What dependencies or logical flow led to this choice]
### Status: COMPLETE | BLOCKED | IN PROGRESS
### What was done:
- [Specific actions taken]
### Validation results:
- Tier 1 (Code): [syntax check, import check]
- Tier 2 (Data): [query results, row counts]
- Tier 3 (Functional): [reflex compile, UI check]
### Files changed:
- [list of files created/modified]
### Committed: [git hash] "[commit message]"
### Patterns discovered:
- [Any reusable learnings — query patterns, matching logic quirks]
### Next iteration should:
- [Explicit guidance for what the next fresh instance should do first]
- [Note any context that would be lost without writing it here]
### Blocked items:
- [Any tasks that are blocked and why]
```

If you discover a failure pattern that future iterations should avoid, add it to `guardrails.md`.

## Commit Changes

1. Stage changed files
2. Use a descriptive commit message referencing the task (e.g., "feat: add drug-indication matching function (Task 2.1)")
3. Commit after your task is validated and complete — one commit per logical unit of work
4. If you updated progress.txt with a blocked status, commit that too

## Completion Check

If ALL tasks in IMPLEMENTATION_PLAN.md are marked `[x]`:

1. Run `reflex compile` to verify app compiles
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
- ALWAYS read progress.txt, guardrails.md before starting work
- **Match drugs to indications** — not just patients to indications
- **Use DimSearchTerm.csv** for drug-to-Search_Term mapping
- **Return ALL GP matches** — not just most recent (remove QUALIFY ROW_NUMBER = 1)
- **Modified UPID format**: `{UPID}|{search_term}` — pipe delimiter is safe
- **Use PseudoNHSNoLinked** — NOT PersonKey for GP record matching
- **Substring matching** for drug fragments from DimSearchTerm.csv
- Keep commits atomic and well-described
- If stuck on the same issue for more than 2 attempts within one iteration, document it in progress.txt and move to the next ready task
- When in doubt, check existing code for patterns that work
- **Pipeline before UI** — processing logic before Reflex changes
- **Don't change directory charts** — only indication chart matching changes

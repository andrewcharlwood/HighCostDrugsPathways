# Guardrails

Known failure patterns. Read EVERY iteration. Follow ALL of these rules.
If you discover a new failure pattern during your work, add it to this file.

---

## Reflex Guardrails

### Use .to() methods for Var operations in rx.foreach
- **When**: Working with items inside `rx.foreach` render functions
- **Rule**: Use `item.to(int)` for numeric comparisons, `item.to_string()` for text operations
- **Why**: Items from rx.foreach are `ObjectItemOperation` Vars, not plain Python values. Using `>=` or f-strings directly causes TypeError.

**Bad:**
```python
def render_row(item):
    color = rx.cond(item["value"] >= 50, "green", "red")  # TypeError!
    return rx.text(f"{item['name']}: {item['value']}")    # Won't interpolate!
```

**Good:**
```python
def render_row(item):
    color = rx.cond(item["value"].to(int) >= 50, "green", "red")
    return rx.text(item["name"].to_string() + ": " + item["value"].to_string())
```

### Use rx.cond for conditional rendering, not Python if
- **When**: Conditionally showing/hiding components or changing styles based on state
- **Rule**: Use `rx.cond(condition, true_component, false_component)` — not Python `if`
- **Why**: Python `if` evaluates at definition time; `rx.cond` evaluates reactively at render time

### State variables must have default values
- **When**: Defining state variables in the State class
- **Rule**: Always provide a default: `my_var: str = ""` not just `my_var: str`
- **Why**: Reflex requires defaults for state initialization

### Computed vars use @rx.var decorator
- **When**: Creating derived/computed values from state
- **Rule**: Use `@rx.var` decorator, return a value, and include return type annotation
- **Why**: Without the decorator, the method won't be reactive

```python
@rx.var
def filtered_count(self) -> int:
    return len(self.filtered_data)
```

### Event handlers don't return values to components
- **When**: Creating methods that handle user interactions
- **Rule**: Event handlers modify state; they don't return values directly to UI
- **Why**: Use state variables and computed vars to communicate between handlers and UI

---

## Design System Guardrails

### Never hardcode colors
- **When**: Any styling that involves color
- **Rule**: Import from `pathways_app.styles` and use `Colors.PRIMARY`, `Colors.SLATE_700`, etc.
- **Why**: Hardcoded colors break consistency and make theming impossible

### Never hardcode spacing
- **When**: Any padding, margin, gap values
- **Rule**: Use `Spacing.SM`, `Spacing.LG`, etc. from the styles module
- **Why**: Consistent spacing is fundamental to visual cohesion

### Use design system typography
- **When**: Any text styling
- **Rule**: Use the typography classes/helpers from styles.py
- **Why**: Typography hierarchy creates visual structure

---

## Code Quality Guardrails

### Verify compilation before committing
- **When**: After ANY code changes
- **Rule**: Run `python -m py_compile <file>` AND `reflex run` (briefly) to check
- **Why**: Committing broken code wastes the next iteration fixing preventable errors

### One component per function
- **When**: Creating UI components
- **Rule**: Each logical component should be its own function returning `rx.Component`
- **Why**: Smaller functions are easier to debug and reuse

### Keep state minimal
- **When**: Designing state structure
- **Rule**: Only store what's necessary; derive everything else with computed vars
- **Why**: Duplicate state leads to sync bugs

---

## Process Guardrails

### One task per iteration
- **When**: Temptation to do additional tasks after completing the current one
- **Rule**: Complete ONE task, validate it, commit it, update progress, then stop
- **Why**: Multiple tasks increase error risk and make failures harder to diagnose

### Never mark complete without validation
- **When**: Task feels "done" but hasn't been tested
- **Rule**: All validation tiers must pass before marking `[x]`
- **Why**: "Feels done" is not "is done"

### Write explicit handoff notes
- **When**: Every iteration, before stopping
- **Rule**: The "Next iteration should" section must contain specific, actionable guidance
- **Why**: The next iteration has zero memory. If you don't write it down, it's lost.

### Check existing code for patterns
- **When**: Unsure how to implement something in Reflex
- **Rule**: Look at `pathways_app.py` for working examples before inventing new patterns
- **Why**: The existing codebase has solved many Reflex quirks already

---

<!--
ADD NEW GUARDRAILS BELOW as failures are observed during the loop.

Format:
### [Short descriptive name]
- **When**: What situation triggers this guardrail?
- **Rule**: What must you do (or not do)?
- **Why**: What failure prompted adding this guardrail?
-->

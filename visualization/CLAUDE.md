# visualization/ - Plotly Chart Generation

## Module: plotly_generator.py

Generates interactive Plotly icicle charts for patient pathway hierarchies.

### Key Functions

**create_icicle_figure(ice_df, title)**
- Builds Plotly icicle figure from pre-processed DataFrame
- Uses 10-field customdata: value, costpp, cost_pp_pa, first/last seen (node + parent), average_spacing, avg_days
- Color gradient based on patient volume (darkblue=high, lightblue=low)
- Hover template shows full treatment pathway and statistics

**save_figure_html(figure, filepath)**
- Exports interactive HTML file with embedded Plotly.js

**open_figure_in_browser(filepath)**
- Opens HTML file in default browser

### Data Requirements

Input DataFrame must have columns: parents, ids, labels, value, colour, cost, costpp, cost_pp_pa, first_seen, last_seen, first_seen_parent, last_seen_parent, average_spacing, avg_days

### Output

Interactive icicle chart showing Trust → Directory/Indication → Drug → Pathway hierarchy with rich tooltips.

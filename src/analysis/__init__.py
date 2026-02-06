"""
Analysis package for patient pathway processing.

This package contains refactored functions from the original generate_graph() pipeline:
- pathway_analyzer: Main analysis pipeline with prepare_data, calculate_statistics, build_hierarchy
- statistics: Statistical calculation functions (costs, frequencies, durations)
"""

from analysis.pathway_analyzer import (
    prepare_data,
    calculate_statistics,
    build_hierarchy,
    prepare_chart_data,
    generate_icicle_chart,
)

from analysis.statistics import (
    count_consecutive_values,
    calculate_drug_costs,
    calculate_dosing_frequency,
    calculate_drug_frequency_row,
    calculate_cost_per_patient_per_annum,
    calculate_treatment_duration,
    calculate_pathway_proportion,
    aggregate_patient_costs,
    aggregate_drug_frequencies,
    format_treatment_statistics,
    remove_nan_values,
)

__all__ = [
    # Pathway analysis pipeline
    "prepare_data",
    "calculate_statistics",
    "build_hierarchy",
    "prepare_chart_data",
    "generate_icicle_chart",
    # Statistical calculations
    "count_consecutive_values",
    "calculate_drug_costs",
    "calculate_dosing_frequency",
    "calculate_drug_frequency_row",
    "calculate_cost_per_patient_per_annum",
    "calculate_treatment_duration",
    "calculate_pathway_proportion",
    "aggregate_patient_costs",
    "aggregate_drug_frequencies",
    "format_treatment_statistics",
    "remove_nan_values",
]

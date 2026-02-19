"""Presenter module — the presentation layer between execution and rendering.

Connects executor outputs (prose in phase_outputs) to consumer rendering
through three capabilities:

1. **View Refiner** (3A): Post-execution LLM call that inspects phase results
   and refines the planner's recommended_views with updated priorities.

2. **Presentation Bridge** (3B): Automated transformation pipeline that runs
   applicable transformation templates against stored prose outputs and
   populates the presentation_cache with structured data.

3. **Presentation API** (3C): Consumer-facing endpoints that assemble
   render-ready PagePresentation payloads combining view definitions,
   structured data, and raw prose.
"""

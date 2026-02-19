"""Context-driven orchestrator for intellectual genealogy analysis.

Given a thinker + corpus + research question, the orchestrator:
1. Assembles a capability catalog from all registries
2. Calls an LLM (Claude Opus) to generate a WorkflowExecutionPlan
3. The plan configures depth, focus dimensions, and model selection per phase
4. Plans are inspectable, editable, and refinable

The orchestrator does NOT execute analyses — it produces plans that
the execution layer (currently The Critic, moving to analyzer-v2) consumes.
"""

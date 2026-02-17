"""Operationalization layer — bridges stances (HOW) and engines (WHAT).

Each engine gets an operationalization file that specifies:
- How each analytical stance applies to that specific engine
- What depth sequences (pass orderings) are available

This decouples stance operationalizations from engine definitions,
enabling drag-and-drop stance composition without touching engine YAMLs.
"""

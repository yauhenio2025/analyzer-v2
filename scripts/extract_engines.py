#!/usr/bin/env python3
"""Extract engine definitions from current Analyzer to JSON files.

This script parses the Python engine classes in the current Analyzer
and extracts their definitions (prompts, schemas, metadata) to JSON files
that Analyzer v2 can load.

Usage:
    python scripts/extract_engines.py

This will:
1. Scan /home/evgeny/projects/analyzer/src/engines/*.py
2. Import each engine class
3. Extract: engine_key, engine_name, description, prompts, schema, etc.
4. Write to analyzer-v2/src/engines/definitions/{engine_key}.json
"""

import json
import sys
from pathlib import Path

# Add analyzer to path for imports
ANALYZER_PATH = Path("/home/evgeny/projects/analyzer")
sys.path.insert(0, str(ANALYZER_PATH))

OUTPUT_DIR = Path(__file__).parent.parent / "src" / "engines" / "definitions"


def extract_engine(engine_class) -> dict:
    """Extract definition from an engine class."""
    # Get prompts with no context (default prompts)
    try:
        extraction_prompt = engine_class.get_extraction_prompt(None)
    except Exception:
        extraction_prompt = ""

    try:
        curation_prompt = engine_class.get_curation_prompt(None)
    except Exception:
        curation_prompt = ""

    try:
        concretization_prompt = engine_class.get_concretization_prompt()
    except Exception:
        concretization_prompt = None

    try:
        canonical_schema = engine_class.get_canonical_schema()
    except Exception:
        canonical_schema = {}

    return {
        "engine_key": engine_class.engine_key,
        "engine_name": engine_class.engine_name,
        "description": engine_class.description,
        "version": getattr(engine_class, "version", 1),
        "category": engine_class.category.value if hasattr(engine_class.category, "value") else str(engine_class.category),
        "kind": engine_class.kind.value if hasattr(engine_class.kind, "value") else str(engine_class.kind),
        "reasoning_domain": getattr(engine_class, "reasoning_domain", ""),
        "researcher_question": getattr(engine_class, "researcher_question", ""),
        "extraction_prompt": extraction_prompt,
        "curation_prompt": curation_prompt,
        "concretization_prompt": concretization_prompt,
        "canonical_schema": canonical_schema,
        "extraction_focus": getattr(engine_class, "extraction_focus", []),
        "primary_output_modes": getattr(engine_class, "primary_output_modes", []),
        "paradigm_keys": getattr(engine_class, "paradigm_keys", []),
        "source_file": f"analyzer/src/engines/{engine_class.engine_key}.py",
    }


def main():
    """Extract all engines from current Analyzer."""
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Import the engine registry from current analyzer
    try:
        from src.engines import EngineRegistry
    except ImportError as e:
        print(f"Failed to import EngineRegistry: {e}")
        print("Make sure you're running from analyzer-v2 directory")
        print("and analyzer is at /home/evgeny/projects/analyzer")
        sys.exit(1)

    # Get all registered engines
    engines = EngineRegistry.list_engines()
    print(f"Found {len(engines)} registered engines")

    extracted = 0
    failed = 0
    errors = []

    for engine_class in engines:
        try:
            definition = extract_engine(engine_class)
            output_file = OUTPUT_DIR / f"{definition['engine_key']}.json"

            with open(output_file, "w") as f:
                json.dump(definition, f, indent=2)

            print(f"  Extracted: {definition['engine_key']}")
            extracted += 1

        except Exception as e:
            engine_key = getattr(engine_class, "engine_key", "unknown")
            errors.append(f"{engine_key}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Extraction complete!")
    print(f"  Extracted: {extracted}")
    print(f"  Failed: {failed}")
    print(f"  Output: {OUTPUT_DIR}")

    if errors:
        print(f"\nErrors:")
        for error in errors:
            print(f"  - {error}")


if __name__ == "__main__":
    main()

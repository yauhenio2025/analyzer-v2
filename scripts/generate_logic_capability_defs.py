#!/usr/bin/env python3
"""Generate capability definition YAML files for the 10 logic-function engines.

Uses Claude Opus API to generate rich CapabilityEngineDefinition content from
the existing JSON engine definitions. Each engine's JSON (with extraction steps,
thinker references, schemas) provides source material; Claude generates the
YAML-compatible structure (problematique, lineage, dimensions, capabilities,
composability, depth_levels).

Validates each generated definition with Pydantic CapabilityEngineDefinition
before saving. Skips engines that already have YAML files (idempotent).

Usage:
    cd /home/evgeny/projects/analyzer-v2
    python scripts/generate_logic_capability_defs.py
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path

import yaml
from anthropic import Anthropic

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.engines.schemas_v2 import CapabilityEngineDefinition

# ── Configuration ──

DEFINITIONS_DIR = PROJECT_ROOT / "src" / "engines" / "definitions"
CAPABILITY_DIR = PROJECT_ROOT / "src" / "engines" / "capability_definitions"
EXEMPLAR_PATH = CAPABILITY_DIR / "inferential_commitment_mapper.yaml"

MODEL = "claude-opus-4-5-20251101"
MAX_TOKENS = 16000

# The 10 logic-function engines to generate capability definitions for
LOGIC_ENGINES = [
    "argument_architecture",
    "dialectical_structure",
    "counterfactual_analyzer",
    "modal_reasoning_analyzer",
    "concept_centrality_mapper",
    "comparative_reasoning_analyzer",
    "specialized_reasoning_classifier",
    "structural_pattern_detector",
    "epistemological_method_detector",
    "theory_construction_analyzer",
]

# Valid analytical stances from src/operations/definitions/stances.yaml
VALID_STANCES = {
    "discovery", "inference", "confrontation", "architecture",
    "integration", "reflection", "dialectical",
}

# ── YAML helpers (preserve formatting) ──

def str_representer(dumper, data):
    """Use block scalar for multi-line strings."""
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_representer)


def save_engine_yaml(filepath: Path, data: dict):
    """Save YAML preserving readability."""
    with open(filepath, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, width=80,
                  allow_unicode=True, sort_keys=False)


def load_exemplar(max_chars: int = 4000) -> str:
    """Load the inferential_commitment_mapper YAML as an exemplar."""
    with open(EXEMPLAR_PATH) as f:
        content = f.read()
    # Take first N chars for prompt context (enough to show structure)
    if len(content) > max_chars:
        content = content[:max_chars] + "\n... [truncated for brevity]"
    return content


def load_engine_json(engine_key: str) -> dict:
    """Load engine's full JSON definition."""
    path = DEFINITIONS_DIR / f"{engine_key}.json"
    with open(path) as f:
        return json.load(f)


def build_engine_context(engine: dict) -> str:
    """Build a comprehensive context string from the engine's JSON definition."""
    parts = []

    parts.append(f"ENGINE KEY: {engine['engine_key']}")
    parts.append(f"ENGINE NAME: {engine['engine_name']}")
    parts.append(f"CATEGORY: {engine.get('category', 'unknown')}")
    parts.append(f"KIND: {engine.get('kind', 'unknown')}")
    parts.append(f"FUNCTION: {engine.get('function', 'logic')}")
    parts.append(f"APPS: {engine.get('apps', ['critic'])}")
    parts.append(f"DESCRIPTION: {engine.get('description', '')}")
    parts.append(f"RESEARCHER QUESTION: {engine.get('researcher_question', '')}")
    parts.append(f"REASONING DOMAIN: {engine.get('reasoning_domain', '')}")
    parts.append("")

    # Stage context with extraction steps (rich source material)
    stage = engine.get('stage_context', {})
    extraction = stage.get('extraction', {})
    if extraction:
        parts.append("EXTRACTION STEPS (what this engine does in detail):")
        for i, step in enumerate(extraction.get('extraction_steps', []), 1):
            parts.append(f"  {i}. {step}")
        if extraction.get('special_instructions'):
            parts.append(f"  SPECIAL: {extraction['special_instructions']}")
        parts.append("")

    # Curation info
    curation = stage.get('curation', {})
    if curation:
        parts.append("CURATION RULES:")
        for rule in curation.get('consolidation_rules', []):
            parts.append(f"  - {rule}")
        if curation.get('synthesis_outputs'):
            parts.append(f"  SYNTHESIS OUTPUTS: {curation['synthesis_outputs']}")
        parts.append("")

    # Framework references
    if stage.get('framework_key'):
        parts.append(f"FRAMEWORK: {stage['framework_key']}")
    if stage.get('additional_frameworks'):
        parts.append(f"ADDITIONAL FRAMEWORKS: {stage['additional_frameworks']}")
    parts.append("")

    # Canonical schema (shows what the engine produces)
    schema = engine.get('canonical_schema', {})
    if schema:
        parts.append("CANONICAL SCHEMA STRUCTURE (what the engine produces):")
        # Show top-level keys and their types
        schema_str = json.dumps(schema, indent=2)
        # Truncate if too long
        if len(schema_str) > 3000:
            schema_str = schema_str[:3000] + "\n... [truncated]"
        parts.append(schema_str)
        parts.append("")

    # Concretization examples
    concretization = stage.get('concretization', {})
    if concretization:
        examples = concretization.get('id_examples', [])
        if examples:
            parts.append("EXAMPLE OUTPUTS:")
            for ex in examples[:5]:
                parts.append(f"  - {ex.get('id', '?')}: {ex.get('description', '')}")
            parts.append("")

    return "\n".join(parts)


def generate_capability_definition(client: Anthropic, engine: dict, exemplar: str) -> dict:
    """Generate a full CapabilityEngineDefinition using Claude Opus."""

    context = build_engine_context(engine)
    engine_key = engine['engine_key']
    engine_name = engine['engine_name']
    category = engine.get('category', 'argument')
    kind = engine.get('kind', 'extraction')

    prompt = f"""You are generating a CAPABILITY DEFINITION for an intellectual analysis engine.
The capability definition describes WHAT the engine investigates (its problematique, intellectual
lineage, analytical dimensions, capabilities) rather than HOW it formats output.

Below is the FULL JSON context of the engine — its description, extraction steps, schema, and
examples. Your task: generate a complete capability definition in JSON format.

{context}

Below is a QUALITY EXEMPLAR — the inferential_commitment_mapper capability definition. Study its
structure, depth, and intellectual rigor. Your output should match this quality level:

```yaml
{exemplar}
```

Generate a COMPLETE capability definition for {engine_name} ({engine_key}) as a JSON object with
these exact fields:

1. **engine_key**: "{engine_key}"
2. **engine_name**: "{engine_name}"
3. **version**: 1
4. **category**: "{category}"
5. **kind**: "{kind}"
6. **function**: "logic"
7. **apps**: ["critic"]

8. **problematique** (string, 3-5 rich prose paragraphs):
   - Paragraph 1: What intellectual problem this engine addresses. Why does it matter?
   - Paragraph 2: What most readers/authors miss that this engine reveals.
   - Paragraph 3: The philosophical foundation — which thinkers and traditions ground this.
   - Paragraph 4: How this engine relates to others in the logic suite.
   - Paragraph 5 (optional): Why commitment to this mode of analysis matters for genuine understanding.
   Use \\n for paragraph breaks in the string.

9. **researcher_question** (string): The one-line question a researcher asks.

10. **intellectual_lineage** (object):
    - primary: {{name: "thinker_name", description: "2-4 sentences on their contribution"}}
    - secondary: [3-5 objects with name + description (2-3 sentences each)]
    - traditions: [4-6 objects with name + description (2-3 sentences each)]
    - key_concepts: [5-8 objects with name + definition (2-3 sentences each)]

11. **analytical_dimensions** (list of 4-6 objects):
    Each has: key (snake_case), description (2-3 sentences), probing_questions (4-5 items),
    depth_guidance: {{surface: "...", standard: "...", deep: "..."}}

12. **capabilities** (list of 4-6 objects):
    Each has:
    - key (snake_case), description (1 sentence)
    - extended_description (2-3 paragraphs, ~200 words — ground in intellectual tradition)
    - intellectual_grounding: {{thinker: "...", concept: "...", method: "1-2 sentences"}}
    - indicators (3-5 textual signals)
    - depth_scaling: {{surface: "...", standard: "...", deep: "..."}}
    - requires_dimensions: [] (dimension keys from THIS engine or others)
    - produces_dimensions: [] (dimension keys from THIS engine's analytical_dimensions)

13. **composability** (object):
    - shares_with: {{dimension_key: "description"}} — 3-5 items
    - consumes_from: {{dimension_key: "from engine_name — what it provides"}} — 2-4 items
    - synergy_engines: [3-5 engine keys from the logic suite or other engines]

14. **depth_levels** (list of 3 objects):
    - surface: 1 pass, key="surface"
    - standard: 2 passes, key="standard"
    - deep: 3-4 passes, key="deep"
    Each has: key, description, typical_passes, suitable_for, passes (list of pass objects)
    Each pass: pass_number, label, stance, focus_dimensions, focus_capabilities,
    consumes_from (list of pass numbers), description (2-5 sentences)

CRITICAL REQUIREMENTS:
- Valid stances ONLY: discovery, inference, confrontation, architecture, integration, reflection, dialectical
- focus_dimensions in passes MUST reference dimension keys from analytical_dimensions
- focus_capabilities in passes MUST reference capability keys from capabilities
- All key fields use snake_case
- Problematique should feel grounded in the SPECIFIC intellectual tradition, not generic
- Thinker descriptions should be historically accurate with dates where known
- The output must be intellectually rigorous — this is philosophy, not marketing copy
- Each engine should have synergy_engines that reference REAL engines from the logic suite:
  argument_architecture, dialectical_structure, counterfactual_analyzer, modal_reasoning_analyzer,
  concept_centrality_mapper, comparative_reasoning_analyzer, specialized_reasoning_classifier,
  structural_pattern_detector, epistemological_method_detector, theory_construction_analyzer,
  inferential_commitment_mapper, conceptual_framework_extraction, concept_semantic_constellation

Return ONLY valid JSON. No markdown wrapping, no explanatory text before or after the JSON.

JSON output:"""

    # Use streaming for long generation
    collected_text = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            collected_text.append(text)

    text = "".join(collected_text).strip()

    # Parse JSON — handle possible markdown wrapping
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    # Handle trailing ``` if present
    if text.endswith("```"):
        text = text[:-3].strip()

    return json.loads(text)


def validate_and_fix(data: dict) -> tuple[dict, list[str]]:
    """Validate the generated data and auto-fix known issues.

    Returns (fixed_data, warnings).
    """
    warnings = []

    # Extract dimension and capability keys for cross-referencing
    dim_keys = {d['key'] for d in data.get('analytical_dimensions', [])}
    cap_keys = {c['key'] for c in data.get('capabilities', [])}

    # Fix stances in depth_level passes
    for dl in data.get('depth_levels', []):
        for p in dl.get('passes', []):
            if p.get('stance') not in VALID_STANCES:
                old = p['stance']
                p['stance'] = 'discovery'
                warnings.append(f"  Fixed invalid stance '{old}' → 'discovery' in pass {p.get('pass_number')}")

            # Check focus_dimensions reference valid dimension keys
            for fd in p.get('focus_dimensions', []):
                if fd not in dim_keys:
                    warnings.append(f"  WARN: focus_dimension '{fd}' not in analytical_dimensions")

            # Check focus_capabilities reference valid capability keys
            for fc in p.get('focus_capabilities', []):
                if fc not in cap_keys:
                    warnings.append(f"  WARN: focus_capability '{fc}' not in capabilities")

    # Ensure produces_dimensions reference valid dimension keys
    for cap in data.get('capabilities', []):
        for pd in cap.get('produces_dimensions', []):
            if pd not in dim_keys:
                warnings.append(f"  WARN: capability '{cap['key']}' produces unknown dimension '{pd}'")

    # Ensure function is set
    if 'function' not in data:
        data['function'] = 'logic'

    # Ensure apps is set
    if 'apps' not in data:
        data['apps'] = ['critic']

    return data, warnings


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = Anthropic(api_key=api_key)

    # Load exemplar
    print("Loading exemplar (inferential_commitment_mapper.yaml)...", flush=True)
    exemplar = load_exemplar(max_chars=4000)
    print(f"  Exemplar loaded: {len(exemplar)} chars\n", flush=True)

    success_count = 0
    skip_count = 0
    error_count = 0

    for engine_key in LOGIC_ENGINES:
        yaml_path = CAPABILITY_DIR / f"{engine_key}.yaml"

        # Skip if already exists (idempotent)
        if yaml_path.exists():
            print(f"SKIP {engine_key}: YAML already exists at {yaml_path.name}", flush=True)
            skip_count += 1
            continue

        print(f"\n{'='*70}", flush=True)
        print(f"GENERATING: {engine_key}", flush=True)
        print(f"{'='*70}", flush=True)

        try:
            # Load source JSON
            engine_json = load_engine_json(engine_key)
            print(f"  Source JSON loaded: {engine_json['engine_name']}", flush=True)

            # Generate with Claude Opus
            print(f"  Calling {MODEL} (streaming)...", flush=True)
            start = time.time()
            data = generate_capability_definition(client, engine_json, exemplar)
            elapsed = time.time() - start
            print(f"  API call completed in {elapsed:.1f}s", flush=True)

            # Validate and fix
            data, warnings = validate_and_fix(data)
            for w in warnings:
                print(w, flush=True)

            # Pydantic validation
            print(f"  Validating with CapabilityEngineDefinition...", flush=True)
            validated = CapabilityEngineDefinition.model_validate(data)
            print(f"  ✓ Pydantic validation passed", flush=True)

            # Convert to dict for YAML serialization
            yaml_data = validated.model_dump(mode='python', exclude_none=True)

            # Convert enums to strings for YAML
            yaml_data['category'] = str(yaml_data['category'].value) if hasattr(yaml_data['category'], 'value') else str(yaml_data['category'])
            yaml_data['kind'] = str(yaml_data['kind'].value) if hasattr(yaml_data['kind'], 'value') else str(yaml_data['kind'])

            # Save YAML
            save_engine_yaml(yaml_path, yaml_data)
            print(f"  ✓ Saved to {yaml_path.name}", flush=True)

            # Summary
            dims = len(data.get('analytical_dimensions', []))
            caps = len(data.get('capabilities', []))
            depth = len(data.get('depth_levels', []))
            prob_len = len(data.get('problematique', ''))
            lineage = data.get('intellectual_lineage', {})
            primary = lineage.get('primary', {})
            primary_name = primary.get('name', primary) if isinstance(primary, dict) else primary
            synergies = data.get('composability', {}).get('synergy_engines', [])

            print(f"  Summary: {dims} dimensions, {caps} capabilities, {depth} depth levels", flush=True)
            print(f"  Problematique: {prob_len} chars, Primary thinker: {primary_name}", flush=True)
            print(f"  Synergy engines: {', '.join(synergies[:5])}", flush=True)

            success_count += 1

        except json.JSONDecodeError as exc:
            print(f"  ✗ JSON parse error: {exc}", flush=True)
            error_count += 1
            continue
        except Exception as exc:
            print(f"  ✗ Error: {exc}", flush=True)
            traceback.print_exc()
            error_count += 1
            continue

        # Rate limiting
        time.sleep(2)

    print(f"\n{'='*70}", flush=True)
    print(f"COMPLETE: {success_count} generated, {skip_count} skipped, {error_count} errors", flush=True)
    print(f"{'='*70}", flush=True)


if __name__ == "__main__":
    main()

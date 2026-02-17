#!/usr/bin/env python3
"""Enrich engine capabilities with extended descriptions, intellectual grounding,
indicators, and depth scaling.

Uses Claude API to generate philosophically grounded content for each capability,
drawing on the engine's full context (problematique, lineage, dimensions, etc.).

Writes enriched capabilities back into the YAML files incrementally.
"""

import os
import sys
import yaml
import json
import time
from pathlib import Path
from anthropic import Anthropic

# ── Configuration ──

DEFINITIONS_DIR = Path(__file__).parent.parent / "src" / "engines" / "capability_definitions"
MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 8000

# ── YAML helpers (preserve formatting) ──

def str_representer(dumper, data):
    """Use block scalar for multi-line strings."""
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_representer)


def load_engine_yaml(filepath: Path) -> dict:
    with open(filepath) as f:
        return yaml.safe_load(f)


def save_engine_yaml(filepath: Path, data: dict):
    """Save YAML preserving readability."""
    with open(filepath, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, width=80,
                  allow_unicode=True, sort_keys=False)


def build_engine_context(engine: dict) -> str:
    """Build a rich context string from the engine definition."""
    parts = []

    parts.append(f"ENGINE: {engine['engine_name']} ({engine['engine_key']})")
    parts.append(f"KIND: {engine.get('kind', 'unknown')}")
    parts.append("")

    # Problematique
    parts.append("PROBLEMATIQUE:")
    parts.append(engine.get('problematique', 'N/A'))
    parts.append("")

    # Researcher question
    if engine.get('researcher_question'):
        parts.append(f"RESEARCHER QUESTION: {engine['researcher_question']}")
        parts.append("")

    # Intellectual lineage
    lineage = engine.get('intellectual_lineage', {})
    parts.append(f"PRIMARY THINKER: {lineage.get('primary', 'N/A')}")
    if lineage.get('secondary'):
        parts.append(f"SECONDARY: {', '.join(lineage['secondary'])}")
    if lineage.get('traditions'):
        parts.append(f"TRADITIONS: {', '.join(lineage['traditions'])}")
    if lineage.get('key_concepts'):
        parts.append(f"KEY CONCEPTS: {', '.join(lineage['key_concepts'])}")
    parts.append("")

    # Analytical dimensions
    parts.append("ANALYTICAL DIMENSIONS:")
    for dim in engine.get('analytical_dimensions', []):
        parts.append(f"  - {dim['key']}: {dim.get('description', '')}")
        if dim.get('probing_questions'):
            for q in dim['probing_questions']:
                parts.append(f"    ? {q}")
        if dim.get('depth_guidance'):
            for depth, guidance in dim['depth_guidance'].items():
                parts.append(f"    [{depth}] {guidance}")
        parts.append("")

    # Depth levels
    parts.append("DEPTH LEVELS:")
    for dl in engine.get('depth_levels', []):
        parts.append(f"  {dl['key']}: {dl.get('description', '')}")
        parts.append(f"    suitable_for: {dl.get('suitable_for', '')}")
        if dl.get('passes'):
            for p in dl['passes']:
                parts.append(f"    Pass {p['pass_number']}: {p.get('label', '')} "
                           f"[stance: {p.get('stance', '')}] "
                           f"dims: {p.get('focus_dimensions', [])} "
                           f"caps: {p.get('focus_capabilities', [])}")
        parts.append("")

    # Composability
    comp = engine.get('composability', {})
    if comp.get('shares_with'):
        parts.append("SHARES WITH DOWNSTREAM:")
        for k, v in comp['shares_with'].items():
            parts.append(f"  - {k}: {v}")
    if comp.get('consumes_from'):
        parts.append("CONSUMES FROM UPSTREAM:")
        for k, v in comp['consumes_from'].items():
            parts.append(f"  - {k}: {v}")
    parts.append("")

    # Existing capabilities (bare)
    parts.append("CURRENT CAPABILITIES (to be enriched):")
    for cap in engine.get('capabilities', []):
        parts.append(f"  - {cap['key']}: {cap.get('description', '')}")
        parts.append(f"    produces: {cap.get('produces_dimensions', [])}")
        parts.append(f"    requires: {cap.get('requires_dimensions', [])}")
    parts.append("")

    return "\n".join(parts)


def generate_enrichments(client: Anthropic, engine: dict) -> list[dict]:
    """Generate enriched capability definitions using Claude."""

    context = build_engine_context(engine)
    caps = engine.get('capabilities', [])
    cap_keys = [c['key'] for c in caps]

    prompt = f"""You are enriching capability definitions for an intellectual analysis engine.

Below is the FULL context of the engine — its problematique, intellectual lineage,
analytical dimensions, depth levels, and composability. Your task: for EACH capability
listed at the end, generate four enrichment fields.

{context}

For each of these {len(caps)} capabilities ({', '.join(cap_keys)}), generate:

1. **extended_description** (2-3 paragraphs, ~150-250 words):
   - First paragraph: What this capability actually does and WHY it matters for the
     engine's problematique. Ground it in the intellectual tradition. Don't just
     restate the one-liner — explain the analytical move.
   - Second paragraph: How this capability relates to the other capabilities and
     dimensions. What does it enable? What would be missing without it?
   - Optional third paragraph: What makes this non-trivial. What does a naive
     version miss that a sophisticated version catches?

2. **intellectual_grounding** (structured):
   - thinker: The specific thinker whose work MOST grounds this particular
     capability (can differ from the engine's primary thinker)
   - concept: The key concept from that thinker
   - method: 1-2 sentences on how the thinker's approach informs this capability

3. **indicators** (3-5 items):
   Textual signals that indicate this capability is needed. These are things
   you'd notice in a text that would tell you "this capability has work to do here."
   Be specific and concrete.

4. **depth_scaling** (3 entries):
   How this capability's output scales across surface/standard/deep.
   - surface: What you get with a quick pass (1 sentence)
   - standard: What you get with moderate analysis (1 sentence)
   - deep: What you get with full treatment (1 sentence)

CRITICAL REQUIREMENTS:
- Each capability's enrichment must feel grounded in the SPECIFIC intellectual tradition,
  not generic. If the engine is Brandomian, the enrichments should feel Brandomian. If
  Foucauldian, they should feel Foucauldian. The philosophical voice matters.
- The thinker in intellectual_grounding can be DIFFERENT from the engine's primary
  thinker — choose whoever most grounds THAT specific capability.
- Indicators should be concrete enough that you could point at a passage and say "this
  is why we need this capability here."
- Depth scaling should show genuine escalation, not just "more of the same."

Return ONLY valid JSON: a list of objects, one per capability, in the same order as listed.
Each object has: "key", "extended_description", "intellectual_grounding" (with "thinker",
"concept", "method"), "indicators" (list of strings), "depth_scaling" (dict with
"surface", "standard", "deep").

JSON output:"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()

    # Parse JSON — handle possible markdown wrapping
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    enrichments = json.loads(text)

    if len(enrichments) != len(caps):
        print(f"  WARNING: Got {len(enrichments)} enrichments for {len(caps)} capabilities")

    return enrichments


def apply_enrichments(engine: dict, enrichments: list[dict]) -> dict:
    """Apply enrichments to engine's capabilities."""
    caps = engine.get('capabilities', [])

    for cap in caps:
        # Find matching enrichment
        enrichment = None
        for e in enrichments:
            if e.get('key') == cap['key']:
                enrichment = e
                break

        if not enrichment:
            print(f"  WARNING: No enrichment found for {cap['key']}")
            continue

        # Apply enrichments
        cap['extended_description'] = enrichment.get('extended_description', '')
        cap['intellectual_grounding'] = enrichment.get('intellectual_grounding', {})
        cap['indicators'] = enrichment.get('indicators', [])
        cap['depth_scaling'] = enrichment.get('depth_scaling', {})

    return engine


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = Anthropic(api_key=api_key)

    yaml_files = sorted(DEFINITIONS_DIR.glob("*.yaml"))
    print(f"Found {len(yaml_files)} engine definitions\n", flush=True)

    for filepath in yaml_files:
        engine = load_engine_yaml(filepath)
        engine_key = engine.get('engine_key', filepath.stem)
        caps = engine.get('capabilities', [])

        if not caps:
            print(f"SKIP {engine_key}: no capabilities", flush=True)
            continue

        # Skip if already enriched
        already_enriched = all(
            cap.get('extended_description') for cap in caps
        )
        if already_enriched:
            print(f"SKIP {engine_key}: already enriched ({len(caps)} caps)", flush=True)
            continue

        print(f"{'='*60}", flush=True)
        print(f"ENGINE: {engine_key} ({len(caps)} capabilities)", flush=True)
        print(f"{'='*60}", flush=True)

        try:
            enrichments = generate_enrichments(client, engine)

            # Validate (soft — warn but proceed)
            valid = True
            for e in enrichments:
                if 'key' not in e:
                    print(f"  WARNING: Missing key in enrichment: {json.dumps(e)[:100]}")
                    valid = False
                if 'extended_description' not in e:
                    print(f"  WARNING: Missing extended_description for {e.get('key', '?')}")
                    # Try alternate names
                    for alt in ['description', 'extended_desc', 'ext_description']:
                        if alt in e:
                            e['extended_description'] = e[alt]
                            print(f"    -> Found as '{alt}', remapped")
                            break

            if not valid:
                print(f"  WARN: Some enrichments incomplete, saving what we have")

            engine = apply_enrichments(engine, enrichments)
            save_engine_yaml(filepath, engine)

            print(f"  ✓ Saved enriched capabilities to {filepath.name}", flush=True)
            for e in enrichments:
                desc_len = len(e.get('extended_description', ''))
                indicators_count = len(e.get('indicators', []))
                grounding = e.get('intellectual_grounding', {})
                thinker = grounding.get('thinker', '?') if isinstance(grounding, dict) else '?'
                print(f"    - {e.get('key', '?')}: {desc_len} chars, {indicators_count} indicators, "
                      f"grounded in {thinker}", flush=True)

        except json.JSONDecodeError as exc:
            print(f"  ✗ JSON parse error for {engine_key}: {exc}", flush=True)
            continue
        except Exception as exc:
            print(f"  ✗ Error for {engine_key}: {exc}")
            import traceback
            traceback.print_exc()
            continue

        print()
        time.sleep(1)  # Rate limiting courtesy

    print("\n✓ All engines processed")


if __name__ == "__main__":
    main()

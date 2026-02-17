#!/usr/bin/env python3
"""Enrich intellectual lineage for all capability engine definitions.

Transforms flat-string lineage (thinker names, tradition labels, concept labels)
into rich objects with bios, descriptions, and definitions using Claude API.

Writes back into YAML incrementally per engine.
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
        yaml.dump(data, f, default_flow_style=False, width=100,
                  allow_unicode=True, sort_keys=False)


def is_already_enriched(lineage: dict) -> bool:
    """Check if lineage has already been enriched to rich object form."""
    primary = lineage.get('primary')
    if isinstance(primary, dict) and primary.get('description'):
        return True
    return False


def generate_lineage_enrichment(client: Anthropic, engine: dict) -> dict:
    """Generate enriched lineage content using Claude."""

    lineage = engine.get('intellectual_lineage', {})
    primary = lineage.get('primary', '')
    secondary = lineage.get('secondary', [])
    traditions = lineage.get('traditions', [])
    key_concepts = lineage.get('key_concepts', [])

    context = f"""ENGINE: {engine['engine_name']} ({engine['engine_key']})
KIND: {engine.get('kind', 'unknown')}

PROBLEMATIQUE:
{engine.get('problematique', 'N/A')}

RESEARCHER QUESTION: {engine.get('researcher_question', 'N/A')}

CURRENT LINEAGE:
- Primary thinker: {primary}
- Secondary thinkers: {', '.join(secondary) if secondary else 'none'}
- Traditions: {', '.join(traditions) if traditions else 'none'}
- Key concepts: {', '.join(key_concepts) if key_concepts else 'none'}
"""

    prompt = f"""You are enriching the intellectual lineage for an analytical engine used in
a genealogical/philosophical document analysis system.

{context}

For this engine, generate rich descriptions for every element in its intellectual lineage.
The descriptions should be precise, scholarly, and relevant to HOW each thinker/tradition/concept
informs THIS engine's analytical approach.

Generate:

1. **primary** — The primary thinker:
   - name: "{primary}"
   - description: 2-3 sentences. Who they are, their dates, their key contribution
     relevant to this engine. Not a generic bio — explain WHY this thinker is the
     primary influence for THIS particular analytical lens.

2. **secondary** — Each secondary thinker ({len(secondary)} total: {', '.join(secondary)}):
   - name: (keep original)
   - description: 2-3 sentences each. Who they are, dates, and specifically how their
     work complements the primary thinker's framework for this engine's purpose.

3. **traditions** — Each intellectual tradition ({len(traditions)} total: {', '.join(traditions)}):
   - name: (keep original)
   - description: 2-3 sentences each. What the tradition IS, its core commitments, and
     how it informs this engine's analytical approach.

4. **key_concepts** — Each concept ({len(key_concepts)} total: {', '.join(key_concepts)}):
   - name: (keep original)
   - definition: 1-2 sentences each. A working definition that makes clear why this
     concept matters for the engine's analysis. Not a dictionary entry — a definition
     oriented toward analytical USE.

CRITICAL:
- Keep the original name/key exactly as-is (lowercase, underscored)
- Descriptions must be specific to THIS engine, not generic bios
- For thinkers, include birth-death years where known
- For traditions, explain core methodology/epistemology briefly
- For concepts, orient definition toward how the engine USES the concept

Return ONLY valid JSON with this structure:
{{
  "primary": {{"name": "...", "description": "..."}},
  "secondary": [{{"name": "...", "description": "..."}}, ...],
  "traditions": [{{"name": "...", "description": "..."}}, ...],
  "key_concepts": [{{"name": "...", "definition": "..."}}, ...]
}}

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

    result = json.loads(text)

    # Log token usage
    usage = response.usage
    print(f"  Tokens: {usage.input_tokens} in / {usage.output_tokens} out", flush=True)

    return result


def apply_lineage_enrichment(engine: dict, enrichment: dict) -> dict:
    """Transform flat lineage into rich objects."""

    lineage = engine.get('intellectual_lineage', {})

    # Primary
    primary_data = enrichment.get('primary', {})
    lineage['primary'] = {
        'name': primary_data.get('name', lineage.get('primary', '')),
        'description': primary_data.get('description', ''),
    }

    # Secondary
    secondary_list = enrichment.get('secondary', [])
    lineage['secondary'] = [
        {'name': s.get('name', ''), 'description': s.get('description', '')}
        for s in secondary_list
    ]

    # Traditions
    traditions_list = enrichment.get('traditions', [])
    lineage['traditions'] = [
        {'name': t.get('name', ''), 'description': t.get('description', '')}
        for t in traditions_list
    ]

    # Key concepts
    concepts_list = enrichment.get('key_concepts', [])
    lineage['key_concepts'] = [
        {'name': c.get('name', ''), 'definition': c.get('definition', '')}
        for c in concepts_list
    ]

    engine['intellectual_lineage'] = lineage
    return engine


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = Anthropic(api_key=api_key)

    yaml_files = sorted(DEFINITIONS_DIR.glob("*.yaml"))
    print(f"Found {len(yaml_files)} engine definitions\n", flush=True)

    enriched_count = 0
    skipped_count = 0

    for filepath in yaml_files:
        engine = load_engine_yaml(filepath)
        engine_key = engine.get('engine_key', filepath.stem)
        lineage = engine.get('intellectual_lineage', {})

        if not lineage:
            print(f"SKIP {engine_key}: no lineage", flush=True)
            skipped_count += 1
            continue

        if is_already_enriched(lineage):
            primary_name = lineage['primary'].get('name', '?') if isinstance(lineage['primary'], dict) else lineage['primary']
            sec_count = len(lineage.get('secondary', []))
            trad_count = len(lineage.get('traditions', []))
            concept_count = len(lineage.get('key_concepts', []))
            print(f"SKIP {engine_key}: already enriched (primary={primary_name}, "
                  f"{sec_count} secondary, {trad_count} traditions, {concept_count} concepts)", flush=True)
            skipped_count += 1
            continue

        primary = lineage.get('primary', '?')
        sec = lineage.get('secondary', [])
        trad = lineage.get('traditions', [])
        concepts = lineage.get('key_concepts', [])

        print(f"{'='*60}", flush=True)
        print(f"ENGINE: {engine_key}", flush=True)
        print(f"  Primary: {primary}", flush=True)
        print(f"  Secondary: {', '.join(sec)}", flush=True)
        print(f"  Traditions: {', '.join(trad)}", flush=True)
        print(f"  Key concepts: {', '.join(concepts)}", flush=True)
        print(f"{'='*60}", flush=True)

        try:
            enrichment = generate_lineage_enrichment(client, engine)

            # Validate
            if 'primary' not in enrichment:
                print(f"  WARNING: Missing primary in enrichment")
            if len(enrichment.get('secondary', [])) != len(sec):
                print(f"  WARNING: Got {len(enrichment.get('secondary', []))} secondary, expected {len(sec)}")
            if len(enrichment.get('traditions', [])) != len(trad):
                print(f"  WARNING: Got {len(enrichment.get('traditions', []))} traditions, expected {len(trad)}")
            if len(enrichment.get('key_concepts', [])) != len(concepts):
                print(f"  WARNING: Got {len(enrichment.get('key_concepts', []))} concepts, expected {len(concepts)}")

            engine = apply_lineage_enrichment(engine, enrichment)
            save_engine_yaml(filepath, engine)

            print(f"  Saved to {filepath.name}", flush=True)

            # Summary
            p = enrichment.get('primary', {})
            print(f"  Primary: {p.get('name', '?')} — {len(p.get('description', ''))} chars", flush=True)
            for s in enrichment.get('secondary', []):
                print(f"  Secondary: {s.get('name', '?')} — {len(s.get('description', ''))} chars", flush=True)
            for t in enrichment.get('traditions', []):
                print(f"  Tradition: {t.get('name', '?')} — {len(t.get('description', ''))} chars", flush=True)
            for c in enrichment.get('key_concepts', []):
                print(f"  Concept: {c.get('name', '?')} — {len(c.get('definition', ''))} chars", flush=True)

            enriched_count += 1

        except json.JSONDecodeError as exc:
            print(f"  JSON parse error: {exc}", flush=True)
            continue
        except Exception as exc:
            print(f"  Error: {exc}", flush=True)
            import traceback
            traceback.print_exc()
            continue

        print(flush=True)
        time.sleep(1)  # Rate limiting

    print(f"\nDone: {enriched_count} enriched, {skipped_count} skipped")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Engine Upgrade Script - Generate Advanced Engine Definitions via Claude API.

This script uses Claude Opus 4.5 with extended thinking (32k tokens) to generate
methodologically-grounded advanced engine definitions.

Usage:
    # Basic: pulls methodology from database
    python scripts/upgrade_engine.py causal_inference_auditor

    # Override methodology (optional)
    python scripts/upgrade_engine.py some_engine \
        --methodology "Custom method" \
        --theorists "Custom theorist"

    # Dry run (shows prompt without calling API)
    python scripts/upgrade_engine.py causal_inference_auditor --dry-run

    # Show token estimate only
    python scripts/upgrade_engine.py causal_inference_auditor --estimate-tokens
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import anthropic
except ImportError:
    print("Error: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)

try:
    from src.engines.schemas import EngineDefinition
except ImportError as e:
    print(f"Error importing schemas: {e}")
    print("Make sure you're running from the analyzer-v2 directory")
    sys.exit(1)


# Paths (PROJECT_ROOT defined above for imports)
CONTEXT_DIR = PROJECT_ROOT / "engine_upgrade_context"
EXAMPLES_DIR = CONTEXT_DIR / "examples"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "upgraded_engines"
DEFINITIONS_DIR = PROJECT_ROOT / "src" / "engines" / "definitions"


def load_system_prompt() -> str:
    """Load the comprehensive system prompt."""
    prompt_path = CONTEXT_DIR / "system_prompt.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"System prompt not found: {prompt_path}")
    return prompt_path.read_text()


def load_methodology_database() -> dict[str, Any]:
    """Load the methodology database."""
    db_path = CONTEXT_DIR / "methodology_database.yaml"
    if not db_path.exists():
        raise FileNotFoundError(f"Methodology database not found: {db_path}")
    with open(db_path) as f:
        return yaml.safe_load(f)


def load_example_engines(max_examples: int = 3) -> list[dict[str, Any]]:
    """Load example advanced engine definitions."""
    examples = []
    example_files = sorted(EXAMPLES_DIR.glob("*.json"))[:max_examples]
    for path in example_files:
        with open(path) as f:
            examples.append(json.load(f))
    return examples


def load_current_engine(engine_key: str) -> dict[str, Any] | None:
    """Load the current engine definition if it exists."""
    # Check for existing definition
    engine_path = DEFINITIONS_DIR / f"{engine_key}.json"
    if engine_path.exists():
        with open(engine_path) as f:
            return json.load(f)

    # Check for advanced version already
    advanced_path = DEFINITIONS_DIR / f"{engine_key}_advanced.json"
    if advanced_path.exists():
        print(f"Note: Advanced version already exists at {advanced_path}")
        with open(advanced_path) as f:
            return json.load(f)

    return None


def get_methodology_for_engine(
    engine_key: str,
    methodology_db: dict[str, Any],
    override_methodology: str | None = None,
    override_theorists: str | None = None,
) -> dict[str, Any]:
    """Get methodology info for an engine, with optional overrides."""
    # Check if engine is in database
    base_key = engine_key.replace("_advanced", "")

    if base_key in methodology_db:
        methodology = methodology_db[base_key].copy()
    else:
        # Create minimal methodology from overrides
        methodology = {
            "primary_method": override_methodology or "Custom methodology",
            "key_theorists": [],
            "key_concepts": [],
            "reasoning_domain": f"{base_key}_advanced",
            "framework_key": base_key,
        }

    # Apply overrides
    if override_methodology:
        methodology["primary_method"] = override_methodology
    if override_theorists:
        # Parse as comma-separated list
        theorist_names = [t.strip() for t in override_theorists.split(",")]
        methodology["key_theorists"] = [
            {"name": name, "contribution": "Custom contribution", "key_works": []}
            for name in theorist_names
        ]

    return methodology


def format_methodology_section(methodology: dict[str, Any]) -> str:
    """Format methodology info for the prompt."""
    lines = [
        f"## Primary Methodology: {methodology['primary_method']}",
        "",
        "### Key Theorists",
    ]

    for theorist in methodology.get("key_theorists", []):
        lines.append(f"\n**{theorist['name']}**")
        lines.append(f"- Contribution: {theorist.get('contribution', 'N/A')}")
        if theorist.get("key_works"):
            lines.append(f"- Key works: {', '.join(theorist['key_works'])}")

    lines.extend([
        "",
        "### Key Concepts (MUST appear in your engine)",
    ])

    for concept in methodology.get("key_concepts", []):
        lines.append(f"- {concept}")

    lines.extend([
        "",
        f"### Engine Settings",
        f"- reasoning_domain: \"{methodology.get('reasoning_domain', 'custom_advanced')}\"",
        f"- framework_key: \"{methodology.get('framework_key', 'custom')}\"",
    ])

    return "\n".join(lines)


def format_example_engine(engine: dict[str, Any], index: int) -> str:
    """Format an example engine for the prompt (truncated for token efficiency)."""
    lines = [
        f"## Example {index + 1}: {engine['engine_name']}",
        "",
        f"**Key**: `{engine['engine_key']}`",
        f"**Description**: {engine['description'][:200]}...",
        f"**Reasoning Domain**: `{engine['reasoning_domain']}`",
        "",
        "### Canonical Schema Structure (showing key entity types):",
        "```json",
    ]

    # Show truncated schema - just the top-level keys and first entity of each
    schema_preview = {}
    for key, value in engine.get("canonical_schema", {}).items():
        if isinstance(value, list) and len(value) > 0:
            schema_preview[key] = [value[0]]  # Just first item
        elif isinstance(value, dict):
            # For nested dicts like relationship_graph, show structure
            schema_preview[key] = {k: "..." for k in value.keys()}
        else:
            schema_preview[key] = value

    lines.append(json.dumps(schema_preview, indent=2)[:3000])  # Truncate
    lines.extend([
        "```",
        "",
        "### Stage Context Extraction Steps:",
    ])

    extraction_steps = engine.get("stage_context", {}).get("extraction", {}).get("extraction_steps", [])
    for step in extraction_steps[:5]:  # First 5 steps
        lines.append(f"- {step}")
    if len(extraction_steps) > 5:
        lines.append(f"- ... ({len(extraction_steps) - 5} more steps)")

    lines.extend([
        "",
        f"### Key Relationships: {engine.get('stage_context', {}).get('extraction', {}).get('key_relationships', [])}",
        "",
    ])

    return "\n".join(lines)


def construct_prompt(
    engine_key: str,
    current_engine: dict[str, Any] | None,
    methodology: dict[str, Any],
    examples: list[dict[str, Any]],
    system_prompt: str,
) -> str:
    """Construct the full prompt for Claude."""
    sections = []

    # System context
    sections.append("# SYSTEM CONTEXT\n")
    sections.append(system_prompt)
    sections.append("\n---\n")

    # Examples
    sections.append("# EXAMPLE ADVANCED ENGINES\n")
    sections.append("Study these examples carefully. Your output should match this level of depth and structure.\n")
    for i, example in enumerate(examples):
        sections.append(format_example_engine(example, i))
    sections.append("\n---\n")

    # Target engine
    sections.append("# TARGET ENGINE TO UPGRADE\n")
    if current_engine:
        sections.append(f"**Current Key**: `{current_engine.get('engine_key', engine_key)}`")
        sections.append(f"**Current Name**: {current_engine.get('engine_name', 'Unknown')}")
        sections.append(f"**Current Description**: {current_engine.get('description', 'None')}")
        sections.append("")
        sections.append("**What's wrong with the current version:**")
        sections.append("- Lacks methodological grounding")
        sections.append("- Schema is too shallow (missing entity types)")
        sections.append("- Extraction steps are generic, not methodology-specific")
        sections.append("- Missing relationship_graph section")
        sections.append("- Missing comprehensive meta section")
    else:
        sections.append(f"**New Engine**: `{engine_key}_advanced`")
        sections.append("(No current definition exists - creating from scratch)")
    sections.append("\n---\n")

    # Methodology requirements
    sections.append("# METHODOLOGY REQUIREMENTS\n")
    sections.append(format_methodology_section(methodology))
    sections.append("\n---\n")

    # Output instructions
    sections.append("# YOUR TASK\n")
    sections.append(f"""
Generate a complete advanced engine definition for `{engine_key}_advanced`.

Your output must be a SINGLE valid JSON object with this structure:
- All fields from the EngineDefinition schema (see system context)
- canonical_schema with 15+ entity types, all interconnected
- relationship_graph section with nodes, edges, clusters
- meta section with counts and highlights
- stage_context with detailed methodology-specific extraction_steps

CRITICAL REQUIREMENTS:
1. Every entity type in canonical_schema MUST have:
   - ID field with format specification (e.g., "string (format: 'CC{{N}}')")
   - Relationship fields pointing to other entities
   - Source tracking (source_articles)

2. extraction_steps MUST reference the actual methodology:
   - BAD: "Look for causal relationships"
   - GOOD: "Apply Pearl's backdoor criterion: identify set Z that blocks all backdoor paths"

3. key_concepts from the methodology MUST appear somewhere in the schema

4. Output ONLY the JSON. No markdown code fences, no explanations before or after.

Generate the complete engine definition now:
""")

    return "\n".join(sections)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars per token average)."""
    return len(text) // 4


def call_anthropic_api(prompt: str, dry_run: bool = False) -> tuple[str, str]:
    """Call Claude API with extended thinking (streaming). Returns (response_text, thinking_text)."""
    if dry_run:
        return ("DRY RUN - no API call made", "DRY RUN - no thinking")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)

    print("Calling Claude API with extended thinking (streaming)...")
    print(f"  Model: claude-opus-4-5-20251101")
    print(f"  Thinking budget: 32,000 tokens")
    print(f"  Max output: 64,000 tokens")
    print(f"  Prompt size: ~{estimate_tokens(prompt):,} tokens")
    print("")

    # Use streaming for extended thinking (required for long operations)
    thinking_text = ""
    response_text = ""

    with client.messages.stream(
        model="claude-opus-4-5-20251101",
        max_tokens=64000,
        thinking={
            "type": "enabled",
            "budget_tokens": 32000,
        },
        messages=[
            {"role": "user", "content": prompt}
        ],
    ) as stream:
        print("  Streaming response...")
        current_block_type = None
        for event in stream:
            # Handle content block start
            if hasattr(event, 'type'):
                if event.type == 'content_block_start':
                    if hasattr(event, 'content_block'):
                        current_block_type = event.content_block.type
                        if current_block_type == 'thinking':
                            print("  [Thinking...]", end="", flush=True)
                        elif current_block_type == 'text':
                            print("\n  [Generating JSON...]", end="", flush=True)
                elif event.type == 'content_block_delta':
                    if hasattr(event, 'delta'):
                        if hasattr(event.delta, 'thinking'):
                            thinking_text += event.delta.thinking
                        elif hasattr(event.delta, 'text'):
                            response_text += event.delta.text
                            # Print progress dots
                            if len(response_text) % 5000 == 0:
                                print(".", end="", flush=True)
                elif event.type == 'content_block_stop':
                    if current_block_type == 'thinking':
                        print(f" ({len(thinking_text):,} chars)")
                    elif current_block_type == 'text':
                        print(f" ({len(response_text):,} chars)")
                elif event.type == 'message_stop':
                    print("  [Message complete]")

        # Also try to get final message for verification
        try:
            final_message = stream.get_final_message()
            # Extract from final message as backup
            for block in final_message.content:
                if block.type == "thinking" and not thinking_text:
                    thinking_text = block.thinking
                elif block.type == "text" and not response_text:
                    response_text = block.text
            print(f"  Final message stop reason: {final_message.stop_reason}")
        except Exception as e:
            print(f"  Warning: Could not get final message: {e}")

    print("")
    return response_text, thinking_text


def fix_json_brackets(text: str) -> str:
    """Fix unbalanced brackets in JSON by removing extras at specific positions.

    This is string-aware - brackets inside quoted strings are ignored.
    """
    # Track extra brackets outside of strings
    extras = []
    in_string = False
    escape_next = False
    curly_depth = 0
    square_depth = 0

    for i, c in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if c == '\\':
            escape_next = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue

        if c == '{':
            curly_depth += 1
        elif c == '}':
            curly_depth -= 1
            if curly_depth < 0:
                extras.append(i)
                curly_depth = 0
        elif c == '[':
            square_depth += 1
        elif c == ']':
            square_depth -= 1
            if square_depth < 0:
                extras.append(i)
                square_depth = 0

    # Remove extras in reverse order to maintain positions
    result = list(text)
    for pos in sorted(extras, reverse=True):
        del result[pos]

    return ''.join(result)


def extract_json_from_response(response_text: str) -> dict[str, Any]:
    """Extract JSON from response, handling potential markdown fences and extra content."""
    text = response_text.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        # Find the end of the first line (```json or ```)
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        # Remove trailing fence
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    # Fix common JSON issues from LLM output
    # 1. Escaped single quotes (not valid JSON - single quotes don't need escaping)
    text = text.replace("\\'", "'")

    # 2. Fix stray quotes after array close: ]", -> ],
    text = re.sub(r'\]"(,)', r']\1', text)

    # 3. Fix unbalanced brackets (LLM sometimes adds extras)
    text = fix_json_brackets(text)

    # Try to parse directly
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # If "Extra data" error, try to extract just the first JSON object
        if "Extra data" in str(e):
            # Find the position and try parsing up to there
            try:
                # Use raw_decode to get just the first valid JSON
                decoder = json.JSONDecoder()
                obj, _ = decoder.raw_decode(text)
                return obj
            except json.JSONDecodeError:
                pass

        # Try to find balanced JSON object
        if text.startswith("{"):
            depth = 0
            in_string = False
            escape = False
            end_pos = 0

            for i, char in enumerate(text):
                if escape:
                    escape = False
                    continue
                if char == '\\' and in_string:
                    escape = True
                    continue
                if char == '"' and not escape:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        end_pos = i + 1
                        break

            if end_pos > 0:
                try:
                    return json.loads(text[:end_pos])
                except json.JSONDecodeError:
                    pass

        raise ValueError(f"Could not parse JSON from response: {e}")


def validate_engine(engine_dict: dict[str, Any]) -> EngineDefinition:
    """Validate engine against Pydantic schema."""
    return EngineDefinition.model_validate(engine_dict)


def save_outputs(
    engine_key: str,
    engine_dict: dict[str, Any],
    thinking_text: str,
) -> tuple[Path, Path]:
    """Save engine definition and thinking to files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save engine definition
    engine_path = OUTPUT_DIR / f"{engine_key}_advanced.json"
    with open(engine_path, "w") as f:
        json.dump(engine_dict, f, indent=2)

    # Save thinking
    thinking_path = OUTPUT_DIR / f"{engine_key}_advanced_thinking.md"
    with open(thinking_path, "w") as f:
        f.write(f"# Claude's Reasoning for {engine_key}_advanced\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(thinking_text)

    return engine_path, thinking_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate advanced engine definitions using Claude API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "engine_key",
        help="The engine key to upgrade (e.g., causal_inference_auditor)",
    )
    parser.add_argument(
        "--methodology",
        help="Override primary methodology (optional)",
    )
    parser.add_argument(
        "--theorists",
        help="Override key theorists (comma-separated, optional)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show prompt without calling API",
    )
    parser.add_argument(
        "--estimate-tokens",
        action="store_true",
        help="Show token estimate and exit",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=2,
        help="Maximum number of example engines to include (default: 2)",
    )

    args = parser.parse_args()

    print(f"Engine Upgrade Script")
    print(f"=" * 50)
    print(f"Target engine: {args.engine_key}")
    print("")

    # Load resources
    print("Loading resources...")
    try:
        system_prompt = load_system_prompt()
        print(f"  - System prompt: {len(system_prompt):,} chars")

        methodology_db = load_methodology_database()
        print(f"  - Methodology database: {len(methodology_db)} engines")

        examples = load_example_engines(args.max_examples)
        print(f"  - Example engines: {len(examples)}")

        current_engine = load_current_engine(args.engine_key)
        print(f"  - Current engine: {'found' if current_engine else 'not found'}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Get methodology
    methodology = get_methodology_for_engine(
        args.engine_key,
        methodology_db,
        args.methodology,
        args.theorists,
    )
    print(f"  - Methodology: {methodology['primary_method']}")
    print("")

    # Construct prompt
    prompt = construct_prompt(
        args.engine_key,
        current_engine,
        methodology,
        examples,
        system_prompt,
    )

    token_estimate = estimate_tokens(prompt)
    print(f"Prompt constructed: ~{token_estimate:,} tokens")

    if args.estimate_tokens:
        print("\nToken estimate mode - exiting without API call")
        return

    if args.dry_run:
        print("\n" + "=" * 50)
        print("DRY RUN - Full prompt:")
        print("=" * 50)
        print(prompt)
        print("=" * 50)
        print("\nDry run complete - no API call made")
        return

    # Call API
    print("")
    try:
        response_text, thinking_text = call_anthropic_api(prompt)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except anthropic.APIError as e:
        print(f"API Error: {e}")
        sys.exit(1)

    # Save raw response for debugging
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = OUTPUT_DIR / f"{args.engine_key}_advanced_raw.txt"
    with open(raw_path, "w") as f:
        f.write(response_text)
    print(f"Raw response saved to: {raw_path}")

    # Parse response
    print("\nParsing response...")
    try:
        engine_dict = extract_json_from_response(response_text)
        print(f"  - Parsed JSON with {len(engine_dict)} top-level keys")
    except ValueError as e:
        print(f"Error parsing response: {e}")
        print(f"\nRaw response saved to: {raw_path}")
        print("\nFirst 2000 chars:")
        print(response_text[:2000])
        print("\n\nLast 500 chars:")
        print(response_text[-500:] if len(response_text) > 500 else response_text)
        sys.exit(1)

    # Validate
    print("Validating against schema...")
    try:
        validated_engine = validate_engine(engine_dict)
        print(f"  - Validation passed!")
        print(f"  - Engine key: {validated_engine.engine_key}")
        print(f"  - Category: {validated_engine.category}")

        # Count entities in schema
        schema = engine_dict.get("canonical_schema", {})
        entity_count = sum(1 for v in schema.values() if isinstance(v, list))
        print(f"  - Entity types in schema: {entity_count}")
    except Exception as e:
        print(f"Validation warning: {e}")
        print("Saving anyway - review manually")

    # Save outputs
    print("\nSaving outputs...")
    engine_path, thinking_path = save_outputs(
        args.engine_key,
        engine_dict,
        thinking_text,
    )
    print(f"  - Engine definition: {engine_path}")
    print(f"  - Thinking log: {thinking_path}")

    print("\n" + "=" * 50)
    print("SUCCESS!")
    print(f"Review the generated engine at: {engine_path}")
    print(f"Review Claude's reasoning at: {thinking_path}")
    print("")
    print("Next steps:")
    print("1. Review the generated definition for quality")
    print("2. If good, copy to src/engines/definitions/")
    print("3. Test via the API: GET /v1/engines/{engine_key}_advanced")


if __name__ == "__main__":
    main()

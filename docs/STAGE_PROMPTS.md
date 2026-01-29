# Stage Prompt Architecture

> **Migration Date**: 2026-01-29
> **Breaking Change**: Yes - engine JSON format changed

## Overview

This document describes the new **Stage Prompt Composition** system that replaces the old engine-specific prompts with generic templates + engine context injection.

### Why This Change?

**Old approach** (160+ engines × 3 prompts = 480+ prompts to maintain):
```json
{
  "engine_key": "inferential_commitment_mapper",
  "extraction_prompt": "[4000 words of Brandomian primer + extraction steps]",
  "curation_prompt": "[2500 words of synthesis instructions]",
  "concretization_prompt": "[2000 words of translation guidance]"
}
```

**Problems**:
1. **Massive duplication** - Same Brandomian primer in multiple engines
2. **Maintenance nightmare** - Update methodology = touch 50+ files
3. **Inconsistent quality** - Some prompts well-maintained, others neglected
4. **No audience adaptation** - One prompt for all audiences

**New approach** (3 templates + shared frameworks + engine contexts):
```json
{
  "engine_key": "inferential_commitment_mapper",
  "stage_context": {
    "framework_key": "brandomian",
    "extraction": {
      "analysis_type": "inferential commitment",
      "core_question": "What are you really signing up for?",
      "id_field": "commitment_id",
      "key_relationships": ["entails", "conflicts_with"]
    },
    "curation": { ... },
    "concretization": { ... }
  }
}
```

**Benefits**:
1. **Single source of truth** - Update Brandomian primer once, all engines benefit
2. **Easy maintenance** - Templates and frameworks in dedicated files
3. **Consistent quality** - All engines use the same well-tested templates
4. **Audience adaptation** - Request prompts for researcher, analyst, executive, or activist

---

## Architecture

```
src/stages/
├── __init__.py              # Module exports
├── schemas.py               # Pydantic models for stage context
├── registry.py              # Loads templates and frameworks
├── composer.py              # Composes prompts using Jinja2
├── templates/
│   ├── extraction.md.j2     # Generic extraction template
│   ├── curation.md.j2       # Generic curation template
│   └── concretization.md.j2 # Generic concretization template
└── frameworks/
    ├── brandomian.json      # Brandomian inferentialism primer
    ├── dennett.json         # Dennett's critical toolkit
    └── toulmin.json         # Toulmin model of argumentation
```

### Component Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                      API Request                            │
│  GET /v1/engines/{key}/extraction-prompt?audience=executive │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     StageComposer                           │
│  - Loads template from StageRegistry                        │
│  - Loads framework primer (if specified)                    │
│  - Builds context dict from engine.stage_context            │
│  - Renders Jinja2 template                                  │
│  - Returns ComposedPrompt                                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────────┐
│  Template   │  │  Framework  │  │  Engine Context │
│ extraction  │  │  brandomian │  │  stage_context  │
│   .md.j2    │  │    .json    │  │    (from JSON)  │
└─────────────┘  └─────────────┘  └─────────────────┘
```

---

## Schema Reference

### StageContext (engine field)

```python
class StageContext(BaseModel):
    # Which framework primer to inject (optional)
    framework_key: Optional[str]  # "brandomian", "dennett", "toulmin"

    # Additional frameworks to layer on top
    additional_frameworks: list[str]

    # Stage-specific injection contexts
    extraction: ExtractionContext
    curation: CurationContext
    concretization: ConcretizationContext

    # Audience vocabulary overrides
    audience_vocabulary: AudienceVocabulary

    # Skip concretization for simple engines
    skip_concretization: bool
```

### ExtractionContext

```python
class ExtractionContext(BaseModel):
    # What this engine analyzes
    analysis_type: str           # "inferential commitment"
    analysis_type_plural: str    # "inferential commitments"

    # The core question
    core_question: str           # "What are you really signing up for?"

    # Numbered extraction steps
    extraction_steps: list[str]

    # Schema field descriptions
    key_fields: dict[str, str]

    # ID naming convention
    id_field: str                # "commitment_id"

    # Relationships to identify
    key_relationships: list[str] # ["entails", "conflicts_with"]

    # Additional instructions
    special_instructions: Optional[str]
```

### CurationContext

```python
class CurationContext(BaseModel):
    # What's being curated
    item_type: str
    item_type_plural: str

    # How to consolidate
    consolidation_rules: list[str]

    # Cross-document patterns
    cross_doc_patterns: list[str]

    # Named synthesis outputs
    synthesis_outputs: list[str]

    # Additional instructions
    special_instructions: Optional[str]
```

### ConcretizationContext

```python
class ConcretizationContext(BaseModel):
    # ID transformation examples
    id_examples: list[dict[str, str]]  # [{"from": "C1", "to": "The Big Commitment"}]

    # Naming guidance
    naming_guidance: str

    # Recommended table types
    recommended_table_types: list[str]

    # Recommended visual patterns
    recommended_visual_patterns: list[str]
```

---

## Framework Files

Frameworks contain reusable methodological primers:

```json
{
  "key": "brandomian",
  "name": "Brandomian Inferentialism",
  "description": "Robert Brandom's framework for...",
  "paradigm_keys": ["brandomian"],
  "primer": "## THE BRANDOMIAN FRAMEWORK\n\n[4000 words]...",
  "vocabulary": {
    "researcher": {"commitment": "inferential commitment", ...},
    "analyst": {"commitment": "commitment (what you're locked into)", ...},
    "executive": {"commitment": "what you're signing up for", ...},
    "activist": {"commitment": "what they're locked into", ...}
  }
}
```

### Available Frameworks

| Key | Name | Use Cases |
|-----|------|-----------|
| `brandomian` | Brandomian Inferentialism | Commitment mapping, implication analysis |
| `dennett` | Dennett's Critical Toolkit | Argument critique, assumption excavation |
| `toulmin` | Toulmin Model | Argument structure analysis |

---

## API Changes

### Prompt Endpoints

All prompt endpoints now accept an `audience` query parameter:

```
GET /v1/engines/{key}/extraction-prompt?audience=executive
GET /v1/engines/{key}/curation-prompt?audience=researcher
GET /v1/engines/{key}/concretization-prompt?audience=activist
```

**Audiences**:
- `researcher` - Full technical vocabulary
- `analyst` - Balanced, terms explained on first use
- `executive` - Plain language, zero jargon
- `activist` - Action-oriented, punchy, zero jargon

### Response Changes

```json
{
  "engine_key": "inferential_commitment_mapper",
  "prompt_type": "extraction",
  "prompt": "[fully composed prompt text]",
  "audience": "executive",
  "framework_used": "brandomian"
}
```

### New Endpoints

```
GET /v1/engines/{key}/stage-context
```
Returns raw stage context for debugging/inspection.

---

## Migration

### Migrating Engine Files

Run the migration script:

```bash
# Preview changes (dry run)
python scripts/migrate_engines_to_stages.py --dry-run

# Migrate all engines
python scripts/migrate_engines_to_stages.py

# Migrate single engine
python scripts/migrate_engines_to_stages.py --engine inferential_commitment_mapper
```

Backups are saved to `src/engines/definitions_backup_pre_stages/`.

### What the Migration Does

1. **Detects framework** - Analyzes extraction_prompt for Brandomian/Dennett/Toulmin patterns
2. **Extracts analysis_type** - Infers from engine_key and description
3. **Parses extraction steps** - Looks for numbered steps in the prompt
4. **Identifies relationships** - Scans for relationship types in prompts/schema
5. **Removes old fields** - Deletes extraction_prompt, curation_prompt, concretization_prompt
6. **Adds stage_context** - With all extracted metadata

### Manual Review Needed

After migration, review engines for:
- Correct `framework_key` detection
- Appropriate `extraction_steps`
- Complete `key_relationships`
- Any `special_instructions` that were lost

---

## Troubleshooting

### "Template not found for stage: X"

Templates are loaded from `src/stages/templates/`. Ensure the file exists:
- `extraction.md.j2`
- `curation.md.j2`
- `concretization.md.j2`

### "Framework not found: X"

Frameworks are loaded from `src/stages/frameworks/`. Check:
- File exists: `{framework_key}.json`
- JSON is valid
- `key` field matches filename

### Prompt Quality Issues

If composed prompts are missing content:
1. Check engine's `stage_context` has all required fields
2. Check template for correct variable names
3. Use `/v1/engines/{key}/stage-context` to inspect raw context

### Reload After Changes

```bash
# Via API
curl -X POST http://localhost:8001/v1/engines/reload

# Or restart the server
```

---

## Adding a New Framework

1. Create `src/stages/frameworks/{name}.json`:
```json
{
  "key": "my_framework",
  "name": "My Framework",
  "description": "Description...",
  "paradigm_keys": [],
  "primer": "## MY FRAMEWORK\n\n...",
  "vocabulary": { ... }
}
```

2. Reference in engine's `stage_context`:
```json
{
  "stage_context": {
    "framework_key": "my_framework",
    ...
  }
}
```

---

## Adding Custom Templates

For engines that need significantly different prompts, you can:

1. Create a custom template in `src/stages/templates/`
2. Reference it via the stage name (future feature)

Or use `special_instructions` field for engine-specific additions.

---

## Files Changed in Migration

| File | Change |
|------|--------|
| `src/engines/schemas.py` | Removed prompt fields, added stage_context |
| `src/engines/definitions/*.json` | Restructured to use stage_context |
| `src/api/routes/engines.py` | Prompt endpoints now compose at runtime |
| `requirements.txt` | Added Jinja2 |
| NEW: `src/stages/` | Entire module |
| NEW: `scripts/migrate_engines_to_stages.py` | Migration script |

---

## Rollback Procedure

If something breaks badly:

1. Restore engine definitions from backup:
```bash
cp src/engines/definitions_backup_pre_stages/*.json src/engines/definitions/
```

2. Revert schema changes (check git):
```bash
git checkout HEAD^ -- src/engines/schemas.py
```

3. Revert API routes:
```bash
git checkout HEAD^ -- src/api/routes/engines.py
```

#!/usr/bin/env python3
"""Import pre-computed markdown outputs into analyzer-v2's database.

Reads a plan directory (with 00_plan.md + phase_X_Y/ subdirs containing
markdown outputs) and inserts them as phase_outputs + executor_jobs records.

Usage:
    cd ~/projects/analyzer-v2
    python scripts/import_markdown_outputs.py /path/to/plan-dir [--plan-template plan-id]

The --plan-template flag copies metadata (thinker, works, strategy) from an
existing plan. Without it, metadata is parsed from 00_plan.md headers.
"""

import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.executor.job_manager import create_job, update_job_status
from src.executor.output_store import save_output
from src.orchestrator.schemas import (
    PhaseExecutionSpec,
    PriorWork,
    TargetWork,
    WorkflowExecutionPlan,
)


def parse_md_header(content: str) -> dict:
    """Parse the standard header from an output markdown file.

    Expected format:
        # Phase X.Y | engine_key | Pass N
        **Work**: work_key
        **Characters**: N,NNN
    """
    lines = content.split("\n", 6)

    header = {}

    # Line 0: # Phase X.Y | engine_key | Pass N
    m = re.match(r"#\s*Phase\s+([\d.]+)\s*\|\s*(\w+)\s*\|\s*Pass\s+(\d+)", lines[0])
    if m:
        header["phase_number"] = float(m.group(1))
        header["engine_key"] = m.group(2)
        header["pass_number"] = int(m.group(3))
    else:
        raise ValueError(f"Cannot parse header line: {lines[0]}")

    # Line 1: **Work**: work_key
    m = re.match(r"\*\*Work\*\*:\s*(.+)", lines[1])
    if m:
        header["work_key"] = m.group(1).strip()
    else:
        header["work_key"] = "target"

    # Characters line (informational only)
    for line in lines[1:5]:
        m = re.match(r"\*\*Characters\*\*:\s*([\d,]+)", line)
        if m:
            header["char_count"] = int(m.group(1).replace(",", ""))

    return header


def parse_plan_md(plan_path: Path) -> dict:
    """Parse 00_plan.md to extract plan-level metadata."""
    content = plan_path.read_text()
    info = {}

    m = re.search(r"\*\*Thinker\*\*:\s*(.+)", content)
    if m:
        info["thinker_name"] = m.group(1).strip()

    m = re.search(r"\*\*Target\*\*:\s*(.+)", content)
    if m:
        info["target_label"] = m.group(1).strip()

    m = re.search(r"\*\*Model\*\*:\s*(.+)", content)
    if m:
        info["model"] = m.group(1).strip()

    m = re.search(r"\*\*Estimated LLM calls\*\*:\s*(\d+)", content)
    if m:
        info["estimated_llm_calls"] = int(m.group(1))

    m = re.search(r"\*\*Strategy\*\*:\s*(.+?)(?=\n\n##|\Z)", content, re.DOTALL)
    if m:
        info["strategy"] = m.group(1).strip()

    # Extract phase info
    phases = []
    for pm in re.finditer(
        r"## Phase ([\d.]+):\s*(.+?)\n\n"
        r"- \*\*Depth\*\*:\s*(\w+)\n"
        r"- \*\*Per-work\*\*:\s*(\w+)\n"
        r"- \*\*Depends on\*\*:\s*\[([^\]]*)\]\n"
        r"- \*\*Model hint\*\*:\s*(\w+)\n\n"
        r"\*\*Rationale\*\*:\s*(.+?)(?=\n\n##|\Z)",
        content,
        re.DOTALL,
    ):
        phases.append({
            "phase_number": float(pm.group(1)),
            "phase_name": pm.group(2).strip(),
            "depth": pm.group(3).strip(),
            "per_work": pm.group(4).strip().lower() == "true",
            "depends_on": [float(x.strip()) for x in pm.group(5).split(",") if x.strip()],
            "model_hint": pm.group(6).strip(),
            "rationale": pm.group(7).strip(),
        })
    info["phases"] = phases

    return info


def build_plan(
    plan_dir: Path,
    plan_info: dict,
    template_plan: dict | None = None,
) -> WorkflowExecutionPlan:
    """Build a WorkflowExecutionPlan for the imported outputs."""
    plan_id = plan_dir.name  # e.g. "plan-ef57a3fb980c"

    # Use template for thinker/work metadata if available
    if template_plan:
        thinker_name = template_plan.get("thinker_name", plan_info.get("thinker_name", "Unknown"))
        target_work = TargetWork(**template_plan["target_work"])
        prior_works = [PriorWork(**pw) for pw in template_plan.get("prior_works", [])]
        research_question = template_plan.get("research_question")
    else:
        thinker_name = plan_info.get("thinker_name", "Unknown")
        target_work = TargetWork(
            title=plan_info.get("target_label", "Unknown"),
            author=thinker_name,
            year=None,
            description="Imported from pre-computed outputs",
        )
        prior_works = []
        research_question = None

    # Build phase specs from parsed plan
    phase_specs = []
    for p in plan_info.get("phases", []):
        phase_specs.append(PhaseExecutionSpec(
            phase_number=p["phase_number"],
            phase_name=p["phase_name"],
            depth=p["depth"],
            rationale=p["rationale"],
        ))

    strategy = plan_info.get("strategy", "")
    if template_plan and not strategy:
        strategy = template_plan.get("strategy_summary", "")

    return WorkflowExecutionPlan(
        plan_id=plan_id,
        created_at=datetime.utcnow().isoformat(),
        workflow_key="intellectual_genealogy",
        thinker_name=thinker_name,
        target_work=target_work,
        prior_works=prior_works,
        research_question=research_question,
        strategy_summary=strategy,
        phases=phase_specs,
        estimated_llm_calls=plan_info.get("estimated_llm_calls", 0),
        estimated_depth_profile="imported",
        status="completed",
        model_used=plan_info.get("model", "gemini-3.1-pro-preview"),
        execution_model=plan_info.get("model", "gemini-3.1-pro-preview"),
    )


def import_outputs(plan_dir: Path, template_plan_id: str | None = None):
    """Main import function."""
    plan_dir = Path(plan_dir)
    if not plan_dir.exists():
        print(f"Error: {plan_dir} does not exist")
        sys.exit(1)

    plan_md = plan_dir / "00_plan.md"
    if not plan_md.exists():
        print(f"Error: {plan_md} not found")
        sys.exit(1)

    # Parse plan metadata
    print(f"Parsing plan from {plan_md}...")
    plan_info = parse_plan_md(plan_md)
    print(f"  Thinker: {plan_info.get('thinker_name', '?')}")
    print(f"  Model: {plan_info.get('model', '?')}")
    print(f"  Phases: {len(plan_info.get('phases', []))}")

    # Load template plan if specified
    template_plan = None
    if template_plan_id:
        plans_dir = Path(__file__).parent.parent / "src" / "orchestrator" / "plans"
        template_path = plans_dir / f"{template_plan_id}.json"
        if template_path.exists():
            with open(template_path) as f:
                template_plan = json.load(f)
            print(f"  Using template plan: {template_plan_id}")
        else:
            print(f"  Warning: template plan {template_plan_id} not found, using parsed metadata")

    # Build and save plan
    plan = build_plan(plan_dir, plan_info, template_plan)
    plans_dir = Path(__file__).parent.parent / "src" / "orchestrator" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plans_dir / f"{plan.plan_id}.json"
    with open(plan_path, "w") as f:
        f.write(plan.model_dump_json(indent=2))
    print(f"  Saved plan: {plan_path}")

    # Create job
    job_id = f"job-import-{uuid.uuid4().hex[:8]}"
    print(f"\nCreating job {job_id}...")
    create_job(
        job_id=job_id,
        plan_id=plan.plan_id,
        plan_data=plan.model_dump(),
        workflow_key="intellectual_genealogy",
    )

    # Import all phase outputs
    phase_dirs = sorted(plan_dir.glob("phase_*"))
    total_outputs = 0
    total_chars = 0

    for phase_dir in phase_dirs:
        md_files = sorted(phase_dir.glob("*.md"))
        if not md_files:
            continue

        print(f"\n  {phase_dir.name}: {len(md_files)} files")

        for md_file in md_files:
            content = md_file.read_text()
            try:
                header = parse_md_header(content)
            except ValueError as e:
                print(f"    SKIP {md_file.name}: {e}")
                continue

            # Strip the header — content after the --- separator
            parts = content.split("---", 1)
            prose = parts[1].strip() if len(parts) > 1 else content

            output_id = save_output(
                job_id=job_id,
                phase_number=header["phase_number"],
                engine_key=header["engine_key"],
                pass_number=header["pass_number"],
                content=prose,
                work_key=header.get("work_key", "target"),
                model_used=plan_info.get("model", "gemini-3.1-pro-preview"),
                input_tokens=0,
                output_tokens=header.get("char_count", len(prose)) // 4,  # rough estimate
                metadata={"imported_from": str(md_file), "source_plan_dir": str(plan_dir)},
            )
            total_outputs += 1
            total_chars += len(prose)
            print(f"    {md_file.name} → {output_id} "
                  f"(phase={header['phase_number']}, engine={header['engine_key']}, "
                  f"pass={header['pass_number']}, work={header.get('work_key', 'target')})")

    # Mark job as completed
    update_job_status(job_id, "completed")

    print(f"\n{'='*60}")
    print(f"Import complete!")
    print(f"  Job ID:    {job_id}")
    print(f"  Plan ID:   {plan.plan_id}")
    print(f"  Outputs:   {total_outputs}")
    print(f"  Total:     {total_chars:,} characters")
    print(f"\nNext steps:")
    print(f"  1. Call presenter compose: POST /v1/presenter/compose")
    print(f"     Body: {{\"job_id\": \"{job_id}\", \"plan_id\": \"{plan.plan_id}\"}}")
    print(f"  2. Or fetch raw page: GET /v1/presenter/page/{job_id}")
    print(f"  3. Or import into the-critic: POST /api/genealogy/import-v2/{job_id}")


def import_via_api(plan_dir: Path, api_url: str, template_plan_id: str | None = None):
    """Import by calling the /v1/executor/import-outputs API endpoint."""
    import requests

    plan_dir = Path(plan_dir)
    plan_md = plan_dir / "00_plan.md"
    if not plan_md.exists():
        print(f"Error: {plan_md} not found")
        sys.exit(1)

    print(f"Parsing plan from {plan_md}...")
    plan_info = parse_plan_md(plan_md)
    print(f"  Thinker: {plan_info.get('thinker_name', '?')}")
    print(f"  Model: {plan_info.get('model', '?')}")

    # Load template plan if specified
    template_plan = None
    if template_plan_id:
        plans_dir = Path(__file__).parent.parent / "src" / "orchestrator" / "plans"
        template_path = plans_dir / f"{template_plan_id}.json"
        if template_path.exists():
            with open(template_path) as f:
                template_plan = json.load(f)
            print(f"  Using template plan: {template_plan_id}")

    # Build plan
    plan = build_plan(plan_dir, plan_info, template_plan)

    # Collect all outputs
    outputs = []
    phase_dirs = sorted(plan_dir.glob("phase_*"))
    for phase_dir in phase_dirs:
        md_files = sorted(phase_dir.glob("*.md"))
        for md_file in md_files:
            content = md_file.read_text()
            try:
                header = parse_md_header(content)
            except ValueError as e:
                print(f"  SKIP {md_file.name}: {e}")
                continue
            parts = content.split("---", 1)
            prose = parts[1].strip() if len(parts) > 1 else content
            outputs.append({
                "phase_number": header["phase_number"],
                "engine_key": header["engine_key"],
                "pass_number": header["pass_number"],
                "work_key": header.get("work_key", "target"),
                "content": prose,
                "model_used": plan_info.get("model", ""),
            })

    print(f"  Outputs to import: {len(outputs)}")
    print(f"  Total characters: {sum(len(o['content']) for o in outputs):,}")

    # Send to API
    payload = {
        "plan_id": plan.plan_id,
        "plan_data": plan.model_dump(),
        "workflow_key": plan.workflow_key,
        "outputs": outputs,
    }

    # Send in batches to avoid timeouts
    BATCH_SIZE = 20
    batches = [outputs[i:i + BATCH_SIZE] for i in range(0, len(outputs), BATCH_SIZE)]

    # First batch: create job
    print(f"\nSending batch 1/{len(batches)} to {api_url}/v1/executor/import-outputs ...")
    first_payload = {
        "plan_id": plan.plan_id,
        "plan_data": plan.model_dump(),
        "workflow_key": plan.workflow_key,
        "outputs": batches[0],
    }
    resp = requests.post(
        f"{api_url}/v1/executor/import-outputs",
        json=first_payload,
        timeout=300,
    )
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        sys.exit(1)

    result = resp.json()
    job_id = result["job_id"]
    total_imported = result["outputs_imported"]
    print(f"  Created job {job_id}, imported {total_imported} outputs")

    # Remaining batches: append
    for i, batch in enumerate(batches[1:], 2):
        print(f"  Sending batch {i}/{len(batches)} ({len(batch)} outputs)...")
        resp = requests.post(
            f"{api_url}/v1/executor/jobs/{job_id}/append-outputs",
            json={"outputs": batch},
            timeout=300,
        )
        if resp.status_code == 200:
            r = resp.json()
            total_imported += r["outputs_appended"]
            print(f"    Appended {r['outputs_appended']} outputs")
        else:
            print(f"    Error {resp.status_code}: {resp.text}")

    # Finalize
    print(f"  Finalizing job...")
    resp = requests.post(f"{api_url}/v1/executor/jobs/{job_id}/finalize", timeout=30)
    if resp.status_code == 200:
        print(f"  Job marked as completed")
    else:
        print(f"  Warning: finalize failed: {resp.text}")

    print(f"\n{'='*60}")
    print(f"Import complete!")
    print(f"  Job ID:    {job_id}")
    print(f"  Plan ID:   {plan.plan_id}")
    print(f"  Outputs:   {total_imported}")
    print(f"  Total:     {sum(len(o['content']) for o in outputs):,} characters")
    print(f"\nPresenter URL: {api_url}/v1/presenter/page/{job_id}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import pre-computed markdown outputs into analyzer-v2")
    parser.add_argument("plan_dir", help="Path to the plan directory (e.g., data/plan-ef57a3fb980c/)")
    parser.add_argument(
        "--plan-template",
        help="Copy thinker/work metadata from an existing plan ID (e.g., plan-9f17768fcc83)",
    )
    parser.add_argument(
        "--api-url",
        help="Import via API endpoint instead of direct DB (e.g., https://analyzer-v2-xxx.onrender.com)",
    )
    args = parser.parse_args()

    if args.api_url:
        import_via_api(Path(args.plan_dir), args.api_url, args.plan_template)
    else:
        import_outputs(Path(args.plan_dir), args.plan_template)

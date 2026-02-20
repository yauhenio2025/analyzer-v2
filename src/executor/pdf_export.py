"""PDF export for completed analysis jobs.

Generates professional A4 PDFs from job prose output using WeasyPrint.
Includes cover page, table of contents, per-phase sections, and appendix.
"""

import io
import logging
from datetime import datetime
from typing import Optional

import markdown

from src.executor.job_manager import get_job
from src.executor.output_store import load_phase_outputs
from src.orchestrator.planner import load_plan

logger = logging.getLogger(__name__)


def generate_analysis_pdf(job_id: str, phase: Optional[float] = None) -> bytes:
    """Generate a PDF document for a completed job.

    Args:
        job_id: The job ID to export.
        phase: Optional phase number to export (None = all phases).

    Returns:
        PDF bytes.

    Raises:
        ValueError: If job not found or not completed.
        ImportError: If weasyprint not installed.
    """
    try:
        from weasyprint import HTML
    except ImportError:
        raise ImportError(
            "weasyprint is required for PDF export. "
            "Install with: pip install weasyprint>=60.0"
        )

    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    plan_id = job.get("plan_id", "")
    plan = load_plan(plan_id) if plan_id else None

    thinker_name = plan.thinker_name if plan else "Unknown"
    strategy_summary = plan.strategy_summary if plan else ""

    # Collect phase outputs
    all_outputs = load_phase_outputs(job_id=job_id)
    if phase is not None:
        all_outputs = [o for o in all_outputs if o.get("phase_number") == phase]

    # Group outputs by phase, then by pass_number
    phases_data: dict[float, list[dict]] = {}
    for output in all_outputs:
        pn = output.get("phase_number", 0)
        phases_data.setdefault(pn, []).append(output)

    # Sort phases
    sorted_phases = sorted(phases_data.keys())

    # Build phase sections
    phase_sections = []
    for pn in sorted_phases:
        outputs = sorted(phases_data[pn], key=lambda o: o.get("pass_number", 0))
        phase_name = _get_phase_name(pn, plan)

        entries = []
        for output in outputs:
            content = output.get("content", "")
            if not content:
                continue
            engine_key = output.get("engine_key", "unknown")
            work_key = output.get("work_key", "")
            pass_number = output.get("pass_number", 0)

            # Convert markdown to HTML
            html_content = markdown.markdown(
                content,
                extensions=["tables", "fenced_code", "toc"],
            )

            entry_title = engine_key.replace("_", " ").title()
            if work_key:
                entry_title += f" — {_humanize_work_key(work_key)}"

            entries.append({
                "title": entry_title,
                "engine_key": engine_key,
                "work_key": work_key,
                "pass_number": pass_number,
                "html_content": html_content,
                "word_count": len(content.split()),
            })

        if entries:
            phase_sections.append({
                "phase_number": pn,
                "phase_name": phase_name,
                "entries": entries,
                "total_words": sum(e["word_count"] for e in entries),
            })

    # Execution stats
    stats = {
        "total_llm_calls": job.get("total_llm_calls", 0),
        "total_input_tokens": job.get("total_input_tokens", 0),
        "total_output_tokens": job.get("total_output_tokens", 0),
        "started_at": job.get("started_at", ""),
        "completed_at": job.get("completed_at", ""),
        "status": job.get("status", "unknown"),
    }

    total_words = sum(ps["total_words"] for ps in phase_sections)

    # Generate HTML
    html_str = _build_html(
        thinker_name=thinker_name,
        strategy_summary=strategy_summary,
        phase_sections=phase_sections,
        stats=stats,
        total_words=total_words,
        job_id=job_id,
    )

    # Convert to PDF
    pdf_bytes = HTML(string=html_str).write_pdf()
    logger.info(
        f"Generated PDF for job {job_id}: {len(pdf_bytes)} bytes, "
        f"{len(phase_sections)} phases, {total_words} words"
    )
    return pdf_bytes


def _get_phase_name(phase_number: float, plan) -> str:
    """Get human-readable phase name from plan."""
    if plan and plan.phases:
        for p in plan.phases:
            if p.phase_number == phase_number:
                return p.phase_name
    phase_names = {
        1.0: "Target Work Profiling",
        1.5: "Relationship Classification",
        2.0: "Prior Work Scanning",
        3.0: "Cross-Work Synthesis",
        4.0: "Final Synthesis",
    }
    return phase_names.get(phase_number, f"Phase {phase_number}")


def _humanize_work_key(work_key: str) -> str:
    """Convert work_key slug to readable title."""
    parts = work_key.split("___")
    if len(parts) >= 3:
        author = " ".join(w.capitalize() for w in parts[0].split("_"))
        title = " ".join(w.capitalize() for w in "_".join(parts[1:-1]).split("_"))
        year = parts[-1]
        return f"{author} - {title} ({year})"
    return " ".join(w.capitalize() for w in work_key.split("_"))


def _build_html(
    thinker_name: str,
    strategy_summary: str,
    phase_sections: list[dict],
    stats: dict,
    total_words: int,
    job_id: str,
) -> str:
    """Build the complete HTML document for PDF rendering."""
    now = datetime.now().strftime("%B %d, %Y")

    # Strategy as HTML
    strategy_html = markdown.markdown(strategy_summary) if strategy_summary else ""

    # Table of contents
    toc_items = ""
    for ps in phase_sections:
        toc_items += (
            f'<li><a href="#phase-{ps["phase_number"]}">'
            f'Phase {ps["phase_number"]}: {ps["phase_name"]}'
            f'<span class="toc-detail">{ps["total_words"]:,} words, '
            f'{len(ps["entries"])} sections</span></a></li>\n'
        )

    # Phase sections
    phase_html = ""
    for ps in phase_sections:
        phase_html += f'''
        <section class="phase-section" id="phase-{ps["phase_number"]}">
            <h2 class="phase-title">
                <span class="phase-number">{ps["phase_number"]}</span>
                {ps["phase_name"]}
            </h2>
            <p class="phase-meta">{len(ps["entries"])} sections &middot; {ps["total_words"]:,} words</p>
        '''
        for entry in ps["entries"]:
            phase_html += f'''
            <article class="engine-output">
                <h3 class="engine-title">{entry["title"]}</h3>
                <div class="engine-meta">
                    <span>Engine: <code>{entry["engine_key"]}</code></span>
                    <span>{entry["word_count"]:,} words</span>
                </div>
                <div class="prose-content">
                    {entry["html_content"]}
                </div>
            </article>
            '''
        phase_html += "</section>"

    # Stats for appendix
    duration = ""
    if stats["started_at"] and stats["completed_at"]:
        try:
            start = datetime.fromisoformat(str(stats["started_at"]).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(stats["completed_at"]).replace("Z", "+00:00"))
            mins = (end - start).total_seconds() / 60
            duration = f"{mins:.1f} minutes"
        except Exception:
            duration = "N/A"

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Intellectual Genealogy: {thinker_name}</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm 2.5cm;
            @top-center {{
                content: "Intellectual Genealogy: {thinker_name}";
                font-family: 'Inter', sans-serif;
                font-size: 8pt;
                color: #94a3b8;
            }}
            @bottom-center {{
                content: counter(page);
                font-family: 'Inter', sans-serif;
                font-size: 8pt;
                color: #94a3b8;
            }}
        }}
        @page:first {{
            @top-center {{ content: none; }}
            @bottom-center {{ content: none; }}
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Crimson Pro', 'Georgia', serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #1e293b;
        }}

        /* Cover page */
        .cover {{
            page-break-after: always;
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 80vh;
            text-align: center;
        }}
        .cover h1 {{
            font-size: 28pt;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 0.5em;
            line-height: 1.2;
        }}
        .cover .subtitle {{
            font-size: 14pt;
            color: #475569;
            margin-bottom: 2em;
        }}
        .cover .meta {{
            font-family: 'Inter', sans-serif;
            font-size: 10pt;
            color: #64748b;
        }}
        .cover .strategy {{
            margin-top: 3em;
            text-align: left;
            padding: 1.5em;
            background: #f8fafc;
            border-left: 4px solid #3b82f6;
            font-size: 10pt;
            line-height: 1.5;
        }}
        .cover .strategy h3 {{
            font-family: 'Inter', sans-serif;
            font-size: 10pt;
            color: #3b82f6;
            margin-bottom: 0.5em;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        /* Table of Contents */
        .toc {{
            page-break-after: always;
        }}
        .toc h2 {{
            font-family: 'Inter', sans-serif;
            font-size: 16pt;
            color: #0f172a;
            margin-bottom: 1em;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 0.5em;
        }}
        .toc ol {{
            list-style: none;
            padding: 0;
        }}
        .toc li {{
            padding: 0.5em 0;
            border-bottom: 1px solid #f1f5f9;
        }}
        .toc a {{
            text-decoration: none;
            color: #1e293b;
            font-size: 11pt;
        }}
        .toc .toc-detail {{
            float: right;
            font-family: 'Inter', sans-serif;
            font-size: 8pt;
            color: #94a3b8;
        }}

        /* Phase sections */
        .phase-section {{
            page-break-before: always;
        }}
        .phase-title {{
            font-family: 'Inter', sans-serif;
            font-size: 18pt;
            color: #0f172a;
            margin-bottom: 0.25em;
            border-bottom: 3px solid #3b82f6;
            padding-bottom: 0.3em;
        }}
        .phase-number {{
            display: inline-block;
            background: #3b82f6;
            color: white;
            width: 1.8em;
            height: 1.8em;
            line-height: 1.8em;
            text-align: center;
            border-radius: 50%;
            font-size: 12pt;
            margin-right: 0.4em;
            vertical-align: middle;
        }}
        .phase-meta {{
            font-family: 'Inter', sans-serif;
            font-size: 9pt;
            color: #64748b;
            margin-bottom: 1.5em;
        }}

        /* Engine output */
        .engine-output {{
            margin-bottom: 2em;
        }}
        .engine-title {{
            font-family: 'Inter', sans-serif;
            font-size: 12pt;
            color: #1e40af;
            margin-bottom: 0.25em;
        }}
        .engine-meta {{
            font-family: 'Inter', sans-serif;
            font-size: 8pt;
            color: #94a3b8;
            margin-bottom: 1em;
            display: flex;
            gap: 1.5em;
        }}
        .engine-meta code {{
            background: #f1f5f9;
            padding: 0.1em 0.3em;
            border-radius: 3px;
            font-size: 8pt;
        }}

        /* Prose content */
        .prose-content {{
            font-size: 10.5pt;
            line-height: 1.65;
        }}
        .prose-content h1, .prose-content h2, .prose-content h3,
        .prose-content h4, .prose-content h5, .prose-content h6 {{
            font-family: 'Inter', sans-serif;
            color: #0f172a;
            margin-top: 1em;
            margin-bottom: 0.4em;
        }}
        .prose-content h1 {{ font-size: 14pt; }}
        .prose-content h2 {{ font-size: 12pt; }}
        .prose-content h3 {{ font-size: 11pt; }}
        .prose-content p {{
            margin-bottom: 0.6em;
            text-align: justify;
        }}
        .prose-content ul, .prose-content ol {{
            margin-left: 1.5em;
            margin-bottom: 0.6em;
        }}
        .prose-content li {{
            margin-bottom: 0.3em;
        }}
        .prose-content blockquote {{
            border-left: 3px solid #cbd5e1;
            padding-left: 1em;
            margin: 0.8em 0;
            color: #475569;
            font-style: italic;
        }}
        .prose-content code {{
            font-family: 'Courier New', monospace;
            background: #f1f5f9;
            padding: 0.1em 0.3em;
            border-radius: 3px;
            font-size: 9pt;
        }}
        .prose-content table {{
            width: 100%;
            border-collapse: collapse;
            margin: 0.8em 0;
            font-size: 9pt;
        }}
        .prose-content th, .prose-content td {{
            border: 1px solid #e2e8f0;
            padding: 0.4em 0.6em;
            text-align: left;
        }}
        .prose-content th {{
            background: #f8fafc;
            font-family: 'Inter', sans-serif;
            font-weight: 600;
        }}

        /* Appendix */
        .appendix {{
            page-break-before: always;
        }}
        .appendix h2 {{
            font-family: 'Inter', sans-serif;
            font-size: 16pt;
            color: #0f172a;
            margin-bottom: 1em;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 0.5em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.8em;
        }}
        .stat-item {{
            padding: 0.8em;
            background: #f8fafc;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
        }}
        .stat-label {{
            font-family: 'Inter', sans-serif;
            font-size: 8pt;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .stat-value {{
            font-family: 'Inter', sans-serif;
            font-size: 14pt;
            font-weight: 700;
            color: #0f172a;
            margin-top: 0.2em;
        }}
    </style>
</head>
<body>

<!-- Cover Page -->
<div class="cover">
    <h1>Intellectual Genealogy</h1>
    <div class="subtitle">{thinker_name}</div>
    <div class="meta">
        <p>Generated {now}</p>
        <p>{total_words:,} words across {len(phase_sections)} phases</p>
        <p>Job: {job_id[:12]}</p>
    </div>
    {f'<div class="strategy"><h3>Analysis Strategy</h3>{strategy_html}</div>' if strategy_html else ''}
</div>

<!-- Table of Contents -->
<div class="toc">
    <h2>Contents</h2>
    <ol>
        {toc_items}
        <li><a href="#appendix">Appendix: Execution Statistics</a></li>
    </ol>
</div>

<!-- Phase Sections -->
{phase_html}

<!-- Appendix -->
<section class="appendix" id="appendix">
    <h2>Appendix: Execution Statistics</h2>
    <div class="stats-grid">
        <div class="stat-item">
            <div class="stat-label">Total Words</div>
            <div class="stat-value">{total_words:,}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">LLM Calls</div>
            <div class="stat-value">{stats["total_llm_calls"]}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Input Tokens</div>
            <div class="stat-value">{stats["total_input_tokens"]:,}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Output Tokens</div>
            <div class="stat-value">{stats["total_output_tokens"]:,}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Duration</div>
            <div class="stat-value">{duration or 'N/A'}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Status</div>
            <div class="stat-value">{stats["status"]}</div>
        </div>
    </div>
</section>

</body>
</html>'''

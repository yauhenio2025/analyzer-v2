"""Phase runner: executes a single workflow phase.

The phase runner resolves what a phase MEANS:
- chain_key → run the chain (sequential engines)
- engine_key → run a single engine (multi-pass via operationalizations)
- Per-work iteration (Phase 1.5, 2.0) → run N times, once per prior work

It applies plan overrides (depth, focus_dimensions, context_emphasis, model_hint)
and handles the per-work parallelism when applicable.

Ported from The Critic's analyze_genealogy.py phase dispatching logic,
now fully plan-driven instead of hardcoded.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from src.aoi.contract import is_aoi_workflow_key
from src.executor.chain_runner import run_chain, run_single_engine
from src.executor.context_broker import assemble_phase_context
from src.executor.document_ids import resolve_target_doc_id
from src.executor.document_store import get_document_text
from src.executor.job_manager import get_job
from src.executor.schemas import (
    EngineCallResult,
    PhaseResult,
    PhaseStatus,
)
from src.orchestrator.schemas import PhaseExecutionSpec
from src.workflows.schemas import WorkflowPhase

logger = logging.getLogger(__name__)

# Max concurrent per-work executions (to avoid flooding the API)
MAX_WORK_CONCURRENCY = 3


def _resolve_execution_target(
    workflow_chain_key: Optional[str],
    workflow_engine_key: Optional[str],
    plan_chain_key: Optional[str],
    plan_engine_key: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Resolve the effective chain/engine for a phase.

    An explicit plan engine override suppresses the workflow template chain.
    Otherwise template chain fallback would make single-engine overrides
    impossible for template-backed phases.
    """
    effective_chain_key = workflow_chain_key
    effective_engine_key = workflow_engine_key

    if plan_chain_key:
        effective_chain_key = plan_chain_key
        effective_engine_key = None

    if plan_engine_key:
        effective_chain_key = None
        effective_engine_key = plan_engine_key

    if effective_engine_key:
        from src.chains.registry import get_chain_registry
        from src.engines.registry import get_engine_registry

        chain_keys = set(get_chain_registry().list_keys())
        engine_reg = get_engine_registry()
        engine_keys = set(engine_reg.list_keys())
        try:
            engine_keys.update(engine_reg.list_capability_keys())
        except Exception:
            pass

        if effective_engine_key not in engine_keys and effective_engine_key in chain_keys:
            logger.warning(
                "Execution target '%s' was stored as engine_key but is a chain; "
                "treating it as chain_key for backward compatibility",
                effective_engine_key,
            )
            effective_chain_key = effective_engine_key
            effective_engine_key = None

    return effective_chain_key, effective_engine_key


def run_phase(
    workflow_phase: WorkflowPhase,
    plan_phase: PhaseExecutionSpec,
    *,
    job_id: str,
    document_ids: Optional[dict[str, str]] = None,
    prior_work_titles: Optional[list[str]] = None,
    cancellation_check: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
    context_char_overrides: Optional[dict[float, int]] = None,
) -> PhaseResult:
    """Execute a single workflow phase with plan overrides.

    Args:
        workflow_phase: The phase definition from the workflow
        plan_phase: The plan's configuration for this phase
        job_id: Job ID for output persistence
        document_ids: Map of work title -> doc_id for uploaded texts
        prior_work_titles: List of prior work titles (for per-work phases)
        cancellation_check: Callable that returns True to cancel
        progress_callback: Callable for progress updates
        context_char_overrides: Per-phase max context chars (Milestone 5).
            Allows Phase 1.0's expanded analysis to pass through at higher
            char limits when consumed by downstream phases.

    Returns:
        PhaseResult with all engine outputs and metadata.
    """
    phase_number = plan_phase.phase_number
    phase_name = plan_phase.phase_name
    start_time = time.time()

    logger.info(
        f"=== Phase {phase_number}: {phase_name} ===\n"
        f"  depth={plan_phase.depth}, skip={plan_phase.skip}, "
        f"model_hint={plan_phase.model_hint}, "
        f"requires_full_docs={plan_phase.requires_full_documents}"
    )

    # Skip check
    if plan_phase.skip:
        logger.info(f"Phase {phase_number} skipped: {plan_phase.skip_reason}")
        return PhaseResult(
            phase_number=phase_number,
            phase_name=phase_name,
            status=PhaseStatus.SKIPPED,
        )

    if progress_callback:
        progress_callback(f"Starting phase {phase_number}: {phase_name}")

    try:
        # Assemble upstream context
        upstream_context = ""
        if workflow_phase.depends_on_phases:
            upstream_context = assemble_phase_context(
                job_id=job_id,
                upstream_phases=workflow_phase.depends_on_phases,
                context_emphasis=plan_phase.context_emphasis,
                phase_max_chars_override=context_char_overrides,
            )

        # Determine if this is a per-work phase
        is_per_work = _is_per_work_phase(phase_number, prior_work_titles, plan_phase)

        # Chapter-targeted execution
        if plan_phase.chapter_targets and plan_phase.document_scope == "chapter":
            return _run_chapter_targeted_phase(
                workflow_phase=workflow_phase,
                plan_phase=plan_phase,
                job_id=job_id,
                document_ids=document_ids or {},
                upstream_context=upstream_context,
                cancellation_check=cancellation_check,
                progress_callback=progress_callback,
                start_time=start_time,
            )

        if is_per_work and prior_work_titles:
            # Per-work execution (Phase 1.5, 2.0)
            return _run_per_work_phase(
                workflow_phase=workflow_phase,
                plan_phase=plan_phase,
                job_id=job_id,
                document_ids=document_ids or {},
                prior_work_titles=prior_work_titles,
                upstream_context=upstream_context,
                cancellation_check=cancellation_check,
                progress_callback=progress_callback,
                start_time=start_time,
            )
        else:
            # Standard single-execution phase
            return _run_standard_phase(
                workflow_phase=workflow_phase,
                plan_phase=plan_phase,
                job_id=job_id,
                document_ids=document_ids or {},
                upstream_context=upstream_context,
                cancellation_check=cancellation_check,
                progress_callback=progress_callback,
                start_time=start_time,
            )

    except InterruptedError:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Phase {phase_number} failed: {e}", exc_info=True)
        return PhaseResult(
            phase_number=phase_number,
            phase_name=phase_name,
            status=PhaseStatus.FAILED,
            error=str(e),
            duration_ms=duration_ms,
        )


def _is_per_work_phase(
    phase_number: float,
    prior_work_titles: Optional[list[str]],
    plan_phase: Optional[PhaseExecutionSpec] = None,
) -> bool:
    """Determine if a phase should run per-work.

    Checks plan's iteration_mode first (adaptive mode),
    falls back to legacy hardcoded check for phases 1.5/2.0.
    """
    if not prior_work_titles:
        return False
    # Adaptive mode: check plan's iteration_mode
    if plan_phase and plan_phase.iteration_mode:
        return plan_phase.iteration_mode in ("per_work", "per_work_filtered")
    # Legacy fallback
    return phase_number in (1.5, 2.0)


def _run_standard_phase(
    workflow_phase: WorkflowPhase,
    plan_phase: PhaseExecutionSpec,
    job_id: str,
    document_ids: dict[str, str],
    upstream_context: str,
    cancellation_check: Optional[Callable[[], bool]],
    progress_callback: Optional[Callable[[str], None]],
    start_time: float,
) -> PhaseResult:
    """Run a standard (non-per-work) phase."""
    phase_number = plan_phase.phase_number
    phase_name = plan_phase.phase_name

    # Get document text for the target work or workflow-specific combined corpus
    document_text = _get_standard_phase_document_text(
        document_ids=document_ids,
        job_id=job_id,
        phase_number=phase_number,
    )

    # Resolve engine overrides from the plan
    engine_overrides = None
    if plan_phase.engine_overrides:
        engine_overrides = {
            k: v if isinstance(v, dict) else v.model_dump()
            for k, v in plan_phase.engine_overrides.items()
        }

    # Resolve chain/engine. An explicit engine override suppresses the template
    # chain; otherwise template chain fallback would make single-engine adaptive
    # phases impossible on template-backed workflows.
    effective_chain_key, effective_engine_key = _resolve_execution_target(
        workflow_phase.chain_key,
        workflow_phase.engine_key,
        plan_phase.chain_key,
        plan_phase.engine_key,
    )

    # Run chain or single engine
    if effective_chain_key:
        result = run_chain(
            chain_key=effective_chain_key,
            document_text=document_text,
            job_id=job_id,
            phase_number=phase_number,
            depth=plan_phase.depth,
            engine_overrides=engine_overrides,
            context_emphasis=plan_phase.context_emphasis,
            upstream_context=upstream_context,
            model_hint=plan_phase.model_hint,
            requires_full_documents=plan_phase.requires_full_documents,
            cancellation_check=cancellation_check,
            progress_callback=progress_callback,
        )
    elif effective_engine_key:
        # Resolve per-engine override for the single engine
        focus_dims = None
        engine_depth = plan_phase.depth
        if engine_overrides and effective_engine_key in engine_overrides:
            ov = engine_overrides[effective_engine_key]
            engine_depth = ov.get("depth", plan_phase.depth) if isinstance(ov, dict) else plan_phase.depth
            focus_dims = ov.get("focus_dimensions") if isinstance(ov, dict) else None

        result = run_single_engine(
            engine_key=effective_engine_key,
            document_text=document_text,
            job_id=job_id,
            phase_number=phase_number,
            depth=engine_depth,
            focus_dimensions=focus_dims,
            upstream_context=upstream_context,
            context_emphasis=plan_phase.context_emphasis,
            model_hint=plan_phase.model_hint,
            requires_full_documents=plan_phase.requires_full_documents,
            cancellation_check=cancellation_check,
            progress_callback=progress_callback,
        )
    else:
        raise ValueError(
            f"Phase {phase_number} has no chain_key or engine_key"
        )

    # --- Milestone 5: Supplementary chain execution ---
    # After the primary chain/engine, run any supplementary chains the
    # orchestrator selected. Each supplementary chain receives the primary
    # output as upstream context and the same document text. All outputs
    # are concatenated into the phase's final output, creating a rich
    # multi-engine analysis that downstream per-work phases consume as
    # distilled context (instead of raw document text).
    if plan_phase.supplementary_chains:
        supp_engine_results = {}
        supp_total_tokens = 0
        primary_output = result["final_output"]

        for supp_idx, supp_chain_key in enumerate(plan_phase.supplementary_chains):
            if cancellation_check and cancellation_check():
                raise InterruptedError(
                    f"Cancelled before supplementary chain {supp_chain_key}"
                )

            if progress_callback:
                progress_callback(
                    f"Supplementary {supp_idx + 1}/{len(plan_phase.supplementary_chains)}: "
                    f"{supp_chain_key}"
                )

            logger.info(
                f"Phase {phase_number}: running supplementary chain "
                f"'{supp_chain_key}' ({supp_idx + 1}/{len(plan_phase.supplementary_chains)})"
            )

            try:
                supp_result = run_chain(
                    chain_key=supp_chain_key,
                    document_text=document_text,
                    job_id=job_id,
                    phase_number=phase_number,
                    depth=plan_phase.depth,
                    engine_overrides=engine_overrides,
                    context_emphasis=plan_phase.context_emphasis,
                    # Feed primary chain output as upstream context
                    upstream_context=(upstream_context + "\n\n---\n\n" + primary_output)
                        if upstream_context else primary_output,
                    model_hint=plan_phase.model_hint,
                    requires_full_documents=plan_phase.requires_full_documents,
                    cancellation_check=cancellation_check,
                    progress_callback=progress_callback,
                )

                supp_engine_results.update(supp_result["engine_results"])
                supp_total_tokens += supp_result["total_tokens"]

                logger.info(
                    f"Supplementary chain '{supp_chain_key}' complete: "
                    f"{supp_result['total_tokens']:,} tokens"
                )
            except InterruptedError:
                raise
            except Exception as e:
                logger.error(
                    f"Supplementary chain '{supp_chain_key}' failed (non-fatal): {e}",
                    exc_info=True,
                )
                # Continue with remaining supplementary chains

        # Merge supplementary results into the primary result
        result["engine_results"].update(supp_engine_results)
        result["total_tokens"] += supp_total_tokens

        # Concatenate all outputs: primary + each supplementary chain's final output
        combined_parts = [primary_output]
        for supp_chain_key in plan_phase.supplementary_chains:
            # Each supplementary chain may have contributed multiple engines;
            # take the last engine's last pass as that chain's contribution
            for eng_key, passes in supp_engine_results.items():
                if passes:
                    combined_parts.append(
                        f"\n\n## Supplementary Analysis: {eng_key}\n\n{passes[-1].content}"
                    )

        result["final_output"] = "\n\n---\n\n".join(combined_parts)

        logger.info(
            f"Phase {phase_number}: {len(plan_phase.supplementary_chains)} supplementary "
            f"chains complete, total supplementary tokens: {supp_total_tokens:,}"
        )

    duration_ms = int((time.time() - start_time) * 1000)

    return PhaseResult(
        phase_number=phase_number,
        phase_name=phase_name,
        status=PhaseStatus.COMPLETED,
        engine_results=result["engine_results"],
        final_output=result["final_output"],
        duration_ms=duration_ms,
        total_tokens=result["total_tokens"],
    )


def _run_per_work_phase(
    workflow_phase: WorkflowPhase,
    plan_phase: PhaseExecutionSpec,
    job_id: str,
    document_ids: dict[str, str],
    prior_work_titles: list[str],
    upstream_context: str,
    cancellation_check: Optional[Callable[[], bool]],
    progress_callback: Optional[Callable[[str], None]],
    start_time: float,
) -> PhaseResult:
    """Run a phase that iterates over prior works.

    Each work gets its own execution with potentially different depth/focus
    based on per_work_overrides from the plan.
    """
    phase_number = plan_phase.phase_number
    phase_name = plan_phase.phase_name

    work_results: dict[str, dict[str, list[EngineCallResult]]] = {}
    total_tokens = 0
    errors: list[str] = []
    target_title = _get_target_work_title(job_id)

    # Milestone 5: Determine if we should use distilled analysis
    # If upstream_context is available AND this is a per-work phase (1.5 or 2.0),
    # use the distilled analysis from Phase 1.0 instead of raw target text.
    # The upstream_context comes from the context broker's assembly of Phase 1.0
    # outputs (which may include supplementary chain outputs).
    use_distilled = bool(upstream_context) and phase_number in (1.5, 2.0)
    if use_distilled:
        logger.info(
            f"Phase {phase_number}: using distilled analysis "
            f"({len(upstream_context):,} chars) instead of raw target text "
            f"for {len(prior_work_titles)} per-work iterations"
        )

    def run_one_work(work_title: str) -> tuple[str, dict, int]:
        """Execute the phase for a single prior work. Returns (title, results, tokens)."""
        if cancellation_check and cancellation_check():
            raise InterruptedError(f"Cancelled before processing {work_title}")

        if progress_callback:
            progress_callback(f"{phase_name}: {work_title}")

        # Resolve per-work overrides
        work_depth = plan_phase.depth
        work_focus_dims = None
        if plan_phase.per_work_overrides and work_title in plan_phase.per_work_overrides:
            override = plan_phase.per_work_overrides[work_title]
            work_depth = override.get("depth", plan_phase.depth)
            work_focus_dims = override.get("focus_dimensions")

        # Get document text for this work
        doc_text = _get_work_document_text(work_title, document_ids)

        # Determine if this phase needs the target work text at all.
        # Phases with NO dependencies (like 1.8 Prior Work Profiling) are
        # profiling ONLY the prior works — injecting the target text would
        # cause the LLM to analyze the wrong document.
        is_independent_profiling = not plan_phase.depends_on

        # Milestone 5: Use distilled analysis path when available
        if use_distilled:
            # Replace raw target text with distilled multi-engine analysis
            combined_text = _combine_with_distilled_analysis(
                distilled_analysis=upstream_context,
                work_text=doc_text,
                work_title=work_title,
                target_title=target_title,
                phase_number=phase_number,
            )
            # Don't pass upstream_context again to the chain/engine — it's
            # already embedded in the combined_text
            effective_upstream = ""
        elif is_independent_profiling:
            # Independent per-work profiling: ONLY the prior work text.
            # Do NOT include the target — this phase profiles each prior work
            # on its own terms, without reference to the target.
            combined_text = f"# {work_title}\n\n{doc_text}"
            effective_upstream = ""
            logger.info(
                f"Phase {phase_number}: independent profiling of '{work_title}' "
                f"({len(doc_text):,} chars, no target text injected)"
            )
        else:
            # Legacy path: concatenate both full texts (for phases that need
            # both target and prior work, like classification or scanning)
            target_text = _get_target_document_text(document_ids)
            combined_text = _combine_document_texts(
                target_text=target_text,
                work_text=doc_text,
                work_title=work_title,
                target_title=target_title,
                phase_number=phase_number,
            )
            effective_upstream = upstream_context

        # Engine overrides from plan
        engine_overrides = None
        if plan_phase.engine_overrides:
            engine_overrides = {
                k: v if isinstance(v, dict) else v.model_dump()
                for k, v in plan_phase.engine_overrides.items()
            }

        work_key = _sanitize_work_key(work_title)

        effective_chain_key, effective_engine_key = _resolve_execution_target(
            workflow_phase.chain_key,
            workflow_phase.engine_key,
            plan_phase.chain_key,
            plan_phase.engine_key,
        )

        # Per-work chain map (most specific override)
        if plan_phase.per_work_chain_map and work_title in plan_phase.per_work_chain_map:
            effective_chain_key = plan_phase.per_work_chain_map[work_title]
            effective_engine_key = None  # chain takes precedence

        if effective_chain_key:
            result = run_chain(
                chain_key=effective_chain_key,
                document_text=combined_text,
                job_id=job_id,
                phase_number=phase_number,
                work_key=work_key,
                depth=work_depth,
                engine_overrides=engine_overrides,
                context_emphasis=plan_phase.context_emphasis,
                upstream_context=effective_upstream,
                model_hint=plan_phase.model_hint,
                requires_full_documents=plan_phase.requires_full_documents,
                cancellation_check=cancellation_check,
            )
        elif effective_engine_key:
            result = run_single_engine(
                engine_key=effective_engine_key,
                document_text=combined_text,
                job_id=job_id,
                phase_number=phase_number,
                work_key=work_key,
                depth=work_depth,
                focus_dimensions=work_focus_dims,
                upstream_context=effective_upstream,
                context_emphasis=plan_phase.context_emphasis,
                model_hint=plan_phase.model_hint,
                requires_full_documents=plan_phase.requires_full_documents,
                cancellation_check=cancellation_check,
            )
        else:
            raise ValueError(
                f"Phase {phase_number} has no chain_key or engine_key"
            )

        return work_title, result["engine_results"], result["total_tokens"]

    # Execute per-work — use thread pool for parallelism
    with ThreadPoolExecutor(max_workers=MAX_WORK_CONCURRENCY) as executor:
        futures = {
            executor.submit(run_one_work, title): title
            for title in prior_work_titles
        }

        for future in as_completed(futures):
            work_title = futures[future]
            try:
                title, eng_results, tokens = future.result()
                work_key = _sanitize_work_key(title)
                work_results[work_key] = eng_results
                total_tokens += tokens
            except InterruptedError:
                raise
            except Exception as e:
                logger.error(f"Per-work execution failed for '{work_title}': {e}")
                errors.append(f"{work_title}: {e}")

    duration_ms = int((time.time() - start_time) * 1000)

    # Combine final outputs from all works
    final_parts = []
    for work_key, eng_results in work_results.items():
        for eng_key, pass_results in eng_results.items():
            if pass_results:
                final_parts.append(
                    f"## {work_key} ({eng_key})\n\n{pass_results[-1].content}"
                )
    final_output = "\n\n---\n\n".join(final_parts)

    status = PhaseStatus.COMPLETED if not errors else PhaseStatus.FAILED

    return PhaseResult(
        phase_number=phase_number,
        phase_name=phase_name,
        status=status,
        work_results=work_results,
        final_output=final_output,
        duration_ms=duration_ms,
        total_tokens=total_tokens,
        error="; ".join(errors) if errors else None,
    )


def _run_chapter_targeted_phase(
    workflow_phase: WorkflowPhase,
    plan_phase: PhaseExecutionSpec,
    job_id: str,
    document_ids: dict[str, str],
    upstream_context: str,
    cancellation_check: Optional[Callable[[], bool]],
    progress_callback: Optional[Callable[[str], None]],
    start_time: float,
) -> PhaseResult:
    """Run a phase that targets specific chapters for individual analysis.

    When a phase has chapter_targets and document_scope="chapter":
    1. Load whole-document text
    2. For each chapter target, extract chapter text
    3. Build input: whole-book summary (from upstream) + chapter text
    4. Run the chain/engine on this combined input
    5. Store results keyed by chapter_id
    """
    from src.executor.chapter_splitter import ChapterInfo, extract_chapter_text

    phase_number = plan_phase.phase_number
    phase_name = plan_phase.phase_name
    chapter_targets = plan_phase.chapter_targets or []

    logger.info(
        f"Phase {phase_number}: chapter-targeted execution with "
        f"{len(chapter_targets)} chapters"
    )

    # Cache full document texts by work_key (loaded on demand)
    _work_text_cache: dict[str, str] = {}

    def _get_work_text(wk: str) -> str:
        if wk not in _work_text_cache:
            if wk == "target":
                _work_text_cache[wk] = _get_target_document_text(
                    document_ids,
                    job_id=job_id,
                )
            else:
                _work_text_cache[wk] = _get_work_document_text(wk, document_ids)
        return _work_text_cache[wk]

    chapter_results: dict[str, dict[str, list[EngineCallResult]]] = {}
    total_tokens = 0
    errors: list[str] = []

    for ch_idx, ch_target in enumerate(chapter_targets):
        if cancellation_check and cancellation_check():
            raise InterruptedError(
                f"Cancelled before chapter {ch_target.chapter_id}"
            )

        if progress_callback:
            progress_callback(
                f"Analyzing chapter {ch_idx + 1} of {len(chapter_targets)}: "
                f"{ch_target.chapter_title or ch_target.chapter_id}"
            )

        try:
            # Strategy 1: Load from pre-uploaded chapter document
            # Key format: "chapter:{work_key}:{chapter_id}"
            work_key = getattr(ch_target, "work_key", "target")
            chapter_doc_key = f"chapter:{work_key}:{ch_target.chapter_id}"
            chapter_doc_id = document_ids.get(chapter_doc_key)
            if chapter_doc_id:
                chapter_text = get_document_text(chapter_doc_id)
                if chapter_text:
                    logger.info(
                        f"Loaded pre-uploaded chapter '{ch_target.chapter_id}' "
                        f"from document store ({len(chapter_text):,} chars)"
                    )
                else:
                    logger.warning(
                        f"Chapter doc {chapter_doc_id} exists but has no text, "
                        f"falling back to extraction"
                    )
                    chapter_text = None
            else:
                chapter_text = None

            # Strategy 2: Extract from full document using char offsets
            if chapter_text is None:
                full_text = _get_work_text(work_key)
                if ch_target.start_char is not None and ch_target.end_char is not None:
                    chapter_info = ChapterInfo(
                        chapter_id=ch_target.chapter_id,
                        chapter_title=ch_target.chapter_title,
                        start_char=ch_target.start_char,
                        end_char=ch_target.end_char,
                        char_count=ch_target.end_char - ch_target.start_char,
                    )
                    chapter_text = extract_chapter_text(full_text, chapter_info)
                else:
                    # Fallback: use the full document if no offsets and no pre-upload
                    logger.warning(
                        f"Chapter {ch_target.chapter_id} has no pre-uploaded document "
                        f"and no char offsets, using full document text"
                    )
                    chapter_text = full_text

            # Build combined input: summary context + chapter text
            combined_text = (
                f"# Whole-Book Summary (from upstream profiling)\n\n"
                f"{upstream_context}\n\n"
                f"---\n\n"
                f"# Chapter: {ch_target.chapter_title or ch_target.chapter_id}\n\n"
                f"{chapter_text}"
            )

            work_key = _sanitize_work_key(ch_target.chapter_id)

            effective_chain_key, effective_engine_key = _resolve_execution_target(
                workflow_phase.chain_key,
                workflow_phase.engine_key,
                plan_phase.chain_key,
                plan_phase.engine_key,
            )

            if effective_chain_key:
                result = run_chain(
                    chain_key=effective_chain_key,
                    document_text=combined_text,
                    job_id=job_id,
                    phase_number=phase_number,
                    work_key=work_key,
                    depth=plan_phase.depth,
                    upstream_context="",  # Already embedded in combined_text
                    context_emphasis=plan_phase.context_emphasis,
                    model_hint=plan_phase.model_hint,
                    requires_full_documents=False,
                    cancellation_check=cancellation_check,
                    progress_callback=progress_callback,
                )
            elif effective_engine_key:
                result = run_single_engine(
                    engine_key=effective_engine_key,
                    document_text=combined_text,
                    job_id=job_id,
                    phase_number=phase_number,
                    work_key=work_key,
                    depth=plan_phase.depth,
                    upstream_context="",
                    context_emphasis=plan_phase.context_emphasis,
                    model_hint=plan_phase.model_hint,
                    requires_full_documents=False,
                    cancellation_check=cancellation_check,
                    progress_callback=progress_callback,
                )
            else:
                raise ValueError(
                    f"Phase {phase_number} has no chain_key or engine_key"
                )

            chapter_results[work_key] = result["engine_results"]
            total_tokens += result["total_tokens"]

        except InterruptedError:
            raise
        except Exception as e:
            logger.error(
                f"Chapter-targeted execution failed for "
                f"'{ch_target.chapter_id}': {e}"
            )
            errors.append(f"{ch_target.chapter_id}: {e}")

    duration_ms = int((time.time() - start_time) * 1000)

    # Combine final outputs from all chapters
    final_parts = []
    for work_key, eng_results in chapter_results.items():
        for eng_key, pass_results in eng_results.items():
            if pass_results:
                final_parts.append(
                    f"## {work_key} ({eng_key})\n\n{pass_results[-1].content}"
                )
    final_output = "\n\n---\n\n".join(final_parts)

    status = PhaseStatus.COMPLETED if not errors else PhaseStatus.FAILED

    return PhaseResult(
        phase_number=phase_number,
        phase_name=phase_name,
        status=status,
        work_results=chapter_results,
        final_output=final_output,
        duration_ms=duration_ms,
        total_tokens=total_tokens,
        error="; ".join(errors) if errors else None,
    )


def _get_target_document_text(
    document_ids: dict[str, str],
    job_id: Optional[str] = None,
) -> str:
    """Get the target work's document text."""
    plan_data = None
    if job_id:
        try:
            job = get_job(job_id) or {}
            plan_data = job.get("plan_data") or {}
        except Exception as exc:
            logger.warning(
                f"Could not load plan_data for target resolution in job {job_id}: {exc}"
            )

    target_doc_id = resolve_target_doc_id(document_ids, plan_data)
    if target_doc_id:
        text = get_document_text(target_doc_id)
        if text:
            return text
    # If no target document, return a placeholder
    # (the plan should have ensured documents are uploaded)
    logger.warning("No target document found — using empty text")
    return "[No target document text provided]"


def _get_standard_phase_document_text(
    *,
    document_ids: dict[str, str],
    job_id: str,
    phase_number: float,
) -> str:
    """Resolve document text for standard phases, including AOI source-corpus phases."""
    plan_data = {}
    try:
        job = get_job(job_id) or {}
        plan_data = job.get("plan_data") or {}
        if plan_data.get("_type") == "request_snapshot":
            plan_data = plan_data.get("plan_request") or {}
    except Exception as exc:
        logger.warning(f"Could not load plan data for job {job_id}: {exc}")

    workflow_key = plan_data.get("workflow_key")
    if not is_aoi_workflow_key(workflow_key):
        return _get_target_document_text(document_ids, job_id=job_id)

    selected_source_thinker_id = plan_data.get("selected_source_thinker_id")
    selected_source_thinker_name = plan_data.get("selected_source_thinker_name") or "Selected source thinker"
    prior_works = plan_data.get("prior_works") or []
    source_blocks: list[str] = []
    for work in prior_works:
        if work.get("source_thinker_id") != selected_source_thinker_id:
            continue
        title = work.get("title") or "Source work"
        source_document_id = work.get("source_document_id")
        text = _get_work_document_text(title, document_ids)
        heading = f"# Source Work: {title}"
        if source_document_id:
            heading += f" [{source_document_id}]"
        source_blocks.append(f"{heading}\n\n{text}")
    source_corpus = (
        "\n\n---\n\n".join(source_blocks)
        if source_blocks
        else f"[No source corpus text provided for {selected_source_thinker_name}]"
    )
    target_text = _get_target_document_text(document_ids, job_id=job_id)
    target_title = _get_target_work_title(job_id)

    if phase_number == 1.0:
        return (
            f"# Selected Source Thinker: {selected_source_thinker_name}\n\n"
            f"{source_corpus}"
        )

    if phase_number == 3.0:
        return (
            f"# Subject Corpus: {target_title}\n\n{target_text}\n\n"
            f"---\n\n"
            f"# Selected Source Thinker: {selected_source_thinker_name}\n\n"
            f"{source_corpus}"
        )

    return target_text


def _get_target_work_title(job_id: str) -> str:
    """Resolve the target work title from the job plan."""
    try:
        job = get_job(job_id) or {}
        plan_data = job.get("plan_data") or {}
        target_work = plan_data.get("target_work") or {}
        return target_work.get("title") or "the target work"
    except Exception:
        logger.warning(f"Could not resolve target work title for job {job_id}")
        return "the target work"


def _get_work_document_text(
    work_title: str,
    document_ids: dict[str, str],
) -> str:
    """Get a prior work's document text."""
    doc_id = document_ids.get(work_title)
    if doc_id:
        text = get_document_text(doc_id)
        if text:
            return text
    logger.warning(f"No document found for prior work: {work_title}")
    return f"[No document text provided for: {work_title}]"


def _combine_document_texts(
    target_text: str,
    work_text: str,
    work_title: str,
    target_title: str,
    phase_number: float,
) -> str:
    """Combine target and work texts for per-work phases.

    Phase 1.5 (classification) needs both target and prior work.
    Phase 2.0 (scanning) primarily needs the prior work + target context.

    NOTE: This is the LEGACY path used when no distilled analysis is available.
    Milestone 5 introduced _combine_with_distilled_analysis() which should be
    preferred when upstream context from Phase 1.0 is available.
    """
    scope_contract = _build_per_work_scope_contract(
        target_title=target_title,
        work_title=work_title,
        phase_number=phase_number,
    )
    if phase_number == 1.5:
        # Classification: both texts needed equally
        return (
            f"{scope_contract}\n\n"
            f"# Target Work: {target_title}\n\n{target_text}\n\n"
            f"---\n\n"
            f"# Prior Work: {work_title}\n\n{work_text}"
        )
    elif phase_number == 2.0:
        # Scanning: prior work is primary, target is context
        return (
            f"{scope_contract}\n\n"
            f"# Prior Work: {work_title}\n\n{work_text}\n\n"
            f"---\n\n"
            f"# Target Work: {target_title} (for reference)\n\n{target_text}"
        )
    else:
        # Generic: both texts
        return (
            f"{scope_contract}\n\n"
            f"# Target Work: {target_title}\n\n{target_text}\n\n"
            f"---\n\n"
            f"# Prior Work: {work_title}\n\n{work_text}"
        )


def _combine_with_distilled_analysis(
    distilled_analysis: str,
    work_text: str,
    work_title: str,
    target_title: str,
    phase_number: float,
) -> str:
    """Combine distilled target analysis + prior work text for per-work phases.

    Milestone 5: Instead of sending TWO full book texts (target + prior work),
    we send the DISTILLED ANALYSIS from Phase 1.0 (typically ~100-150K chars of
    multi-engine analysis) + the full prior work text. This dramatically reduces
    token counts while giving the LLM more useful context.

    The distilled analysis comes from the context broker's assembly of all
    Phase 1.0 outputs (including supplementary chains if the orchestrator
    selected them).
    """
    scope_contract = _build_per_work_scope_contract(
        target_title=target_title,
        work_title=work_title,
        phase_number=phase_number,
    )
    if phase_number == 1.5:
        # Classification: distilled analysis of target + prior work text
        return (
            f"{scope_contract}\n\n"
            f"# Target Work Analysis: {target_title}\n"
            f"(distilled from multi-engine profiling)\n\n"
            f"{distilled_analysis}\n\n"
            f"---\n\n"
            f"# Prior Work: {work_title}\n\n{work_text}"
        )
    elif phase_number == 2.0:
        # Scanning: prior work is primary, distilled target analysis is context
        return (
            f"{scope_contract}\n\n"
            f"# Prior Work: {work_title}\n\n{work_text}\n\n"
            f"---\n\n"
            f"# Target Work Analysis: {target_title}\n"
            f"(distilled from multi-engine profiling)\n\n"
            f"{distilled_analysis}"
        )
    else:
        # Generic: distilled analysis + work text
        return (
            f"{scope_contract}\n\n"
            f"# Target Work Analysis: {target_title}\n"
            f"(distilled from multi-engine profiling)\n\n"
            f"{distilled_analysis}\n\n"
            f"---\n\n"
            f"# Prior Work: {work_title}\n\n{work_text}"
        )


def _build_per_work_scope_contract(
    target_title: str,
    work_title: str,
    phase_number: float,
) -> str:
    """Anchor per-work phases to the intended target/prior pair."""
    task = (
        "Classify the relationship between these exact two works."
        if phase_number == 1.5
        else "Analyze how this exact prior work bears on this exact target work."
    )
    return (
        "# Pair Scope Contract\n\n"
        f"- TARGET WORK: {target_title}\n"
        f"- PRIOR WORK: {work_title}\n"
        f"- TASK: {task}\n"
        "- RULE: If the prior work mentions additional earlier works, treat them as "
        "internal references inside the prior work, not as substitutes for the "
        "named prior work.\n"
        "- RULE: Do not silently reframe the pair as some other predecessor-successor "
        "relationship mentioned inside the documents."
    )


def _sanitize_work_key(title: str) -> str:
    """Convert a work title to a safe key string."""
    # Keep only alphanumeric, spaces, and hyphens, then normalize
    safe = "".join(
        c if c.isalnum() or c in " -" else "_"
        for c in title
    )
    return safe.strip().replace("  ", " ")[:100]

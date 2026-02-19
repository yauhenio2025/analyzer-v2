"""Sequential chain execution for the executor.

A chain is a sequence of engines that run one after another, each receiving
the previous engine's output as context. The chain runner:

1. Loads the chain definition (engine_keys, blend_mode)
2. For each engine in the chain:
   a. Loads the CapabilityEngineDefinition
   b. Composes prompts using the capability_composer
   c. Runs multi-pass execution (via operationalizations)
   d. Threads output as context to the next engine
3. Returns the final engine's output as the chain result

Plan overrides (depth, focus_dimensions) are applied per-engine.

Ported from The Critic's execute_chain() with plan-driven override support.
"""

import logging
import time
from typing import Any, Callable, Optional

from src.chains.registry import get_chain_registry
from src.engines.registry import get_engine_registry
from src.executor.context_broker import (
    assemble_chain_context,
    assemble_inner_pass_context,
)
from src.executor.engine_runner import run_engine_call
from src.executor.output_store import save_output
from src.executor.schemas import EngineCallResult
from src.stages.capability_composer import (
    compose_all_pass_prompts,
    compose_pass_prompt,
)

logger = logging.getLogger(__name__)


def run_chain(
    chain_key: str,
    document_text: str,
    *,
    job_id: str,
    phase_number: float,
    work_key: str = "",
    depth: str = "standard",
    engine_overrides: Optional[dict[str, dict]] = None,
    context_emphasis: Optional[str] = None,
    upstream_context: str = "",
    model_hint: Optional[str] = None,
    requires_full_documents: bool = False,
    cancellation_check: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """Execute a chain of engines sequentially.

    Args:
        chain_key: Chain definition key
        document_text: The document text to analyze
        job_id: Job ID for output persistence
        phase_number: Current phase number
        work_key: Work identifier (for per-work phases)
        depth: Default depth for all engines in the chain
        engine_overrides: Per-engine depth/focus overrides from the plan
        context_emphasis: Emphasis text to prepend to context
        upstream_context: Context from upstream phases
        model_hint: Default model hint for all engines
        requires_full_documents: Whether to use 1M context
        cancellation_check: Callable that returns True to cancel
        progress_callback: Callable for progress updates

    Returns:
        dict with keys: engine_results, final_output, total_tokens, duration_ms
    """
    start_time = time.time()
    chain_reg = get_chain_registry()
    engine_reg = get_engine_registry()

    chain = chain_reg.get(chain_key)
    if chain is None:
        raise ValueError(f"Chain not found: {chain_key}")

    logger.info(
        f"Starting chain '{chain_key}': {len(chain.engine_keys)} engines, "
        f"depth={depth}, work_key={work_key or 'N/A'}"
    )

    engine_results: dict[str, list[EngineCallResult]] = {}
    previous_engine_output: Optional[str] = None
    total_tokens = 0

    for engine_idx, engine_key in enumerate(chain.engine_keys):
        if cancellation_check and cancellation_check():
            raise InterruptedError(f"Chain '{chain_key}' cancelled before engine {engine_key}")

        if progress_callback:
            progress_callback(
                f"Engine {engine_idx + 1}/{len(chain.engine_keys)}: {engine_key}"
            )

        # Resolve per-engine overrides from the plan
        engine_depth = depth
        engine_focus_dims = None
        if engine_overrides and engine_key in engine_overrides:
            override = engine_overrides[engine_key]
            if isinstance(override, dict):
                engine_depth = override.get("depth", depth)
                engine_focus_dims = override.get("focus_dimensions")
            else:
                # It's an EngineExecutionSpec object
                engine_depth = getattr(override, "depth", depth)
                engine_focus_dims = getattr(override, "focus_dimensions", None)

        # Load capability engine definition
        cap_def = engine_reg.get_capability_definition(engine_key)
        if cap_def is None:
            logger.error(f"Engine not found: {engine_key}, skipping")
            continue

        # Run multi-pass execution for this engine
        pass_results = _run_engine_passes(
            cap_def=cap_def,
            document_text=document_text,
            depth=engine_depth,
            focus_dimensions=engine_focus_dims,
            previous_engine_output=previous_engine_output,
            upstream_context=upstream_context,
            context_emphasis=context_emphasis,
            engine_label=chain.engine_keys[engine_idx - 1] if engine_idx > 0 else None,
            job_id=job_id,
            phase_number=phase_number,
            work_key=work_key,
            model_hint=model_hint,
            requires_full_documents=requires_full_documents,
            cancellation_check=cancellation_check,
        )

        engine_results[engine_key] = pass_results

        # The last pass output becomes context for the next engine
        if pass_results:
            previous_engine_output = pass_results[-1].content
            total_tokens += sum(r.input_tokens + r.output_tokens for r in pass_results)

    duration_ms = int((time.time() - start_time) * 1000)
    final_output = previous_engine_output or ""

    logger.info(
        f"Chain '{chain_key}' completed: {len(engine_results)} engines, "
        f"{total_tokens:,} tokens, {duration_ms:,}ms"
    )

    return {
        "engine_results": engine_results,
        "final_output": final_output,
        "total_tokens": total_tokens,
        "duration_ms": duration_ms,
    }


def _run_engine_passes(
    cap_def: Any,
    document_text: str,
    depth: str,
    focus_dimensions: Optional[list[str]],
    previous_engine_output: Optional[str],
    upstream_context: str,
    context_emphasis: Optional[str],
    engine_label: Optional[str],
    job_id: str,
    phase_number: float,
    work_key: str,
    model_hint: Optional[str],
    requires_full_documents: bool,
    cancellation_check: Optional[Callable[[], bool]],
) -> list[EngineCallResult]:
    """Run all passes for a single engine using operationalization-driven prompts.

    Handles:
    - Multi-pass execution (discovery → architecture → integration etc.)
    - Inner-pass context threading (via consumes_from)
    - Incremental output persistence
    """
    # Get pass prompts from the capability composer
    # This checks the operationalization registry first, then falls back to inline passes
    pass_prompts = compose_all_pass_prompts(
        cap_def=cap_def,
        depth=depth,
        use_operationalizations=True,
    )

    if not pass_prompts:
        # No multi-pass definition — run a single whole-engine prompt
        logger.info(
            f"No pass definitions for {cap_def.engine_key} at depth={depth}, "
            f"running single whole-engine call"
        )
        return _run_single_engine_call(
            cap_def=cap_def,
            document_text=document_text,
            depth=depth,
            focus_dimensions=focus_dimensions,
            previous_engine_output=previous_engine_output,
            upstream_context=upstream_context,
            context_emphasis=context_emphasis,
            engine_label=engine_label,
            job_id=job_id,
            phase_number=phase_number,
            work_key=work_key,
            model_hint=model_hint,
            requires_full_documents=requires_full_documents,
            cancellation_check=cancellation_check,
        )

    # Multi-pass execution
    results: list[EngineCallResult] = []
    prior_pass_outputs: dict[int, str] = {}
    pass_stances: dict[int, str] = {}

    for pass_prompt in pass_prompts:
        if cancellation_check and cancellation_check():
            raise InterruptedError(
                f"Cancelled during {cap_def.engine_key} pass {pass_prompt.pass_number}"
            )

        # Build inner-pass context from consumed passes
        inner_context = assemble_inner_pass_context(
            prior_pass_outputs=prior_pass_outputs,
            consumes_from=pass_prompt.consumes_from,
            pass_stances=pass_stances,
        )

        # Build chain context from previous engine
        chain_context = ""
        if previous_engine_output:
            chain_context = assemble_chain_context(
                previous_engine_output=previous_engine_output,
                engine_label=engine_label or "prior engine",
            )

        # Compose the full prompt with actual shared context
        # Re-compose with the real shared context now available
        shared_context_parts = []
        if upstream_context:
            shared_context_parts.append(upstream_context)
        if context_emphasis:
            shared_context_parts.append(
                f"## Analytical Emphasis\n\n**{context_emphasis}**"
            )
        if chain_context:
            shared_context_parts.append(chain_context)
        if inner_context:
            shared_context_parts.append(inner_context)

        full_shared_context = "\n\n---\n\n".join(shared_context_parts) if shared_context_parts else None

        # Get the PassDefinition to re-compose with shared context
        from src.engines.schemas_v2 import PassDefinition
        pass_def = PassDefinition(
            pass_number=pass_prompt.pass_number,
            label=pass_prompt.pass_label,
            stance=pass_prompt.stance_key,
            description="",  # Will use the original prompt structure
            focus_dimensions=pass_prompt.focus_dimensions,
            consumes_from=pass_prompt.consumes_from,
        )

        recomposed = compose_pass_prompt(
            cap_def=cap_def,
            pass_def=pass_def,
            depth=depth,
            shared_context=full_shared_context,
        )

        system_prompt = recomposed.prompt

        # Build user message with document text
        user_message = document_text

        label = (
            f"Phase {phase_number} | {cap_def.engine_key} | "
            f"Pass {pass_prompt.pass_number} ({pass_prompt.pass_label})"
        )
        if work_key:
            label += f" | {work_key}"

        # Execute the LLM call
        result = run_engine_call(
            system_prompt=system_prompt,
            user_message=user_message,
            phase_number=phase_number,
            model_hint=model_hint,
            depth=depth,
            requires_full_documents=requires_full_documents,
            cancellation_check=cancellation_check,
            label=label,
        )

        # Build EngineCallResult
        engine_result = EngineCallResult(
            engine_key=cap_def.engine_key,
            pass_number=pass_prompt.pass_number,
            stance_key=pass_prompt.stance_key,
            content=result["content"],
            model_used=result["model_used"],
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            thinking_tokens=result["thinking_tokens"],
            duration_ms=result["duration_ms"],
            retries=result["retries"],
        )
        results.append(engine_result)

        # Track for inner-pass context threading
        prior_pass_outputs[pass_prompt.pass_number] = result["content"]
        pass_stances[pass_prompt.pass_number] = pass_prompt.stance_key

        # Persist incrementally
        save_output(
            job_id=job_id,
            phase_number=phase_number,
            engine_key=cap_def.engine_key,
            pass_number=pass_prompt.pass_number,
            content=result["content"],
            work_key=work_key,
            stance_key=pass_prompt.stance_key,
            role="extraction",
            model_used=result["model_used"],
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            parent_id=None,  # TODO: lineage tracking
        )

        logger.info(
            f"  Pass {pass_prompt.pass_number}/{len(pass_prompts)} "
            f"({pass_prompt.pass_label}): "
            f"{result['input_tokens']}+{result['output_tokens']} tokens, "
            f"{result['duration_ms']}ms"
        )

    return results


def _run_single_engine_call(
    cap_def: Any,
    document_text: str,
    depth: str,
    focus_dimensions: Optional[list[str]],
    previous_engine_output: Optional[str],
    upstream_context: str,
    context_emphasis: Optional[str],
    engine_label: Optional[str],
    job_id: str,
    phase_number: float,
    work_key: str,
    model_hint: Optional[str],
    requires_full_documents: bool,
    cancellation_check: Optional[Callable[[], bool]],
) -> list[EngineCallResult]:
    """Fallback: run a single whole-engine call (no multi-pass)."""
    from src.stages.capability_composer import compose_capability_prompt

    # Build shared context
    shared_context_parts = []
    if upstream_context:
        shared_context_parts.append(upstream_context)
    if context_emphasis:
        shared_context_parts.append(
            f"## Analytical Emphasis\n\n**{context_emphasis}**"
        )
    if previous_engine_output:
        chain_ctx = assemble_chain_context(
            previous_engine_output=previous_engine_output,
            engine_label=engine_label or "prior engine",
        )
        shared_context_parts.append(chain_ctx)

    full_shared = "\n\n---\n\n".join(shared_context_parts) if shared_context_parts else None

    cap_prompt = compose_capability_prompt(
        cap_def=cap_def,
        depth=depth,
        shared_context=full_shared,
        focus_dimensions=focus_dimensions,
    )

    label = f"Phase {phase_number} | {cap_def.engine_key}"
    if work_key:
        label += f" | {work_key}"

    result = run_engine_call(
        system_prompt=cap_prompt.prompt,
        user_message=document_text,
        phase_number=phase_number,
        model_hint=model_hint,
        depth=depth,
        requires_full_documents=requires_full_documents,
        cancellation_check=cancellation_check,
        label=label,
    )

    engine_result = EngineCallResult(
        engine_key=cap_def.engine_key,
        pass_number=1,
        stance_key="",
        content=result["content"],
        model_used=result["model_used"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        thinking_tokens=result["thinking_tokens"],
        duration_ms=result["duration_ms"],
        retries=result["retries"],
    )

    # Persist
    save_output(
        job_id=job_id,
        phase_number=phase_number,
        engine_key=cap_def.engine_key,
        pass_number=1,
        content=result["content"],
        work_key=work_key,
        role="extraction",
        model_used=result["model_used"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
    )

    return [engine_result]


def run_single_engine(
    engine_key: str,
    document_text: str,
    *,
    job_id: str,
    phase_number: float,
    work_key: str = "",
    depth: str = "standard",
    focus_dimensions: Optional[list[str]] = None,
    upstream_context: str = "",
    context_emphasis: Optional[str] = None,
    model_hint: Optional[str] = None,
    requires_full_documents: bool = False,
    cancellation_check: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """Execute a single engine (not part of a chain).

    Used for phases backed by a single engine_key instead of a chain_key.
    Handles multi-pass via operationalizations just like chain_runner does.

    Returns:
        dict with keys: engine_results, final_output, total_tokens, duration_ms
    """
    start_time = time.time()
    engine_reg = get_engine_registry()

    cap_def = engine_reg.get_capability_definition(engine_key)
    if cap_def is None:
        raise ValueError(f"Engine not found: {engine_key}")

    if progress_callback:
        progress_callback(f"Engine: {engine_key}")

    pass_results = _run_engine_passes(
        cap_def=cap_def,
        document_text=document_text,
        depth=depth,
        focus_dimensions=focus_dimensions,
        previous_engine_output=None,
        upstream_context=upstream_context,
        context_emphasis=context_emphasis,
        engine_label=None,
        job_id=job_id,
        phase_number=phase_number,
        work_key=work_key,
        model_hint=model_hint,
        requires_full_documents=requires_full_documents,
        cancellation_check=cancellation_check,
    )

    total_tokens = sum(r.input_tokens + r.output_tokens for r in pass_results)
    final_output = pass_results[-1].content if pass_results else ""
    duration_ms = int((time.time() - start_time) * 1000)

    return {
        "engine_results": {engine_key: pass_results},
        "final_output": final_output,
        "total_tokens": total_tokens,
        "duration_ms": duration_ms,
    }

"""Profiled AOI proof fixtures and source-corpus validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
THE_CRITIC_ROOT = PROJECT_ROOT.parent / "the-critic"


@dataclass(frozen=True)
class AOISourceDocumentProfile:
    """Canonical metadata for one AOI source document."""

    source_document_id: str
    title: str
    raw_input_path: Path | None
    extracted_output_path: Path
    source_order: int
    extraction_mode: str = "pre_extracted"
    page_range_hint: tuple[int, int] | None = None
    title_anchors: tuple[str, ...] = ()
    additional_anchors: tuple[str, ...] = ()
    title_aliases: tuple[str, ...] = ()
    minimum_characters: int = 1_000
    author: str | None = None
    year: int | None = None
    description: str = "AOI source corpus text for the selected thinker."


@dataclass(frozen=True)
class AOIFixtureProfile:
    """Named AOI proof profile for one bounded run."""

    profile_key: str
    selected_source_thinker_id: str
    selected_source_thinker_name: str
    source_documents: tuple[AOISourceDocumentProfile, ...]


SUBJECT_FILES: tuple[tuple[str, str, Path], ...] = (
    (
        "nlr_153",
        "Beyond Capitalism 1",
        THE_CRITIC_ROOT / "inputs" / "Aaron Benanav, Beyond Capitalism 1, NLR 153, May June 2025.md",
    ),
    (
        "nlr_154",
        "Beyond Capitalism 2",
        THE_CRITIC_ROOT / "inputs" / "Aaron Benanav, Beyond Capitalism 2, NLR 154, July August 2025.md",
    ),
    (
        "response",
        "Response to Benanav",
        THE_CRITIC_ROOT / "inputs" / "response to Benanav (1).md",
    ),
)

_ONEILL_EXTRACTED_ROOT = THE_CRITIC_ROOT / "analyzer" / "extracted" / "morozov-on-slobodian"
_NEURATH_RAW_ROOT = THE_CRITIC_ROOT / "others" / "influences" / "otto-neurath"
_NEURATH_EXTRACTED_ROOT = THE_CRITIC_ROOT / "analyzer" / "extracted" / "aoi" / "otto-neurath"

FIXTURE_PROFILES: dict[str, AOIFixtureProfile] = {
    "benanav_oneill": AOIFixtureProfile(
        profile_key="benanav_oneill",
        selected_source_thinker_id="john_oneill",
        selected_source_thinker_name="John O'Neill",
        source_documents=(
            AOISourceDocumentProfile(
                source_document_id="oneill_hayek_neurath",
                title="O'Neill on Hayek and Neurath",
                raw_input_path=None,
                extracted_output_path=_ONEILL_EXTRACTED_ROOT / "oneill_hayek_neurath.txt",
                source_order=1,
                extraction_mode="pre_extracted",
                title_anchors=("Hayek", "Neurath"),
                additional_anchors=("market", "planning"),
                title_aliases=("oneill_hayek_neurath",),
                minimum_characters=20_000,
                author="John O'Neill",
                description="Previously extracted AOI source text for the bounded O'Neill proof.",
            ),
        ),
    ),
    "benanav_neurath": AOIFixtureProfile(
        profile_key="benanav_neurath",
        selected_source_thinker_id="otto_neurath",
        selected_source_thinker_name="Otto Neurath",
        source_documents=(
            AOISourceDocumentProfile(
                source_document_id="through_war_economy_to_economy_in_kind",
                title="Through War Economy to Economy in Kind",
                raw_input_path=_NEURATH_RAW_ROOT / "Empiricism and Sociology - Otto Neurath - Vienna Circle Collection - 1973.pdf",
                extracted_output_path=_NEURATH_EXTRACTED_ROOT / "through_war_economy_to_economy_in_kind.txt",
                source_order=1,
                extraction_mode="page_range",
                page_range_hint=(138, 172),
                title_anchors=("Through War Economy to Economy in Kind",),
                additional_anchors=(
                    "The Theory of War Economy as a Separate Discipline",
                    "Utopia as a Social Engineer's Construction",
                ),
                title_aliases=("Durch die Kriegswirtschaft zur Naturalwirtschaft",),
                minimum_characters=40_000,
                author="Otto Neurath",
            ),
            AOISourceDocumentProfile(
                source_document_id="international_planning_for_freedom",
                title="International Planning for Freedom",
                raw_input_path=_NEURATH_RAW_ROOT / "Empiricism and Sociology - Otto Neurath - Vienna Circle Collection - 1973.pdf",
                extracted_output_path=_NEURATH_EXTRACTED_ROOT / "international_planning_for_freedom.txt",
                source_order=2,
                extraction_mode="page_range",
                page_range_hint=(437, 455),
                title_anchors=("International Planning for Freedom",),
                additional_anchors=(
                    "Planning Revolution",
                    "man does not live by bread alone",
                ),
                title_aliases=(
                    "INTERNA TIONAL PLANNING FOR FREEDOM",
                    "International Planning & Freedom",
                    "International Planning and Freedom",
                ),
                minimum_characters=20_000,
                author="Otto Neurath",
            ),
            AOISourceDocumentProfile(
                source_document_id="economic_plan_and_calculation_in_kind",
                title="Economic Plan and Calculation in Kind",
                raw_input_path=_NEURATH_RAW_ROOT / "Economic Writings Selections 1904-1945 - Otto Neurath - Vienna Circle Collection - 2004.pdf",
                extracted_output_path=_NEURATH_EXTRACTED_ROOT / "economic_plan_and_calculation_in_kind.txt",
                source_order=3,
                extraction_mode="page_range",
                page_range_hint=(411, 471),
                title_anchors=("Economic Plan and Calculation in Kind",),
                additional_anchors=(
                    "On the Socialist Order of Life",
                    "The study of economic efficiency and the economic plan",
                ),
                minimum_characters=80_000,
                author="Otto Neurath",
            ),
            AOISourceDocumentProfile(
                source_document_id="socialist_utility_calculation_and_capitalist_profit_calculation",
                title="Socialist Utility Calculation and Capitalist Profit Calculation",
                raw_input_path=_NEURATH_RAW_ROOT / "Economic Writings Selections 1904-1945 - Otto Neurath - Vienna Circle Collection - 2004.pdf",
                extracted_output_path=_NEURATH_EXTRACTED_ROOT / "socialist_utility_calculation_and_capitalist_profit_calculation.txt",
                source_order=4,
                extraction_mode="page_range",
                page_range_hint=(472, 480),
                title_anchors=("Socialist Utility Calculation and Capitalist Profit Calculation",),
                additional_anchors=(
                    "In a future society where class opposition has vanished",
                    "The Poverty of Philosophy",
                ),
                minimum_characters=10_000,
                author="Otto Neurath",
            ),
        ),
    ),
}


def list_fixture_profiles() -> list[str]:
    return sorted(FIXTURE_PROFILES)


def get_fixture_profile(profile_key: str) -> AOIFixtureProfile:
    try:
        return FIXTURE_PROFILES[profile_key]
    except KeyError as exc:
        available = ", ".join(list_fixture_profiles())
        raise KeyError(f"Unknown AOI fixture profile '{profile_key}'. Available: {available}") from exc


def iter_extracted_documents(profile: AOIFixtureProfile) -> Iterable[AOISourceDocumentProfile]:
    return sorted(profile.source_documents, key=lambda doc: doc.source_order)


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing AOI source fixture file: {path}")
    return path.read_text(encoding="utf-8")


def validate_extracted_text(profile_doc: AOISourceDocumentProfile, text: str) -> list[str]:
    errors: list[str] = []
    stripped = text.strip()
    if not stripped:
        return ["text is empty"]
    if len(stripped) < profile_doc.minimum_characters:
        errors.append(
            f"text is too short ({len(stripped)} chars < {profile_doc.minimum_characters})"
        )

    normalized_text = _normalize_for_matching(stripped)
    title_candidates = [profile_doc.title, *profile_doc.title_aliases, *profile_doc.title_anchors]
    if not any(_normalize_for_matching(candidate) in normalized_text for candidate in title_candidates):
        errors.append(
            f"text does not contain any configured title anchor for '{profile_doc.source_document_id}'"
        )
    if profile_doc.additional_anchors and not any(
        _normalize_for_matching(anchor) in normalized_text for anchor in profile_doc.additional_anchors
    ):
        errors.append(
            f"text does not contain any configured additional anchor for '{profile_doc.source_document_id}'"
        )
    return errors


def validate_extracted_file(profile_doc: AOISourceDocumentProfile) -> list[str]:
    if not profile_doc.extracted_output_path.exists():
        return [f"missing extracted file: {profile_doc.extracted_output_path}"]
    return validate_extracted_text(profile_doc, read_text(profile_doc.extracted_output_path))


def resolve_profile_source_document(
    *,
    thinker_id: Optional[str],
    source_document_id: Optional[str] = None,
    title: Optional[str] = None,
) -> AOISourceDocumentProfile | None:
    if not thinker_id:
        return None

    normalized_candidates = {
        candidate
        for candidate in (
            _normalize_for_matching(source_document_id) if source_document_id else None,
            _normalize_for_matching(title) if title else None,
        )
        if candidate
    }
    if not normalized_candidates:
        return None

    for profile in FIXTURE_PROFILES.values():
        if profile.selected_source_thinker_id != thinker_id:
            continue
        for doc in profile.source_documents:
            aliases = {
                _normalize_for_matching(doc.source_document_id),
                _normalize_for_matching(doc.title),
                *(_normalize_for_matching(alias) for alias in doc.title_aliases),
                *(_normalize_for_matching(anchor) for anchor in doc.title_anchors),
            }
            if normalized_candidates & aliases:
                return doc
    return None


def _normalize_for_matching(value: str) -> str:
    return " ".join(value.lower().replace("’", "'").split())

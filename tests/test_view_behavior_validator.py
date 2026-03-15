from types import SimpleNamespace

from src.presenter.view_behavior_validator import (
    CARD_GRID_RESIDUAL_RISK,
    CARD_GRID_SCOPE,
    validate_registered_card_grid_behavior_policies,
    _validate_card_grid_behavior,
)
from src.views.registry import get_view_registry


def _view(view_key: str, renderer_config: dict, renderer_type: str = "card_grid", status: str = "active"):
    return SimpleNamespace(
        view_key=view_key,
        renderer_type=renderer_type,
        renderer_config=renderer_config,
        status=status,
    )


def test_card_grid_behavior_validator_requires_explicit_expandable_boolean():
    issues = _validate_card_grid_behavior(_view("test_card_grid", {"columns": 2}))

    assert len(issues) == 1
    assert issues[0].view_key == "test_card_grid"
    assert issues[0].path == "renderer_config.expandable"


def test_card_grid_behavior_validator_requires_group_by_when_group_style_map_present():
    issues = _validate_card_grid_behavior(
        _view(
            "test_grouped",
            {
                "expandable": False,
                "group_style_map": "sin_type",
            },
        )
    )

    assert len(issues) == 1
    assert issues[0].path == "renderer_config.group_style_map"


def test_card_grid_behavior_validator_rejects_falsy_group_by_values():
    for group_by in (None, "", "   "):
        issues = _validate_card_grid_behavior(
            _view(
                f"test_grouped_{repr(group_by)}",
                {
                    "expandable": False,
                    "group_style_map": "sin_type",
                    "group_by": group_by,
                },
            )
        )

        assert len(issues) == 1
        assert issues[0].path == "renderer_config.group_style_map"


def test_card_grid_behavior_summary_counts_distinct_failing_views():
    failing_one = _validate_card_grid_behavior(
        _view(
            "failing_view",
            {
                "group_style_map": "sin_type",
            },
        )
    )
    failing_two = _validate_card_grid_behavior(_view("second_view", {"columns": 1}))

    issues = failing_one + failing_two
    invalid = len({issue.view_key for issue in issues})

    assert len(issues) == 3
    assert invalid == 2


def test_card_grid_behavior_validator_ignores_non_card_grid_views():
    summary = validate_registered_card_grid_behavior_policies()

    assert "genealogy_per_work_scan" not in {
        issue["view_key"]
        for issue in summary["issues"]
    }


def test_registered_card_grid_behavior_summary_is_raw_registry_scoped():
    summary = validate_registered_card_grid_behavior_policies()

    assert summary["scope"] == CARD_GRID_SCOPE
    assert summary["residual_risk"] == CARD_GRID_RESIDUAL_RISK


def test_all_active_card_grid_views_have_explicit_non_expandable_policy():
    expected = {
        "aoi_by_sin_type": False,
        "aoi_source_documents": False,
        "genealogy_cop_alternative_paths": False,
        "genealogy_cop_constraining_conditions": False,
        "genealogy_cop_enabling_conditions": False,
        "genealogy_cop_unacknowledged_debts": False,
        "genealogy_relationship_landscape": False,
        "genealogy_tactics": False,
        "lines_of_attack_extraction": False,
        "lines_of_attack_strategies": False,
    }

    views = {
        view.view_key: view
        for view in get_view_registry().list_all()
        if getattr(view, "status", "active") == "active" and view.renderer_type == "card_grid"
    }

    assert set(views) == set(expected)
    assert {
        key: views[key].renderer_config.get("expandable")
        for key in sorted(views)
    } == expected


def test_registered_card_grid_behavior_policies_are_valid_for_current_registry():
    summary = validate_registered_card_grid_behavior_policies()

    assert summary["total"] == 10
    assert summary["invalid"] == 0
    assert summary["valid"] == 10
    assert summary["issues"] == []

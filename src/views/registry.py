"""View registry — loads and serves view definitions from JSON files.

Follows the same pattern as ChainRegistry/WorkflowRegistry:
- JSON-per-file in definitions/ directory
- Lazy loading with _loaded guard
- In-memory dict keyed by view_key
- Global singleton via get_view_registry()
- CRUD with file persistence
- compose_tree() for building nested page layouts
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .schemas import (
    ComposedPageResponse,
    ComposedView,
    ViewDefinition,
    ViewSummary,
)

logger = logging.getLogger(__name__)


class ViewRegistry:
    """Registry of view definitions loaded from JSON files."""

    def __init__(self, definitions_dir: Optional[Path] = None):
        if definitions_dir is None:
            definitions_dir = Path(__file__).parent / "definitions"
        self.definitions_dir = definitions_dir
        self._views: dict[str, ViewDefinition] = {}
        self._file_map: dict[str, Path] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all view definitions from JSON files."""
        if self._loaded:
            return

        if not self.definitions_dir.exists():
            logger.warning(f"Views definitions directory not found: {self.definitions_dir}")
            self._loaded = True
            return

        for json_file in self.definitions_dir.glob("*.json"):
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                view = ViewDefinition.model_validate(data)
                self._views[view.view_key] = view
                self._file_map[view.view_key] = json_file
                logger.debug(f"Loaded view: {view.view_key}")
            except Exception as e:
                logger.error(f"Failed to load view from {json_file}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self._views)} view definitions")

    def get(self, view_key: str) -> Optional[ViewDefinition]:
        """Get a view definition by key."""
        self.load()
        return self._views.get(view_key)

    def list_all(self) -> list[ViewDefinition]:
        """List all view definitions."""
        self.load()
        return list(self._views.values())

    def list_summaries(
        self,
        app: Optional[str] = None,
        page: Optional[str] = None,
    ) -> list[ViewSummary]:
        """List view summaries with optional filters."""
        self.load()
        views = self._views.values()
        if app:
            views = [v for v in views if v.target_app == app]
        if page:
            views = [v for v in views if v.target_page == page]
        return [
            self._build_summary(v)
            for v in sorted(views, key=lambda v: v.position)
        ]

    @staticmethod
    def _build_summary(v: ViewDefinition) -> ViewSummary:
        """Build ViewSummary with structural hints from renderer_config."""
        rc = v.renderer_config or {}

        # Count sections
        sections = rc.get("sections", [])
        sections_count = len(sections) if isinstance(sections, list) else 0

        # Detect sub-renderers
        has_sub = bool(rc.get("section_renderers"))

        # Build config hints — short descriptive tags
        hints: list[str] = []
        if sections_count > 0:
            hints.append(f"{sections_count} sections")
        if has_sub:
            sr = rc.get("section_renderers", {})
            sub_types = set()
            for sr_val in sr.values():
                if isinstance(sr_val, dict):
                    if sr_val.get("renderer_type"):
                        sub_types.add(sr_val["renderer_type"])
                    for sub in (sr_val.get("sub_renderers") or {}).values():
                        if isinstance(sub, dict) and sub.get("renderer_type"):
                            sub_types.add(sub["renderer_type"])
            if sub_types:
                hints.append(f"sub: {', '.join(sorted(sub_types))}")
        if rc.get("cell_renderer"):
            hints.append(f"cell: {rc['cell_renderer']}")
        if rc.get("columns") and isinstance(rc["columns"], (int, float)):
            hints.append(f"{int(rc['columns'])} cols")
        elif rc.get("columns") and isinstance(rc["columns"], list):
            hints.append(f"{len(rc['columns'])} columns")
        if rc.get("group_by"):
            hints.append(f"grouped by {rc['group_by']}")
        if rc.get("sortable"):
            hints.append("sortable")
        if rc.get("expandable"):
            hints.append("expandable")
        if rc.get("layout"):
            hints.append(rc["layout"])
        if rc.get("syntax_highlight"):
            hints.append("syntax highlight")
        if rc.get("pass_selector"):
            hints.append("pass selector")

        return ViewSummary(
            view_key=v.view_key,
            view_name=v.view_name,
            description=v.description,
            target_app=v.target_app,
            target_page=v.target_page,
            renderer_type=v.renderer_type,
            presentation_stance=v.presentation_stance,
            position=v.position,
            parent_view_key=v.parent_view_key,
            visibility=v.visibility,
            status=v.status,
            sections_count=sections_count,
            has_sub_renderers=has_sub,
            config_hints=hints,
        )

    def list_keys(self) -> list[str]:
        """List all view keys."""
        self.load()
        return list(self._views.keys())

    def count(self) -> int:
        """Get total number of views."""
        self.load()
        return len(self._views)

    def for_workflow(self, workflow_key: str) -> list[ViewDefinition]:
        """Get all views that reference a given workflow."""
        self.load()
        return [
            v for v in self._views.values()
            if v.data_source.workflow_key == workflow_key
            or any(s.workflow_key == workflow_key for s in v.secondary_sources)
        ]

    def compose_tree(self, app: str, page: str) -> ComposedPageResponse:
        """Build a nested tree of views for a specific app/page.

        Returns top-level views sorted by position, with children
        nested under their parent_view_key. This is the primary
        consumer endpoint — fetch once, render the whole page.
        """
        self.load()

        # Filter to matching app/page, active views only
        page_views = [
            v for v in self._views.values()
            if v.target_app == app
            and v.target_page == page
            and v.status == "active"
        ]

        # Build lookup for nesting
        by_key: dict[str, ViewDefinition] = {v.view_key: v for v in page_views}

        # Build ComposedView objects
        composed: dict[str, ComposedView] = {}
        for v in page_views:
            composed[v.view_key] = ComposedView(
                view_key=v.view_key,
                view_name=v.view_name,
                description=v.description,
                renderer_type=v.renderer_type,
                renderer_config=v.renderer_config,
                data_source=v.data_source,
                secondary_sources=v.secondary_sources,
                transformation=v.transformation,
                presentation_stance=v.presentation_stance,
                position=v.position,
                visibility=v.visibility,
                tab_count_field=v.tab_count_field,
                audience_overrides=v.audience_overrides,
                children=[],
            )

        # Wire children to parents
        top_level: list[ComposedView] = []
        for v in page_views:
            cv = composed[v.view_key]
            if v.parent_view_key and v.parent_view_key in composed:
                composed[v.parent_view_key].children.append(cv)
            else:
                top_level.append(cv)

        # Sort everything by position
        top_level.sort(key=lambda x: x.position)
        for cv in composed.values():
            cv.children.sort(key=lambda x: x.position)

        return ComposedPageResponse(
            app=app,
            page=page,
            view_count=len(page_views),
            views=top_level,
        )

    def save(self, view_key: str, view: ViewDefinition) -> bool:
        """Save a view definition to JSON file."""
        self.load()

        json_file = self._file_map.get(
            view_key, self.definitions_dir / f"{view_key}.json"
        )

        try:
            self.definitions_dir.mkdir(parents=True, exist_ok=True)

            with open(json_file, "w") as f:
                json.dump(view.model_dump(), f, indent=2)
                f.write("\n")

            self._views[view_key] = view
            self._file_map[view_key] = json_file

            logger.info(f"Saved view: {view_key} -> {json_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save view {view_key}: {e}")
            return False

    def delete(self, view_key: str) -> bool:
        """Delete a view definition."""
        self.load()

        if view_key not in self._views:
            return False

        json_file = self._file_map.get(
            view_key, self.definitions_dir / f"{view_key}.json"
        )

        try:
            if json_file.exists():
                json_file.unlink()

            del self._views[view_key]
            self._file_map.pop(view_key, None)

            logger.info(f"Deleted view: {view_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete view {view_key}: {e}")
            return False

    def reload(self) -> None:
        """Force reload all definitions."""
        self._loaded = False
        self._views.clear()
        self._file_map.clear()
        self.load()


# Global registry instance
_registry: Optional[ViewRegistry] = None


def get_view_registry() -> ViewRegistry:
    """Get the global view registry instance."""
    global _registry
    if _registry is None:
        _registry = ViewRegistry()
        _registry.load()
    return _registry

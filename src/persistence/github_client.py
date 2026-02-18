"""GitHub persistence layer for committing definition changes back to the repository.

When users modify workflows/chains via the API (e.g., adding engines to phases),
those changes need to persist across Render redeploys. Since Render's filesystem
is ephemeral and we have no database, the git repo IS the source of truth.

This module commits file changes back to GitHub using the Git Data API,
enabling atomic multi-file commits. When the commit lands on master,
Render auto-deploys with the updated definitions.

Requires environment variables:
    GITHUB_TOKEN: Fine-grained PAT with contents:write scope
    GITHUB_REPO: owner/repo (e.g., yauhenio2025/analyzer-v2)

Gracefully degrades when credentials are not set (local dev).
"""

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Project root — used to convert absolute paths to repo-relative paths
_PROJECT_ROOT: Path = Path(__file__).parent.parent.parent


@dataclass
class CommitFile:
    """A file to include in a commit."""
    repo_path: str  # Path relative to repo root (e.g., "src/chains/definitions/foo.json")
    content: str    # File content as string


@dataclass
class CommitResult:
    """Result of a GitHub commit operation."""
    success: bool
    sha: Optional[str] = None
    message: str = ""
    url: Optional[str] = None


class GitHubPersistence:
    """Commits file changes to GitHub for persistence across deploys.

    Uses the Git Data API for atomic multi-file commits:
    1. Get current branch ref → commit SHA
    2. Get current commit → tree SHA
    3. Create blobs for each file
    4. Create new tree with updated blobs
    5. Create new commit pointing to new tree
    6. Update branch ref to new commit

    This ensures all files in a single operation are committed atomically —
    either all succeed or none do.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        repo: Optional[str] = None,
        branch: str = "master",
    ):
        self.token = token
        self.repo = repo
        self.branch = branch
        self.enabled = bool(token and repo)

        if self.enabled:
            self._client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )
            logger.info(
                f"GitHub persistence enabled for {repo} (branch: {branch})"
            )
        else:
            self._client = None
            if not token:
                logger.warning(
                    "GITHUB_TOKEN not set — changes will be ephemeral (lost on redeploy)"
                )
            if not repo:
                logger.warning(
                    "GITHUB_REPO not set — changes will be ephemeral (lost on redeploy)"
                )

    async def commit_files(
        self,
        files: list[CommitFile],
        message: str,
    ) -> CommitResult:
        """Commit multiple files atomically to the repository.

        Uses the Git Data API (trees/commits/refs) for atomic multi-file commits.

        Args:
            files: List of CommitFile objects with repo-relative paths and content
            message: Commit message

        Returns:
            CommitResult with success status, SHA, and any error message
        """
        if not self.enabled:
            logger.info(
                f"GitHub persistence disabled — skipping commit of "
                f"{len(files)} file(s): {message}"
            )
            return CommitResult(
                success=False,
                message="GitHub persistence not configured (no GITHUB_TOKEN/GITHUB_REPO)",
            )

        try:
            # Step 1: Get current branch ref
            ref_resp = await self._client.get(
                f"/repos/{self.repo}/git/ref/heads/{self.branch}"
            )
            ref_resp.raise_for_status()
            current_commit_sha = ref_resp.json()["object"]["sha"]

            # Step 2: Get current commit's tree
            commit_resp = await self._client.get(
                f"/repos/{self.repo}/git/commits/{current_commit_sha}"
            )
            commit_resp.raise_for_status()
            base_tree_sha = commit_resp.json()["tree"]["sha"]

            # Step 3: Create blobs for each file
            tree_items = []
            for f in files:
                blob_resp = await self._client.post(
                    f"/repos/{self.repo}/git/blobs",
                    json={
                        "content": f.content,
                        "encoding": "utf-8",
                    },
                )
                blob_resp.raise_for_status()
                blob_sha = blob_resp.json()["sha"]

                tree_items.append({
                    "path": f.repo_path,
                    "mode": "100644",  # regular file
                    "type": "blob",
                    "sha": blob_sha,
                })

            # Step 4: Create new tree
            tree_resp = await self._client.post(
                f"/repos/{self.repo}/git/trees",
                json={
                    "base_tree": base_tree_sha,
                    "tree": tree_items,
                },
            )
            tree_resp.raise_for_status()
            new_tree_sha = tree_resp.json()["sha"]

            # Step 5: Create new commit
            new_commit_resp = await self._client.post(
                f"/repos/{self.repo}/git/commits",
                json={
                    "message": message,
                    "tree": new_tree_sha,
                    "parents": [current_commit_sha],
                },
            )
            new_commit_resp.raise_for_status()
            new_commit_sha = new_commit_resp.json()["sha"]
            commit_url = new_commit_resp.json().get("html_url", "")

            # Step 6: Update branch ref
            ref_update_resp = await self._client.patch(
                f"/repos/{self.repo}/git/refs/heads/{self.branch}",
                json={"sha": new_commit_sha},
            )
            ref_update_resp.raise_for_status()

            file_list = ", ".join(f.repo_path for f in files)
            logger.info(
                f"Committed {len(files)} file(s) to GitHub: {file_list} "
                f"(SHA: {new_commit_sha[:8]})"
            )

            return CommitResult(
                success=True,
                sha=new_commit_sha,
                message=f"Committed {len(files)} file(s)",
                url=commit_url,
            )

        except httpx.HTTPStatusError as e:
            error_body = e.response.text[:500] if e.response else "no response body"
            logger.error(
                f"GitHub API error during commit: {e.response.status_code} — {error_body}"
            )
            return CommitResult(
                success=False,
                message=f"GitHub API error: {e.response.status_code} — {error_body}",
            )
        except httpx.HTTPError as e:
            logger.error(f"GitHub HTTP error during commit: {e}")
            return CommitResult(
                success=False,
                message=f"GitHub HTTP error: {e}",
            )
        except Exception as e:
            logger.error(f"Unexpected error during GitHub commit: {e}")
            return CommitResult(
                success=False,
                message=f"Unexpected error: {e}",
            )

    async def commit_file(
        self,
        repo_path: str,
        content: str,
        message: str,
    ) -> CommitResult:
        """Commit a single file. Convenience wrapper around commit_files."""
        return await self.commit_files(
            files=[CommitFile(repo_path=repo_path, content=content)],
            message=message,
        )

    @staticmethod
    def absolute_to_repo_path(absolute_path: Path) -> str:
        """Convert an absolute file path to a repo-relative path.

        Args:
            absolute_path: Absolute path like /home/user/projects/analyzer-v2/src/chains/definitions/foo.json

        Returns:
            Repo-relative path like src/chains/definitions/foo.json
        """
        try:
            return str(absolute_path.relative_to(_PROJECT_ROOT))
        except ValueError:
            # Path is not under project root — use the path as-is
            # This can happen in tests or unusual deployment setups
            logger.warning(
                f"Path {absolute_path} is not under project root {_PROJECT_ROOT}, "
                f"using filename only"
            )
            return str(absolute_path)

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()


# Singleton instance
_github: Optional[GitHubPersistence] = None


def get_github_persistence() -> GitHubPersistence:
    """Get or create the global GitHubPersistence instance."""
    global _github
    if _github is None:
        _github = GitHubPersistence(
            token=os.environ.get("GITHUB_TOKEN"),
            repo=os.environ.get("GITHUB_REPO"),
            branch=os.environ.get("GITHUB_BRANCH", "master"),
        )
    return _github

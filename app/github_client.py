"""GitHub REST API client for hydrating pull-request context, diffs, and linked issues."""

import re
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.config import Settings, settings
from app.logging_config import logger
from app.models import ChangedFile, HydratedPRContext, LinkedIssue


class GitHubClient:
    """Asynchronous client for interacting with the GitHub REST API v3."""

    # Regex to match GitHub linked issue keywords:
    # Fixes #12, Closes #12, Resolves #12, Fixed #12, Closed #12, Resolved #12
    # Also handles full URLs or repo-scoped references: owner/repo#12
    LINKED_ISSUE_REGEX = re.compile(
        r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+"
        r"(?:(?:https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/)|"
        r"(?:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#)|#)"
        r"(\d+)\b"
    )

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = "https://api.github.com",
        timeout: float = 20.0,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.token = token if token is not None else settings.GITHUB_TOKEN
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._external_client = client

    async def close(self) -> None:
        """Close external HTTP client if one was provided."""
        if self._external_client and not self._external_client.is_closed:
            await self._external_client.aclose()

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "PR-Chronicler-App",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def extract_linked_issue_numbers(self, text: Optional[str]) -> List[int]:
        """Extract unique issue numbers referenced in PR description or comments."""
        if not text:
            return []
        matches = self.LINKED_ISSUE_REGEX.findall(text)
        seen = set()
        unique_numbers: List[int] = []
        for num_str in matches:
            num = int(num_str)
            if num not in seen:
                seen.add(num)
                unique_numbers.append(num)
        return unique_numbers

    async def get_pr_files(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        pull_number: int,
    ) -> Tuple[List[ChangedFile], int]:
        """Fetch all files modified in the pull request with pagination.
        
        Returns:
            Tuple of (list of ChangedFile, total patch character count)
        """
        changed_files: List[ChangedFile] = []
        total_patch_chars = 0
        page = 1
        per_page = 100

        while True:
            endpoint = f"/repos/{owner}/{repo}/pulls/{pull_number}/files?per_page={per_page}&page={page}"
            full_url = f"{self.base_url}{endpoint}"

            try:
                response = await client.get(full_url, headers=self._get_headers())
                logger.info(
                    "GitHub API request: GET %s -> status %d",
                    endpoint,
                    response.status_code,
                )

                if response.status_code == 401:
                    logger.error("GitHub API 401 Unauthorized: Invalid or expired GITHUB_TOKEN")
                    break
                elif response.status_code in (403, 429):
                    rate_limit_rem = response.headers.get("x-ratelimit-remaining", "unknown")
                    logger.warning(
                        "GitHub API Rate Limited (status %d). Remaining quota: %s",
                        response.status_code,
                        rate_limit_rem,
                    )
                    break
                elif response.status_code == 404:
                    logger.warning("PR files not found: %s", endpoint)
                    break

                response.raise_for_status()
                data = response.json()

                if not data or not isinstance(data, list):
                    break

                for item in data:
                    patch = item.get("patch")
                    if patch:
                        total_patch_chars += len(patch)
                    changed_file = ChangedFile(
                        filename=item.get("filename", "unknown"),
                        status=item.get("status", "modified"),
                        additions=item.get("additions", 0),
                        deletions=item.get("deletions", 0),
                        changes=item.get("changes", 0),
                        patch=patch,
                    )
                    changed_files.append(changed_file)

                # If returned less than per_page, reached last page
                if len(data) < per_page:
                    break

                page += 1

            except httpx.TimeoutException as exc:
                logger.error("GitHub API timeout when requesting %s: %s", endpoint, exc)
                break
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "GitHub API HTTP status error for %s: %s (status %d)",
                    endpoint,
                    exc,
                    exc.response.status_code if exc.response else 0,
                )
                break
            except Exception as exc:
                logger.error("Unexpected error fetching PR files for %s: %s", endpoint, exc, exc_info=True)
                break

        return changed_files, total_patch_chars

    async def get_issue_details(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        issue_number: int,
    ) -> Optional[LinkedIssue]:
        """Fetch title and body of a linked issue."""
        endpoint = f"/repos/{owner}/{repo}/issues/{issue_number}"
        full_url = f"{self.base_url}{endpoint}"

        try:
            response = await client.get(full_url, headers=self._get_headers())
            logger.info("GitHub API request: GET %s -> status %d", endpoint, response.status_code)

            if response.status_code == 404:
                logger.info("Linked issue #%d not found in %s/%s (may be private or deleted)", issue_number, owner, repo)
                return None
            elif response.status_code in (401, 403, 429):
                logger.warning(
                    "GitHub API issue request status %d for %s. Skipping issue #%d",
                    response.status_code,
                    endpoint,
                    issue_number,
                )
                return None

            response.raise_for_status()
            data = response.json()
            return LinkedIssue(
                number=issue_number,
                title=data.get("title", f"Issue #{issue_number}"),
                body=data.get("body"),
                state=data.get("state", "closed"),
                html_url=data.get("html_url", f"https://github.com/{owner}/{repo}/issues/{issue_number}"),
            )
        except httpx.TimeoutException as exc:
            logger.error("Timeout fetching linked issue #%d: %s", issue_number, exc)
            return None
        except Exception as exc:
            logger.error("Error fetching linked issue #%d: %s", issue_number, exc)
            return None

    async def hydrate_pr(
        self,
        payload: Dict[str, Any],
        client: Optional[httpx.AsyncClient] = None,
    ) -> HydratedPRContext:
        """Fully hydrates pull request metadata, changed files, diffs, and linked issues."""
        pr_data = payload.get("pull_request") or {}
        repo_data = payload.get("repository") or {}

        repo_full_name = repo_data.get("full_name") or ""
        if "/" in repo_full_name:
            owner, repo_name = repo_full_name.split("/", 1)
        else:
            owner = repo_data.get("owner", {}).get("login", "")
            repo_name = repo_data.get("name", "")

        pr_number = pr_data.get("number") or payload.get("number") or 0
        pr_title = pr_data.get("title", "")
        pr_body = pr_data.get("body") or ""
        pr_author = pr_data.get("user", {}).get("login", "unknown")
        pr_url = pr_data.get("html_url", f"https://github.com/{owner}/{repo_name}/pull/{pr_number}")
        merged_at = pr_data.get("merged_at")
        merge_commit_sha = pr_data.get("merge_commit_sha")

        logger.info(
            "Hydrating PR context for %s/%s #%d ('%s')",
            owner,
            repo_name,
            pr_number,
            pr_title,
        )

        async def _run_hydration(active_client: httpx.AsyncClient) -> HydratedPRContext:
            # 1. Fetch changed files & diffs
            changed_files, total_chars = await self.get_pr_files(
                active_client, owner, repo_name, pr_number
            )

            # 2. Extract and fetch linked issues
            issue_numbers = self.extract_linked_issue_numbers(pr_body)
            linked_issues: List[LinkedIssue] = []
            for num in issue_numbers:
                issue = await self.get_issue_details(active_client, owner, repo_name, num)
                if issue:
                    linked_issues.append(issue)

            logger.info(
                "PR #%d hydrated successfully: %d files changed (%d diff chars), %d linked issues found",
                pr_number,
                len(changed_files),
                total_chars,
                len(linked_issues),
            )

            return HydratedPRContext(
                repo_owner=owner,
                repo_name=repo_name,
                pr_number=pr_number,
                title=pr_title,
                author=pr_author,
                body=pr_body,
                html_url=pr_url,
                merged_at=merged_at,
                merge_commit_sha=merge_commit_sha,
                files=changed_files,
                linked_issues=linked_issues,
                total_patch_char_count=total_chars,
            )

        if client:
            return await _run_hydration(client)
        elif self._external_client:
            return await _run_hydration(self._external_client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as new_client:
                return await _run_hydration(new_client)

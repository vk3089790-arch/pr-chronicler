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

    def parse_github_input(self, query: str, forced_type: Optional[str] = None) -> Tuple[str, str, Optional[str]]:
        """Parses user input into (mode, identifier1, identifier2).
        
        Returns:
            Tuple of:
            - mode: "user" or "repo"
            - identifier1: username (for "user") or owner (for "repo")
            - identifier2: None (for "user") or repo_name (for "repo")
        """
        clean = query.strip().rstrip("/")
        # Remove GitHub base URL if present
        clean = re.sub(r"^https?://(?:www\.)?github\.com/", "", clean, flags=re.IGNORECASE)
        # Remove leading @
        clean = clean.lstrip("@").strip()

        if forced_type == "user":
            parts = clean.split("/")
            return "user", parts[0], None
        elif forced_type == "repo":
            parts = clean.split("/")
            owner = parts[0] if parts else ""
            repo = parts[1] if len(parts) > 1 else ""
            return "repo", owner, repo

        # Auto-detect: if contains '/' and at least 2 parts, treat as repo
        parts = clean.split("/")
        if len(parts) >= 2 and parts[0] and parts[1]:
            return "repo", parts[0], parts[1]
        return "user", parts[0] if parts else "", None

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

    async def get_user_profile(
        self,
        username: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch public profile metadata for a GitHub user."""
        endpoint = f"/users/{username}"
        full_url = f"{self.base_url}{endpoint}"

        async def _fetch(c: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
            try:
                res = await c.get(full_url, headers=self._get_headers())
                if res.status_code == 404:
                    return None
                res.raise_for_status()
                return res.json()
            except Exception as exc:
                logger.error("Error fetching user profile for %s: %s", username, exc)
                return None

        if client:
            return await _fetch(client)
        elif self._external_client:
            return await _fetch(self._external_client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                return await _fetch(c)

    async def get_user_repos(
        self,
        username: str,
        sort: str = "updated",
        per_page: int = 30,
        page: int = 1,
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch public repositories for a GitHub user."""
        endpoint = f"/users/{username}/repos?sort={sort}&per_page={per_page}&page={page}"
        full_url = f"{self.base_url}{endpoint}"

        async def _fetch(c: httpx.AsyncClient) -> List[Dict[str, Any]]:
            try:
                res = await c.get(full_url, headers=self._get_headers())
                if res.status_code == 404:
                    return []
                res.raise_for_status()
                return res.json()
            except Exception as exc:
                logger.error("Error fetching repos for %s: %s", username, exc)
                return []

        if client:
            return await _fetch(client)
        elif self._external_client:
            return await _fetch(self._external_client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                return await _fetch(c)

    async def get_user_pull_requests(
        self,
        username: str,
        state: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """Fetch pull requests authored by a GitHub user via the Search API.
        
        Supports state: 'all', 'merged', 'open', 'closed'
        """
        query_parts = [f"author:{username}", "type:pr"]
        if state == "merged":
            query_parts.append("is:merged")
        elif state == "open":
            query_parts.append("is:open")
        elif state == "closed":
            query_parts.append("is:closed")
            query_parts.append("is:unmerged")

        q = "+".join(query_parts)
        endpoint = f"/search/issues?q={q}&page={page}&per_page={per_page}&sort=created&order=desc"
        full_url = f"{self.base_url}{endpoint}"

        async def _fetch(c: httpx.AsyncClient) -> Dict[str, Any]:
            try:
                res = await c.get(full_url, headers=self._get_headers())
                if res.status_code == 404:
                    return {"total_count": 0, "items": []}
                res.raise_for_status()
                data = res.json()
                return {
                    "total_count": data.get("total_count", 0),
                    "items": data.get("items", []),
                }
            except Exception as exc:
                logger.error("Error searching PRs for user %s: %s", username, exc)
                return {"total_count": 0, "items": []}

        if client:
            return await _fetch(client)
        elif self._external_client:
            return await _fetch(self._external_client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                return await _fetch(c)

    async def get_repo_details(
        self,
        owner: str,
        repo: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch repository metadata."""
        endpoint = f"/repos/{owner}/{repo}"
        full_url = f"{self.base_url}{endpoint}"

        async def _fetch(c: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
            try:
                res = await c.get(full_url, headers=self._get_headers())
                if res.status_code == 404:
                    return None
                res.raise_for_status()
                return res.json()
            except Exception as exc:
                logger.error("Error fetching repo %s/%s: %s", owner, repo, exc)
                return None

        if client:
            return await _fetch(client)
        elif self._external_client:
            return await _fetch(self._external_client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                return await _fetch(c)

    async def get_repo_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        page: int = 1,
        per_page: int = 30,
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch pull requests for a repository."""
        endpoint = f"/repos/{owner}/{repo}/pulls?state={state}&page={page}&per_page={per_page}"
        full_url = f"{self.base_url}{endpoint}"

        async def _fetch(c: httpx.AsyncClient) -> List[Dict[str, Any]]:
            try:
                res = await c.get(full_url, headers=self._get_headers())
                if res.status_code == 404:
                    return []
                res.raise_for_status()
                return res.json()
            except Exception as exc:
                logger.error("Error fetching repo PRs for %s/%s: %s", owner, repo, exc)
                return []

        if client:
            return await _fetch(client)
        elif self._external_client:
            return await _fetch(self._external_client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                return await _fetch(c)

    async def get_repo_contributors(
        self,
        owner: str,
        repo: str,
        page: int = 1,
        per_page: int = 30,
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch public contributors for a repository."""
        endpoint = f"/repos/{owner}/{repo}/contributors?page={page}&per_page={per_page}"
        full_url = f"{self.base_url}{endpoint}"

        async def _fetch(c: httpx.AsyncClient) -> List[Dict[str, Any]]:
            try:
                res = await c.get(full_url, headers=self._get_headers())
                if res.status_code == 404:
                    return []
                res.raise_for_status()
                return res.json()
            except Exception as exc:
                logger.error("Error fetching contributors for %s/%s: %s", owner, repo, exc)
                return []

        if client:
            return await _fetch(client)
        elif self._external_client:
            return await _fetch(self._external_client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                return await _fetch(c)

    async def get_pr_details(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch single pull request metadata."""
        endpoint = f"/repos/{owner}/{repo}/pulls/{pull_number}"
        full_url = f"{self.base_url}{endpoint}"

        async def _fetch(c: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
            try:
                res = await c.get(full_url, headers=self._get_headers())
                if res.status_code == 404:
                    return None
                res.raise_for_status()
                return res.json()
            except Exception as exc:
                logger.error("Error fetching PR #%d for %s/%s: %s", pull_number, owner, repo, exc)
                return None

        if client:
            return await _fetch(client)
        elif self._external_client:
            return await _fetch(self._external_client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                return await _fetch(c)

    async def hydrate_pr_by_number(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        client: Optional[httpx.AsyncClient] = None,
    ) -> HydratedPRContext:
        """Fetches PR data and hydrates full context (files, diffs, linked issues) on demand."""
        async def _hydrate(c: httpx.AsyncClient) -> HydratedPRContext:
            pr_data = await self.get_pr_details(owner, repo, pull_number, client=c)
            payload = {
                "pull_request": pr_data or {},
                "repository": {
                    "owner": {"login": owner},
                    "name": repo,
                    "full_name": f"{owner}/{repo}",
                },
                "number": pull_number,
            }
            return await self.hydrate_pr(payload, client=c)

        if client:
            return await _hydrate(client)
        elif self._external_client:
            return await _hydrate(self._external_client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                return await _hydrate(c)


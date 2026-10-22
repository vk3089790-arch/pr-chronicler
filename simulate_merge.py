#!/usr/bin/env python3
"""CLI utility to simulate GitHub pull request webhook events against the PR Chronicler server."""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Optional, Tuple

# Ensure project root is in sys.path so app imports work when run standalone
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings


def generate_hmac_signature(secret: str, payload_bytes: bytes) -> str:
    """Generate X-Hub-Signature-256 HMAC header value.
    
    Format: sha256=<hex_digest>
    """
    mac = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def prepare_webhook_request(
    url: str,
    payload: dict,
    delivery_id: str,
    secret: Optional[str] = None,
) -> Tuple[urllib.request.Request, bytes]:
    """Serializes payload to bytes once, signs it with HMAC-SHA256, and constructs urllib Request.
    
    Raises:
        ValueError: If webhook secret is missing or empty.
    """
    resolved_secret = (
        secret
        or getattr(settings, "GITHUB_WEBHOOK_SECRET", None)
        or os.getenv("WEBHOOK_SECRET")
    )

    if not resolved_secret:
        raise ValueError(
            "Webhook secret is required to sign requests. "
            "Provide --secret or configure GITHUB_WEBHOOK_SECRET / WEBHOOK_SECRET in .env."
        )

    # 1. Serialize the exact payload to JSON bytes once
    payload_bytes = json.dumps(payload, indent=2).encode("utf-8")

    # 2. Compute signature over the exact payload bytes
    sig = generate_hmac_signature(resolved_secret, payload_bytes)

    # 3. Preserve headers and set X-Hub-Signature-256
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "GitHub-Hookshot/simulated",
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": delivery_id,
        "X-Hub-Signature-256": sig,
    }

    req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
    return req, payload_bytes


def build_payload(scenario: str, custom_repo: str = None, custom_pr: int = None) -> dict:
    """Constructs mock GitHub pull request payloads for different scenarios."""
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if scenario == "merged":
        return {
            "action": "closed",
            "number": custom_pr or 42,
            "pull_request": {
                "id": 100042,
                "number": custom_pr or 42,
                "title": "feat: optimize connection pooling and cache invalidation",
                "body": "Implements LRU cache eviction and async connection recycling.\n\nFixes #12\nCloses #15",
                "state": "closed",
                "merged": True,
                "merged_at": now_iso,
                "merge_commit_sha": "a1b2c3d4e5f678901234567890abcdef12345678",
                "html_url": f"https://github.com/{custom_repo or 'octocat/Hello-World'}/pull/{custom_pr or 42}",
                "user": {"login": "alice-dev", "id": 101},
            },
            "repository": {
                "name": (custom_repo or "octocat/Hello-World").split("/")[-1],
                "full_name": custom_repo or "octocat/Hello-World",
                "owner": {"login": (custom_repo or "octocat/Hello-World").split("/")[0]},
            },
            "sender": {"login": "alice-dev"},
        }

    elif scenario == "unmerged":
        return {
            "action": "closed",
            "number": custom_pr or 43,
            "pull_request": {
                "id": 100043,
                "number": custom_pr or 43,
                "title": "refactor: abandoned experimental grpc rewrite",
                "body": "Closing because architectural benchmark did not show improvements.\n\nCloses #99",
                "state": "closed",
                "merged": False,
                "merged_at": None,
                "merge_commit_sha": None,
                "html_url": f"https://github.com/{custom_repo or 'octocat/Hello-World'}/pull/{custom_pr or 43}",
                "user": {"login": "bob-dev", "id": 102},
            },
            "repository": {
                "name": (custom_repo or "octocat/Hello-World").split("/")[-1],
                "full_name": custom_repo or "octocat/Hello-World",
                "owner": {"login": (custom_repo or "octocat/Hello-World").split("/")[0]},
            },
            "sender": {"login": "bob-dev"},
        }

    elif scenario == "opened":
        return {
            "action": "opened",
            "number": custom_pr or 44,
            "pull_request": {
                "id": 100044,
                "number": custom_pr or 44,
                "title": "WIP: draft implementation of rate limiting middleware",
                "body": "Initial draft for review. Work in progress.\nResolves #20",
                "state": "open",
                "merged": False,
                "merged_at": None,
                "html_url": f"https://github.com/{custom_repo or 'octocat/Hello-World'}/pull/{custom_pr or 44}",
                "user": {"login": "carol-dev", "id": 103},
            },
            "repository": {
                "name": (custom_repo or "octocat/Hello-World").split("/")[-1],
                "full_name": custom_repo or "octocat/Hello-World",
                "owner": {"login": (custom_repo or "octocat/Hello-World").split("/")[0]},
            },
            "sender": {"login": "carol-dev"},
        }

    elif scenario == "synchronize":
        return {
            "action": "synchronize",
            "number": custom_pr or 44,
            "pull_request": {
                "id": 100044,
                "number": custom_pr or 44,
                "title": "WIP: draft implementation of rate limiting middleware (updated)",
                "body": "Pushed updated commits.\nResolves #20",
                "state": "open",
                "merged": False,
                "merged_at": None,
                "html_url": f"https://github.com/{custom_repo or 'octocat/Hello-World'}/pull/{custom_pr or 44}",
                "user": {"login": "carol-dev", "id": 103},
            },
            "repository": {
                "name": (custom_repo or "octocat/Hello-World").split("/")[-1],
                "full_name": custom_repo or "octocat/Hello-World",
                "owner": {"login": (custom_repo or "octocat/Hello-World").split("/")[0]},
            },
            "sender": {"login": "carol-dev"},
        }

    elif scenario == "real-pr":
        # Historical verified public PR: pallets/flask #6168
        repo_target = custom_repo or "pallets/flask"
        pr_target = custom_pr or 6168
        return {
            "action": "closed",
            "number": pr_target,
            "pull_request": {
                "id": 182736450,
                "number": pr_target,
                "title": "drop support for Python 3.10",
                "body": "Drop Python 3.10 as it has reached EOL.\n\nFixes #6100",
                "state": "closed",
                "merged": True,
                "merged_at": "2026-10-07T13:56:06Z",
                "merge_commit_sha": "d5b306b9b3df38f8cf6226155694206e9389e6eb",
                "html_url": f"https://github.com/{repo_target}/pull/{pr_target}",
                "user": {"login": "davidism", "id": 165585},
            },
            "repository": {
                "name": repo_target.split("/")[-1],
                "full_name": repo_target,
                "owner": {"login": repo_target.split("/")[0]},
            },
            "sender": {"login": "davidism"},
        }
    else:
        raise ValueError(f"Unknown scenario: {scenario}")


def send_webhook(
    url: str,
    payload: dict,
    delivery_id: str,
    secret: Optional[str] = None,
    wait: bool = True,
) -> None:
    """Dispatches webhook HTTP request using standard library urllib."""
    try:
        req, _ = prepare_webhook_request(
            url=url,
            payload=payload,
            delivery_id=delivery_id,
            secret=secret,
        )
    except ValueError as exc:
        print(f"\n[CONFIGURATION ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\n=======================================================")
    print(f"[REQUEST] Target URL : {url}")
    print(f"[REQUEST] Delivery ID: {delivery_id}")
    print(f"[REQUEST] Action     : {payload.get('action')}")
    print(f"[REQUEST] PR Number  : #{payload.get('number')}")
    print(f"[REQUEST] PR Merged  : {payload.get('pull_request', {}).get('merged')}")
    print(f"[REQUEST] Signed     : Yes (HMAC SHA-256 enabled)")
    print(f"=======================================================")

    try:
        start = time.time()
        with urllib.request.urlopen(req, timeout=15) as response:
            status_code = response.getcode()
            response_body = response.read().decode("utf-8")
            elapsed = time.time() - start

            print(f"\n[RESPONSE] Status Code: {status_code} (took {elapsed:.2f}s)")
            parsed_json = {}
            try:
                parsed_json = json.loads(response_body)
                print(f"[RESPONSE] Body:\n{json.dumps(parsed_json, indent=2)}")
            except Exception:
                print(f"[RESPONSE] Body:\n{response_body}")

            # If accepted for background processing, poll delivery status
            if parsed_json.get("status") == "accepted" and wait:
                print("\n[ASYNC] Webhook accepted. Monitoring background pipeline status...")
                base_url = url.split("/webhook")[0]
                status_url = f"{base_url}/webhook/delivery/{delivery_id}"
                poll_start = time.time()
                while time.time() - poll_start < 45:
                    time.sleep(1.5)
                    try:
                        req_st = urllib.request.Request(status_url, headers={"User-Agent": "GitHub-Hookshot/simulated"})
                        with urllib.request.urlopen(req_st, timeout=5) as st_resp:
                            st_data = json.loads(st_resp.read().decode("utf-8"))
                            cur_status = st_data.get("status")
                            if cur_status in ("COMPLETED", "FAILED"):
                                print(f"\n[PIPELINE FINISHED] Delivery status: {cur_status} (after {time.time() - poll_start:.1f}s)")
                                print(f"[DETAILS]:\n{json.dumps(st_data, indent=2)}")
                                return
                            else:
                                print(f"  ... processing ({cur_status})", end="\r", flush=True)
                    except Exception:
                        pass
                print("\n[INFO] Background processing is still in progress.")

    except urllib.error.HTTPError as exc:
        print(f"\n[HTTP ERROR] Status: {exc.code}")
        err_body = exc.read().decode("utf-8", errors="replace")
        print(f"[HTTP ERROR] Body  : {err_body}")
    except urllib.error.URLError as exc:
        print(f"\n[NETWORK ERROR] Could not connect to {url}: {exc.reason}")
        print("Hint: Is the FastAPI server running? Start it with: python -m uvicorn app.main:app --reload")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Simulate GitHub pull request webhook deliveries against PR Chronicler."
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000/webhook/github",
        help="PR Chronicler webhook URL (default: http://localhost:8000/webhook/github)",
    )
    parser.add_argument(
        "--scenario",
        choices=["merged", "unmerged", "opened", "synchronize", "real-pr"],
        default="merged",
        help="Scenario to simulate: merged, unmerged, opened, synchronize, or real-pr",
    )
    parser.add_argument(
        "--secret",
        default=None,
        help="GitHub webhook HMAC secret (defaults to GITHUB_WEBHOOK_SECRET or WEBHOOK_SECRET from .env)",
    )
    parser.add_argument(
        "--delivery-id",
        default=None,
        help="Custom delivery UUID (useful for testing idempotency and duplicate retries)",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Custom repository full name (e.g. 'owner/repo')",
    )
    parser.add_argument(
        "--pr",
        type=int,
        default=None,
        help="Custom PR number",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Do not poll for background completion after webhook acknowledgment",
    )

    args = parser.parse_args()
    delivery_id = args.delivery_id or str(uuid.uuid4())
    payload = build_payload(args.scenario, custom_repo=args.repo, custom_pr=args.pr)

    send_webhook(
        url=args.url,
        payload=payload,
        delivery_id=delivery_id,
        secret=args.secret,
        wait=not args.no_wait,
    )


if __name__ == "__main__":
    main()

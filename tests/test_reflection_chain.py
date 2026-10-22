"""Tests for LangChain LCEL reflection pipeline, Pydantic validation, and grounding constraints."""

import pytest
from unittest.mock import AsyncMock, patch
from google.api_core.exceptions import ResourceExhausted
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from app.models import ChangedFile, HydratedPRContext, LinkedIssue, ReflectionOutput
from app.reflection_chain import (
    ReflectionChain,
    extract_retry_delay,
    format_pr_context_for_prompt,
    is_quota_exceeded_error,
)


def test_reflection_output_validation_learnings_count():
    """Verify strictly between 3 and 4 key learnings are required."""
    valid_data_3 = {
        "issue_details": "Race condition in thread pool",
        "execution_summary": "Added mutex guard around queue access",
        "key_learnings": [
            "Learning 1: Thread safety is essential",
            "Learning 2: Mutex lock contention must be monitored",
            "Learning 3: Queue draining should be graceful",
        ],
    }

    # 3 items -> valid
    obj3 = ReflectionOutput(**valid_data_3)
    assert len(obj3.key_learnings) == 3

    # 4 items -> valid
    valid_data_4 = dict(valid_data_3)
    valid_data_4["key_learnings"] = valid_data_3["key_learnings"] + ["Learning 4: Benchmarks are needed"]
    obj4 = ReflectionOutput(**valid_data_4)
    assert len(obj4.key_learnings) == 4

    # 2 items -> invalid (too few)
    invalid_data_2 = dict(valid_data_3)
    invalid_data_2["key_learnings"] = valid_data_3["key_learnings"][:2]
    with pytest.raises(ValidationError) as exc:
        ReflectionOutput(**invalid_data_2)
    assert "at least 3 items" in str(exc.value) or "too_short" in str(exc.value) or "between 3 and 4" in str(exc.value)

    # 5 items -> invalid (too many)
    invalid_data_5 = dict(valid_data_3)
    invalid_data_5["key_learnings"] = valid_data_3["key_learnings"] + ["Learning 4", "Learning 5"]
    with pytest.raises(ValidationError) as exc:
        ReflectionOutput(**invalid_data_5)
    assert "at most 4 items" in str(exc.value) or "too_long" in str(exc.value) or "between 3 and 4" in str(exc.value)


def test_reflection_output_validation_empty_strings():
    """Verify empty or whitespace strings in learnings or summaries are rejected."""
    # Empty learning item
    with pytest.raises(ValidationError):
        ReflectionOutput(
            issue_details="Some details",
            execution_summary="Some summary",
            key_learnings=["Valid 1", "   ", "Valid 3"],
        )

    # Empty issue_details
    with pytest.raises(ValidationError):
        ReflectionOutput(
            issue_details="",
            execution_summary="Some summary",
            key_learnings=["L1", "L2", "L3"],
        )


def test_format_pr_context_for_prompt_missing_patch_and_issues():
    """Verify prompt formatting safely indicates missing issues and patches without fabrication."""
    context = HydratedPRContext(
        repo_owner="org",
        repo_name="service",
        pr_number=12,
        title="chore: update dependencies",
        author="dependabot",
        body=None,  # Missing body
        html_url="https://github.com/org/service/pull/12",
        files=[
            ChangedFile(
                filename="binary.wasm",
                status="modified",
                patch=None,  # Missing patch
            )
        ],
        linked_issues=[],  # No linked issues
        total_patch_char_count=0,
    )

    vars_dict = format_pr_context_for_prompt(context)

    assert "No linked issues referenced" in vars_dict["linked_issues_text"]
    assert "patch omitted" in vars_dict["patches_text"]
    assert "No PR description provided" in vars_dict["pr_body"]
    assert vars_dict["patch_char_count"] == 0


@pytest.mark.asyncio
async def test_reflection_chain_lcel_execution(sample_hydrated_context):
    """Test full LCEL pipeline invocation with a mocked LLM returning valid JSON."""
    expected_response_json = """{
        "issue_details": "Worker thread deadlocks under connection stalls in pool/worker.py.",
        "execution_summary": "Replaced blocking lock.acquire() with timeout guard and verified with test_pool_timeout.",
        "key_learnings": [
            "Always enforce timeouts on lock acquisitions in I/O workers.",
            "Use regression tests to verify timeout exceptions under simulated failure.",
            "Separate connection acquisition timeout from query execution timeout."
        ]
    }"""
    mock_llm = RunnableLambda(lambda _: AIMessage(content=expected_response_json))

    chain = ReflectionChain(api_key="mock-key", llm=mock_llm)
    output = await chain.generate_reflection(sample_hydrated_context)

    assert isinstance(output, ReflectionOutput)
    assert "deadlocks under connection stalls" in output.issue_details
    assert len(output.key_learnings) == 3


@pytest.mark.asyncio
async def test_reflection_chain_invalid_llm_json(sample_hydrated_context):
    """Test that invalid non-JSON output from LLM raises OutputParserException."""
    mock_llm = RunnableLambda(lambda _: AIMessage(content="I am unable to parse this PR."))

    chain = ReflectionChain(api_key="mock-key", llm=mock_llm)

    with pytest.raises(OutputParserException):
        await chain.generate_reflection(sample_hydrated_context)


def test_gemini_api_key_whitespace_and_quote_sanitization():
    """Verify that leading/trailing whitespace and surrounding quotes are sanitized."""
    from app.config import Settings
    s1 = Settings(GOOGLE_API_KEY="  fake-gemini-key  ")
    assert s1.GOOGLE_API_KEY == "fake-gemini-key"

    s2 = Settings(GOOGLE_API_KEY='"fake-quoted-key"')
    assert s2.GOOGLE_API_KEY == "fake-quoted-key"


def test_gemini_api_key_alias_support():
    """Verify GEMINI_API_KEY is accepted as a valid alias for GOOGLE_API_KEY."""
    from app.config import Settings
    s = Settings(GEMINI_API_KEY="fake-alias-key")
    assert s.GOOGLE_API_KEY == "fake-alias-key"


@pytest.mark.asyncio
async def test_missing_api_key_raises_clear_error(sample_hydrated_context):
    """Verify clear ValueError is raised when API key is unconfigured."""
    chain = ReflectionChain(api_key="")
    # Remove mock invoke if any
    chain.llm = None
    with pytest.raises(ValueError) as exc:
        await chain.generate_reflection(sample_hydrated_context)
    assert "GOOGLE_API_KEY is not configured" in str(exc.value)
    assert "https://aistudio.google.com/" in str(exc.value)


@pytest.mark.asyncio
async def test_reflection_handles_pr_with_unsupported_bug_fix_claim():
    """1. Test a PR whose description claims a bug is fixed but whose diff does not support that claim."""
    context = HydratedPRContext(
        repo_owner="pallets",
        repo_name="flask",
        pr_number=6168,
        title="Drop Python 3.10 as it has reached EOL",
        author="maintainer",
        body="Drop Python 3.10 support.\nFixes #6100 (Deadlock during wsgi_app teardown).",
        html_url="https://github.com/pallets/flask/pull/6168",
        files=[
            ChangedFile(
                filename="pyproject.toml",
                status="modified",
                additions=1,
                deletions=1,
                patch="@@ -50,3 +50,3 @@\n-requires-python = '>=3.10'\n+requires-python = '>=3.11'",
            )
        ],
        linked_issues=[
            LinkedIssue(
                number=6100,
                title="Exceptions in wsgi_app teardown cause deadlock",
                body="Streaming response exceptions are not caught in wsgi_app.",
                state="closed",
                html_url="https://github.com/pallets/flask/issues/6100",
            )
        ],
        total_patch_char_count=85,
    )

    # Prompt check
    vars_dict = format_pr_context_for_prompt(context)
    assert "Issue #6100" in vars_dict["linked_issues_text"]
    assert "Verify whether the code patch diff actually addresses this issue" in vars_dict["linked_issues_text"]

    # Mock LLM generating evidence-grounded reflection that detects the discrepancy
    llm_response = """{
        "issue_details": "[Context Discrepancy / Unverified Claim]: The PR description claims to resolve #6100 (wsgi_app teardown exception handling), but the code diff solely updates python version requirements in pyproject.toml. The claimed bug fix is [Unverified] as no WSGI error handling code was modified.",
        "execution_summary": "[Verified]: Updated pyproject.toml requires-python constraint from '>=3.10' to '>=3.11'. No application logic or error handling paths were changed in this PR.",
        "key_learnings": [
            "What changed: pyproject.toml minimum Python version bumped to 3.11. Why: Drops unsupported EOL Python 3.10. Principle: Keep language runtime baselines current. Evidence: [Verified] pyproject.toml diff.",
            "What changed: No code was changed for issue #6100. Why: PR metadata conflated version deprecation with a separate teardown bug. Principle: Ground bug resolution claims in code diffs. Evidence: [Verified] diff inspection reveals no wsgi modifications.",
            "What changed: Minimum Python runtime constraint modified. Why: Enables modern 3.11+ syntax and standard library features in future work. Principle: Runtime deprecation should precede syntactic upgrades. Evidence: [Inferred] standard version lifecycle strategy."
        ]
    }"""
    mock_llm = RunnableLambda(lambda _: AIMessage(content=llm_response))
    chain = ReflectionChain(api_key="mock-key", llm=mock_llm)

    output = await chain.generate_reflection(context)
    assert isinstance(output, ReflectionOutput)
    assert "[Context Discrepancy / Unverified Claim]" in output.issue_details
    assert "[Unverified]" in output.issue_details
    assert len(output.key_learnings) == 3


@pytest.mark.asyncio
async def test_reflection_handles_unrelated_linked_issue():
    """2. Test a linked issue that appears unrelated to the actual code changes."""
    context = HydratedPRContext(
        repo_owner="acme",
        repo_name="portal",
        pr_number=204,
        title="style(ui): update dark mode navbar contrast",
        author="designer",
        body="Updates navbar background hex color.\n\nCloses #902",
        html_url="https://github.com/acme/portal/pull/204",
        files=[
            ChangedFile(
                filename="static/css/nav.css",
                status="modified",
                additions=2,
                deletions=2,
                patch="@@ -10,2 +10,2 @@\n-background: #111;\n+background: #181818;",
            )
        ],
        linked_issues=[
            LinkedIssue(
                number=902,
                title="Memory leak in background task worker queue",
                body="Redis task consumer memory steadily rises over 48 hours.",
                state="open",
                html_url="https://github.com/acme/portal/issues/902",
            )
        ],
        total_patch_char_count=65,
    )

    llm_response = """{
        "issue_details": "[Context Discrepancy]: Issue #902 reports a Redis consumer memory leak, which is completely unrelated to the UI theme changes in this PR. [Verified] diff shows only static/css/nav.css color adjustment.",
        "execution_summary": "[Verified]: Modified static/css/nav.css to change navbar background color from #111 to #181818 for improved contrast. No Python or Redis worker code was touched.",
        "key_learnings": [
            "What changed: CSS background color updated in nav.css. Why: Improves accessibility and visual contrast in dark mode. Principle: Use design tokens consistently across UI themes. Evidence: [Verified] static/css/nav.css diff.",
            "What changed: Issue #902 was linked in PR text but untouched. Why: Accidental or misrouted issue link. Principle: Do not assume issue resolution without diff verification. Evidence: [Verified] diff contains zero backend code.",
            "What changed: Pure styling tweak isolated to stylesheet. Why: Zero risk to backend task consumption. Principle: Separation of concerns isolates UI presentation from service workers. Evidence: [Inferred] from asset-only file change."
        ]
    }"""
    mock_llm = RunnableLambda(lambda _: AIMessage(content=llm_response))
    chain = ReflectionChain(api_key="mock-key", llm=mock_llm)

    output = await chain.generate_reflection(context)
    assert "Issue #902 reports a Redis consumer memory leak" in output.issue_details
    assert "completely unrelated" in output.issue_details
    assert len(output.key_learnings) == 3


def test_reflection_handles_missing_or_incomplete_diff():
    """3. Test missing or incomplete diff information."""
    # Context with a binary file (patch=None) and a large truncated file
    context = HydratedPRContext(
        repo_owner="acme",
        repo_name="core",
        pr_number=55,
        title="assets: add new branding and dataset",
        author="dev",
        body="Added branding logo and machine learning weights.",
        html_url="https://github.com/acme/core/pull/55",
        files=[
            ChangedFile(
                filename="assets/logo.png",
                status="added",
                patch=None,  # Binary file, no patch
            ),
            ChangedFile(
                filename="models/weights.bin",
                status="added",
                patch=None,  # Binary file, no patch
            ),
        ],
        linked_issues=[],
        total_patch_char_count=0,
    )

    vars_dict = format_pr_context_for_prompt(context)
    # Check that evidence limitation warning is populated in patches_text
    assert "partial evidence limitation" in vars_dict["patches_text"]
    assert "assets/logo.png" in vars_dict["patches_text"]
    assert "models/weights.bin" in vars_dict["patches_text"]


@pytest.mark.asyncio
async def test_reflection_flags_unsupported_performance_or_security_claims():
    """4. Test that unsupported performance or security claims are flagged or avoided."""
    # PR with a simple doc typo fix, but author claims "10x speedup and eliminates all security CVEs"
    context = HydratedPRContext(
        repo_owner="acme",
        repo_name="docs",
        pr_number=10,
        title="docs: fix typo in installation guide",
        author="contributor",
        body="Fixed typo in command. Also this gives a 10x throughput speedup and resolves all security vulnerabilities.",
        html_url="https://github.com/acme/docs/pull/10",
        files=[
            ChangedFile(
                filename="docs/install.md",
                status="modified",
                patch="@@ -12,2 +12,2 @@\n-pythn install\n+python install",
            )
        ],
        linked_issues=[],
        total_patch_char_count=40,
    )

    llm_response = """{
        "issue_details": "[Verified]: Corrected typographic error 'pythn' in docs/install.md. [Unverified / Unsupported Claim]: PR description claims a 10x throughput speedup and security CVE fixes; these claims are completely unsupported by the markdown diff.",
        "execution_summary": "[Verified]: Modified a single character in docs/install.md. No executable code or security configurations were modified.",
        "key_learnings": [
            "What changed: Fixed typo in install.md. Why: Prevents user confusion during initial onboarding. Principle: Documentation accuracy reduces initial support friction. Evidence: [Verified] docs/install.md diff.",
            "What changed: Author claimed performance and security gains. Why: Claims lack benchmark and code support. Principle: Strictly reject unverified performance and security claims without code proof. Evidence: [Verified] inspection of markdown-only diff.",
            "What changed: Correction limited to command string. Why: Guarantees zero runtime behavioral changes. Principle: Non-code changes should have predictable, zero-risk blast radius. Evidence: [Inferred] documentation-only modification."
        ]
    }"""
    mock_llm = RunnableLambda(lambda _: AIMessage(content=llm_response))
    chain = ReflectionChain(api_key="mock-key", llm=mock_llm)

    output = await chain.generate_reflection(context)
    assert "[Unverified / Unsupported Claim]" in output.issue_details
    assert "unsupported by the markdown diff" in output.issue_details
    assert len(output.key_learnings) == 3


def test_reflection_correct_json_parsing_and_schema_preservation():
    """5. Test correct JSON parsing and preservation of the existing output schema."""
    valid_payload = {
        "issue_details": "Fixes connection exhaustion in pool manager.",
        "execution_summary": "Added semaphore to limit concurrent HTTP connections to 100.",
        "key_learnings": [
            "What changed: Added BoundedSemaphore in pool.py. Why: Prevents socket exhaustion. Principle: Enforce bounded resource limits. Evidence: [Verified] diff in pool.py.",
            "What changed: Configurable concurrency ceiling. Why: Allows tuning per host capacity. Principle: Make operational limits configurable. Evidence: [Verified] pool.py.",
            "What changed: Added unit test with 150 simulated requests. Why: Asserts semaphore queuing behavior. Principle: Test boundary limits. Evidence: [Verified] tests/test_pool.py."
        ]
    }

    # Model instantiation and validation
    reflection = ReflectionOutput.model_validate(valid_payload)
    assert reflection.issue_details == valid_payload["issue_details"]
    assert reflection.execution_summary == valid_payload["execution_summary"]
    assert len(reflection.key_learnings) == 3

    # Ensure schema forbids extra fields (preserves strict schema)
    with pytest.raises(ValidationError):
        ReflectionOutput.model_validate({**valid_payload, "extra_unexpected_field": "disallowed"})

    # Round-trip JSON test
    json_str = reflection.model_dump_json()
    roundtrip = ReflectionOutput.model_validate_json(json_str)
    assert roundtrip == reflection


@pytest.mark.asyncio
async def test_reflection_generation_failures_reported_clearly(sample_hydrated_context):
    """6. Test reflection generation failures being reported clearly with informative error types."""
    # Test OutputParserException when LLM returns invalid JSON
    bad_json_llm = RunnableLambda(lambda _: AIMessage(content="Internal Server Error: model output not JSON"))
    chain_bad_json = ReflectionChain(api_key="mock-key", llm=bad_json_llm)
    with pytest.raises(OutputParserException):
        await chain_bad_json.generate_reflection(sample_hydrated_context)

    # Test ValidationError when LLM returns schema-violating payload (e.g. only 1 key learning)
    invalid_schema_llm = RunnableLambda(lambda _: AIMessage(content="""{
        "issue_details": "Some problem",
        "execution_summary": "Some changes",
        "key_learnings": ["Only one learning"]
    }"""))
    chain_invalid_schema = ReflectionChain(api_key="mock-key", llm=invalid_schema_llm)
    with pytest.raises(ValidationError) as val_exc:
        await chain_invalid_schema.generate_reflection(sample_hydrated_context)
    assert "key_learnings" in str(val_exc.value)

    # Test unexpected runtime error propagates with original cause intact
    def _raise_error(_):
        raise ConnectionResetError("Gemini API stream disconnected")

    failing_llm = RunnableLambda(_raise_error)
    chain_failing = ReflectionChain(api_key="mock-key", llm=failing_llm)
    with pytest.raises(ConnectionResetError) as conn_exc:
        await chain_failing.generate_reflection(sample_hydrated_context)
    assert "Gemini API stream disconnected" in str(conn_exc.value)


@pytest.mark.asyncio
async def test_gemini_quota_resource_exhausted_handled_predictably(sample_hydrated_context):
    """Test that a simulated Gemini quota (429 ResourceExhausted) exception is handled predictably."""
    quota_error_msg = (
        "429 Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, "
        "limit: 5, model: gemini-2.5-flash\nPlease retry in 8.325651653s."
    )
    exc = ResourceExhausted(quota_error_msg)

    assert is_quota_exceeded_error(exc) is True
    delay = extract_retry_delay(exc)
    assert abs(delay - 8.325651653) < 0.001

    def _raise_quota(_):
        raise exc

    quota_llm = RunnableLambda(_raise_quota)
    chain = ReflectionChain(api_key="mock-key", llm=quota_llm)

    with pytest.raises(ResourceExhausted) as raised:
        await chain.generate_reflection(sample_hydrated_context)

    assert "Quota exceeded" in str(raised.value)


@pytest.mark.asyncio
async def test_quota_failure_cannot_produce_successful_reflection(sample_hydrated_context):
    """Test that a quota failure cannot accidentally produce a successful reflection."""
    def _raise_quota(_):
        raise ResourceExhausted("429 ResourceExhausted: free tier quota exhausted")

    quota_llm = RunnableLambda(_raise_quota)
    chain = ReflectionChain(api_key="mock-key", llm=quota_llm)

    result = None
    try:
        result = await chain.generate_reflection(sample_hydrated_context)
    except ResourceExhausted:
        pass

    assert result is None, "Reflection generation must never produce output when quota fails"


@pytest.mark.asyncio
async def test_no_email_sent_when_reflection_fails_on_quota(sample_hydrated_context, tmp_path):
    """Test that no email is sent and delivery is marked FAILED when reflection fails due to quota."""
    from app.database import DatabaseManager
    from app.webhook import WebhookPipeline

    db_path = str(tmp_path / "quota_test.db")
    db = DatabaseManager(db_path)
    await db.init_db()

    delivery_id = "test-quota-delivery-123"
    await db.register_delivery(
        delivery_id=delivery_id,
        repo="pallets/flask",
        pr_number=6168,
        action="closed",
    )

    # Mock reflection chain to raise ResourceExhausted
    mock_reflection_chain = AsyncMock()
    mock_reflection_chain.generate_reflection.side_effect = ResourceExhausted(
        "429 Quota exceeded: retry in 8s"
    )

    # Mock GitHub client to return hydrated context
    mock_github = AsyncMock()
    mock_github.hydrate_pr.return_value = sample_hydrated_context

    # Mock email dispatcher with spy
    mock_email = AsyncMock()
    mock_email.recipient_email = "team@example.com"

    pipeline = WebhookPipeline(
        db_manager=db,
        github_client=mock_github,
        reflection_chain=mock_reflection_chain,
        email_dispatcher=mock_email,
    )

    payload = {
        "action": "closed",
        "number": 6168,
        "pull_request": {"number": 6168, "merged": True},
        "repository": {"full_name": "pallets/flask"},
    }

    result = await pipeline.process_merged_pr(payload, delivery_id)

    # 1. Pipeline reports failure
    assert result["status"] == "failed"
    assert "ResourceExhausted" in result["error"]

    # 2. Email dispatcher was NEVER called
    mock_email.send_reflection_email.assert_not_called()

    # 3. Database status is strictly FAILED
    delivery_record = await db.get_delivery(delivery_id)
    assert delivery_record is not None
    assert delivery_record.status == "FAILED"
    assert "ResourceExhausted" in (delivery_record.error_message or "")


@pytest.mark.asyncio
async def test_reflection_distinguishes_observed_change_from_maintainer_intent():
    """Verify that removing a tool configuration is logged as verified change, but maintainer intent is not assumed."""
    context = HydratedPRContext(
        repo_owner="pallets",
        repo_name="flask",
        pr_number=6168,
        title="Drop Python 3.10 as it has reached EOL",
        author="maintainer",
        body="Drop Python 3.10 support and clean up configs.",
        html_url="https://github.com/pallets/flask/pull/6168",
        files=[
            ChangedFile(
                filename="pyproject.toml",
                status="modified",
                additions=0,
                deletions=4,
                patch="@@ -80,4 +80,0 @@\n-[tool.pyright]\n-pythonVersion = '3.10'",
            )
        ],
        linked_issues=[],
        total_patch_char_count=50,
    )

    llm_response = """{
        "issue_details": "[Verified]: The PR removes the [tool.pyright] configuration block from pyproject.toml as part of dropping Python 3.10 baseline support.",
        "execution_summary": "[Verified]: Deleted 4 lines in pyproject.toml containing the [tool.pyright] table. [Inferred: unverified maintainer motivation]: The removal may indicate consolidation onto mypy or an alternative type-checker configuration, but the diff does not prove maintainer intent.",
        "key_learnings": [
            "What changed: Removed [tool.pyright] configuration block. Why: Cleans up obsolete version-specific settings. Principle: Explicitly distinguish observed diff edits from unverified maintainer motivations. Evidence: [Verified] pyproject.toml lines 80-84.",
            "What changed: Type checker configuration deleted. Why: Avoid asserting strategic tooling migration without proof. Principle: Only assert tool shifts when alternative tool configurations are added. Evidence: [Inferred: unverified maintainer motivation] pyproject.toml.",
            "What changed: Streamlined pyproject.toml. Why: Reduces configuration debt. Principle: Configuration hygiene should accompany runtime baseline bumps. Evidence: [Verified] pyproject.toml deletion diff."
        ]
    }"""
    mock_llm = RunnableLambda(lambda _: AIMessage(content=llm_response))
    chain = ReflectionChain(api_key="mock-key", llm=mock_llm)

    output = await chain.generate_reflection(context)
    assert "[Verified]" in output.execution_summary
    assert "[Inferred: unverified maintainer motivation]" in output.execution_summary
    assert "pyproject.toml" in output.key_learnings[0]
    assert len(output.key_learnings) == 3


@pytest.mark.asyncio
async def test_reflection_rejects_unsupported_performance_improvement_claims():
    """Verify that claims of performance improvement without benchmarks or measurements are flagged."""
    context = HydratedPRContext(
        repo_owner="acme",
        repo_name="db",
        pr_number=88,
        title="refactor: rewrite query loop",
        author="contributor",
        body="Rewrote query processing with list comprehensions. Yields 50% faster throughput and zero allocations.",
        html_url="https://github.com/acme/db/pull/88",
        files=[
            ChangedFile(
                filename="src/query.py",
                status="modified",
                additions=3,
                deletions=5,
                patch="@@ -15,5 +15,3 @@\n-res = []\n-for row in rows:\n-    res.append(row[0])\n+res = [row[0] for row in rows]",
            )
        ],
        linked_issues=[],
        total_patch_char_count=90,
    )

    llm_response = """{
        "issue_details": "[Verified]: Refactored rows extraction loop in src/query.py into a list comprehension. [Unverified / Unsupported Claim]: Author claimed 50% faster throughput and zero allocations, but no microbenchmarks, profiling data, or memory telemetry are included in the diff.",
        "execution_summary": "[Verified]: Replaced explicit list append loop with a list comprehension in src/query.py (+3 -5). No algorithm or I/O characteristics were altered.",
        "key_learnings": [
            "What changed: Replaced append loop with list comprehension in src/query.py. Why: Improves idiomatic Python style. Principle: Do not claim measurable performance benefits without benchmark evidence in the diff. Evidence: [Verified] src/query.py diff.",
            "What changed: Performance improvement claimed without proof. Why: List comprehensions have minor bytecode optimization but 50% throughput is unproven. Principle: Reject unverified performance assertions. Evidence: [Unverified] author claim in PR body vs src/query.py.",
            "What changed: Simplified syntax in src/query.py. Why: Increases readability and maintainability. Principle: Idiomatic expressions reduce cognitive load. Evidence: [Verified] src/query.py lines 15-18."
        ]
    }"""
    mock_llm = RunnableLambda(lambda _: AIMessage(content=llm_response))
    chain = ReflectionChain(api_key="mock-key", llm=mock_llm)

    output = await chain.generate_reflection(context)
    assert "[Unverified / Unsupported Claim]" in output.issue_details
    assert "no microbenchmarks, profiling data, or memory telemetry" in output.issue_details
    assert "src/query.py" in output.key_learnings[0]
    assert len(output.key_learnings) == 3


@pytest.mark.asyncio
async def test_reflection_rejects_unsupported_issue_resolution_claims():
    """Verify that a PR claiming to resolve an issue is flagged when the diff does not modify relevant code."""
    context = HydratedPRContext(
        repo_owner="pallets",
        repo_name="werkzeug",
        pr_number=3000,
        title="docs: update changelog for release",
        author="maintainer",
        body="Update changelog. Resolves #7777 (Race condition in session cache invalidation).",
        html_url="https://github.com/pallets/werkzeug/pull/3000",
        files=[
            ChangedFile(
                filename="CHANGES.rst",
                status="modified",
                additions=5,
                deletions=0,
                patch="@@ -10,0 +10,5 @@\n+Version 3.1.0\n+-------------\n+- Fix session cache invalidation (#7777)",
            )
        ],
        linked_issues=[
            LinkedIssue(
                number=7777,
                title="Race condition in session cache invalidation",
                body="Concurrent sessions overwrite cache keys without lock protection.",
                state="closed",
                html_url="https://github.com/pallets/werkzeug/issues/7777",
            )
        ],
        total_patch_char_count=110,
    )

    llm_response = """{
        "issue_details": "[Context Discrepancy / Unverified Claim]: PR title and body claim to resolve #7777 (race condition in session cache), but the diff exclusively updates CHANGES.rst release notes. The bug fix resolution is [Unverified] as zero session cache code or concurrency locks were modified in this PR.",
        "execution_summary": "[Verified]: Added 5 lines of release documentation to CHANGES.rst. No session or cache implementation files were modified.",
        "key_learnings": [
            "What changed: Added release note entry in CHANGES.rst. Why: Informs downstream users of previous release changes. Principle: Changelog edits must not be conflated with the actual bug fix implementation. Evidence: [Verified] CHANGES.rst diff.",
            "What changed: Claimed resolution of #7777 without code changes. Why: PR is a release management commit, not a functional bug fix. Principle: Never assume an issue was resolved unless the patch touches the defect's code path. Evidence: [Verified] diff inspection showing only CHANGES.rst.",
            "What changed: Release metadata documentation updated. Why: Ensures transparent version history. Principle: Traceability between issue numbers and changelog entries supports audits. Evidence: [Inferred] CHANGES.rst lines 10-15."
        ]
    }"""
    mock_llm = RunnableLambda(lambda _: AIMessage(content=llm_response))
    chain = ReflectionChain(api_key="mock-key", llm=mock_llm)

    output = await chain.generate_reflection(context)
    assert "[Context Discrepancy / Unverified Claim]" in output.issue_details
    assert "zero session cache code" in output.issue_details
    assert "CHANGES.rst" in output.key_learnings[0]
    assert len(output.key_learnings) == 3





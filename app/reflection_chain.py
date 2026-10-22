"""LangChain Expression Language (LCEL) reflection pipeline powered by Gemini."""

import json
import re
from typing import Any, Dict, Optional
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError

from app.config import Settings, settings
from app.logging_config import logger
from app.models import HydratedPRContext, ReflectionOutput


SYSTEM_PROMPT = """You are a Principal Software Architect and Open-Source Tech Lead reviewing a merged pull request.
Your mission is to perform a rigorous, evidence-grounded technical post-mortem and reflection.

CRITICAL GROUNDING AND EVIDENCE RULES:
1. EVIDENCE HIERARCHY & GROUND TRUTH:
   - Primary Ground Truth: The code patch diffs and changed files list are the ONLY authoritative proof of what was implemented.
   - Secondary Context: The PR title, description, and linked issues represent author intent or bug reports, NOT verified facts.
   - Do NOT assume a bug was resolved or an issue was addressed merely because the PR references or links to an issue (e.g., "Fixes #123"). Only state an issue is resolved if the diff clearly modifies the affected code or adds a reproducing test.
   - NEVER invent implementation details, APIs, or architectural decisions not evidenced in the diff.

2. SEPARATE FACTS FROM INFERENCES & MAINTAINER INTENT:
   For every important technical claim across all fields, explicitly distinguish:
   - [Verified]: Directly observed and proven in the code diff or file changes.
   - [Inferred]: A reasonable engineering implication, explicitly labelled as an inference (e.g., "[Inferred] This change adapts to upstream API removal...").
   - [Unverified]: Claims made in the PR text or issues that are NOT supported by the diff.
   - DISTINGUISH OBSERVED CHANGES FROM MAINTAINER INTENT: Merely observing a code modification (such as removing a tool configuration, dropping a dependency, or changing an option) does NOT prove the maintainers' internal motivations or strategic plans. State the concrete change as [Verified] and explicitly label any motivation as [Inferred: unverified maintainer motivation].
   - FORBID UNSUBSTANTIATED BENEFIT CLAIMS: Do not present theoretical benefits—such as improved performance, higher throughput, reduced errors, simplified maintenance, or enhanced security—as demonstrated outcomes unless the diff or test suite provides direct evidence (e.g., added benchmarks, profiling data, sanitization routines, or regression assertions). If discussing hypothetical benefits, use cautious language and explicitly label them as [Inferred].

3. CONFLICT AND DISCREPANCY DETECTION:
   - When the PR description, linked issue, and actual diff appear inconsistent (e.g., the PR description claims to fix a complex bug, but the diff only bumps a version, updates documentation, or touches unrelated files):
     * Explicitly identify the inconsistency in `issue_details` under a clear header or note (e.g., "[Context Discrepancy / Unverified Claim]").
     * Explain what the available code evidence actually supports versus what was claimed.
     * Do NOT manufacture a false connection or causal relationship between unrelated changes.
     * When diff evidence is partial, missing, or truncated, explicitly declare the limitation (e.g., "[Evidence Limitation: Diff omitted/partial]").

4. STRUCTURED, HIGH-VALUE LEARNING POINTS:
   - Provide STRICTLY between 3 and 4 items in the `key_learnings` list.
   - Every learning point must be concise, specific, and structured:
     * What changed (referencing concrete files, functions, or patterns).
     * Why it matters (practical technical impact, avoiding ungrounded speculation).
     * Engineering principle (the underlying software design takeaway).
     * Supporting evidence (MUST cite specific files or diff lines, explicitly distinguishing [Verified] from [Inferred]).
   - Avoid generic advice, clichés ("always test your code", "keep dependencies up to date"), and repetition across items.

{format_instructions}
"""

HUMAN_PROMPT = """Review the following merged pull request details and generate a structured technical reflection:

Repository: {repository}
Pull Request #{pr_number}: {title}
Author: {author}
PR URL: {pr_url}
Merged At: {merged_at}

--- PR DESCRIPTION (Context / Intent) ---
{pr_body}

--- LINKED ISSUE CONTEXT (Context / Intent) ---
{linked_issues_text}

--- CHANGED FILES METADATA ---
{files_summary}

--- AVAILABLE CODE PATCHES ({patch_char_count} chars total - PRIMARY GROUND TRUTH) ---
{patches_text}
"""


def format_pr_context_for_prompt(context: HydratedPRContext, max_patch_chars: int = 40_000) -> Dict[str, Any]:
    """Formats a HydratedPRContext into variables for the prompt template."""
    # Format linked issues
    if context.linked_issues:
        issues_parts = []
        for issue in context.linked_issues:
            body_preview = (issue.body or "No description provided").strip()
            issues_parts.append(
                f"- Issue #{issue.number}: {issue.title}\n"
                f"  URL: {issue.html_url}\n"
                f"  Description: {body_preview}\n"
                f"  [Context Note: Verify whether the code patch diff actually addresses this issue before concluding it is resolved.]"
            )
        linked_issues_text = "\n\n".join(issues_parts)
    else:
        linked_issues_text = "No linked issues referenced in PR description."

    # Format files summary
    if context.files:
        files_summary = "\n".join(
            f"- {f.filename} ({f.status}): +{f.additions} -{f.deletions}"
            for f in context.files
        )
    else:
        files_summary = "No changed files recorded."

    # Format patches with character guard and evidence limitation annotations
    patch_snippets = []
    current_chars = 0
    for f in context.files:
        if f.patch:
            header = f"=== File: {f.filename} ({f.status}) ===\n"
            content = f.patch
            snippet = header + content + "\n\n"
            if current_chars + len(snippet) > max_patch_chars:
                remaining_quota = max(0, max_patch_chars - current_chars)
                if remaining_quota > len(header) + 50:
                    truncated_content = content[: remaining_quota - len(header) - 30]
                    patch_snippets.append(header + truncated_content + "\n[Diff truncated for length - partial evidence limitation]...\n\n")
                else:
                    patch_snippets.append(f"=== File: {f.filename} (Diff omitted due to prompt size limit - partial evidence limitation) ===\n\n")
                break
            else:
                patch_snippets.append(snippet)
                current_chars += len(snippet)
        else:
            patch_snippets.append(f"=== File: {f.filename} (Binary or large diff, patch omitted by GitHub - partial evidence limitation) ===\n\n")

    if patch_snippets:
        patches_text = "".join(patch_snippets)
    else:
        patches_text = "[WARNING: No code patches available for this PR. Any claims about code modifications must be flagged as [Unverified] due to missing diff evidence.]"

    return {
        "repository": f"{context.repo_owner}/{context.repo_name}",
        "pr_number": context.pr_number,
        "title": context.title,
        "author": context.author,
        "pr_url": context.html_url,
        "merged_at": context.merged_at or "Unknown",
        "pr_body": context.body or "No PR description provided.",
        "linked_issues_text": linked_issues_text,
        "files_summary": files_summary,
        "patch_char_count": context.total_patch_char_count,
        "patches_text": patches_text,
    }


SUPPORTED_DEFAULT_MODEL = "gemini-2.5-flash"
DEPRECATED_MODELS = {"gemini-1.5-flash", "models/gemini-1.5-flash", "gemini-1.5-pro", "models/gemini-1.5-pro"}

try:
    from google.api_core.exceptions import ResourceExhausted
except ImportError:
    ResourceExhausted = None  # type: ignore


def extract_retry_delay(exc: Exception, default: float = 10.0) -> float:
    """Extract recommended retry delay seconds from Google ResourceExhausted exception."""
    msg = str(exc)
    match = re.search(r"Please retry in ([0-9]+(?:\.[0-9]+)?)s", msg)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    match_sec = re.search(r"retry_delay\s*\{\s*seconds:\s*([0-9]+)", msg)
    if match_sec:
        try:
            return float(match_sec.group(1))
        except ValueError:
            pass
    return default


def is_quota_exceeded_error(exc: Exception) -> bool:
    """Check if exception is a 429 / ResourceExhausted quota error."""
    if ResourceExhausted is not None and isinstance(exc, ResourceExhausted):
        return True
    msg = str(exc).lower()
    return "429" in msg or "resourceexhausted" in msg or "quota exceeded" in msg


class ReflectionChain:
    """Manages LangChain LCEL pipeline execution with Gemini."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        api_key: Optional[str] = None,
        llm: Optional[Any] = None,
    ):
        self.configured_model = model_name or settings.GEMINI_MODEL
        model = self.configured_model
        if model in DEPRECATED_MODELS:
            logger.info(
                "Configured model '%s' is not supported on current API version. Automatically migrating to effective model '%s'.",
                model,
                SUPPORTED_DEFAULT_MODEL,
            )
            model = SUPPORTED_DEFAULT_MODEL

        self.model_name = model
        self.temperature = temperature if temperature is not None else settings.GEMINI_TEMPERATURE
        raw_key = api_key if api_key is not None else settings.GOOGLE_API_KEY
        self.api_key = raw_key.strip() if isinstance(raw_key, str) else ""

        self.parser = JsonOutputParser(pydantic_object=ReflectionOutput)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ]).partial(format_instructions=self.parser.get_format_instructions())

        if llm is not None:
            self.llm = llm
        else:
            # Note: langchain-google-genai uses google_api_key; limit retries to 2 to prevent long stalls
            self.llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                temperature=self.temperature,
                google_api_key=self.api_key or "missing-key",
                max_retries=2,
            )

        # LCEL pipeline: prompt | model | parser
        self.chain = self.prompt | self.llm | self.parser

    async def generate_reflection(self, context: HydratedPRContext) -> ReflectionOutput:
        """Executes LCEL pipeline to produce a validated technical reflection.
        
        Raises:
            ValueError: If API key is missing or prompt variables are invalid.
            ValidationError: If model output violates Pydantic constraints.
            OutputParserException: If model output cannot be parsed into JSON.
            ResourceExhausted: If Gemini quota/rate limits are exceeded.
        """
        if (not self.api_key or self.api_key == "missing-key") and not hasattr(self.llm, "invoke"):
            raise ValueError(
                "GOOGLE_API_KEY is not configured. Please obtain a valid Gemini API key from "
                "Google AI Studio (https://aistudio.google.com/) and configure GOOGLE_API_KEY in your .env file."
            )

        input_vars = format_pr_context_for_prompt(context)
        logger.info(
            "Invoking LangChain LCEL reflection chain for PR #%d using effective model '%s' (configured: '%s', temp=%.1f)",
            context.pr_number,
            self.model_name,
            self.configured_model,
            self.temperature,
        )

        try:
            raw_output = await self.chain.ainvoke(input_vars)
            logger.info("Successfully received LLM response, validating with ReflectionOutput model")
            
            # Validate output using strict Pydantic model
            if isinstance(raw_output, dict):
                validated_output = ReflectionOutput.model_validate(raw_output)
            elif isinstance(raw_output, ReflectionOutput):
                validated_output = raw_output
            else:
                validated_output = ReflectionOutput.model_validate_json(str(raw_output))

            logger.info(
                "Reflection output validated successfully: %d key learnings generated",
                len(validated_output.key_learnings),
            )
            return validated_output

        except OutputParserException as exc:
            logger.error("Failed to parse LLM output into JSON for PR #%d: %s", context.pr_number, exc)
            raise
        except ValidationError as exc:
            logger.error("LLM output failed Pydantic schema validation for PR #%d: %s", context.pr_number, exc)
            raise
        except Exception as exc:
            if is_quota_exceeded_error(exc):
                delay = extract_retry_delay(exc)
                logger.error(
                    "Gemini API rate limit exceeded (429 ResourceExhausted) for model '%s'. "
                    "Free-tier quota limit is typically 5 requests/minute. "
                    "Recommended retry delay: %.1fs. No reflection generated.",
                    self.model_name,
                    delay,
                )
            else:
                logger.error("Unexpected error in reflection chain for PR #%d: %s", context.pr_number, exc, exc_info=True)
            raise

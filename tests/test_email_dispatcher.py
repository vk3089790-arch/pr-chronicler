"""Tests for SMTP email dispatcher formatting, subject line, TLS, and failure handling."""

from email.message import EmailMessage
import smtplib
from unittest.mock import MagicMock, patch
import pytest

from app.email_dispatcher import EmailDispatcher
from app.models import HydratedPRContext, ReflectionOutput


def test_subject_format(sample_hydrated_context):
    """Verify exact subject format: [OS-Log] PR Merged: <Repository Name> (#<PR Number>)."""
    dispatcher = EmailDispatcher()
    subject = dispatcher.build_subject(sample_hydrated_context.repo_name, sample_hydrated_context.pr_number)
    assert subject == "[OS-Log] PR Merged: backend (#101)"


def test_email_message_structure(sample_hydrated_context, sample_reflection_output):
    """Verify EmailMessage headers and clearly separated body sections."""
    dispatcher = EmailDispatcher(
        smtp_email="sender@example.com",
        recipient_email="team@example.com",
    )
    msg = dispatcher.create_message(sample_hydrated_context, sample_reflection_output)

    assert msg["Subject"] == "[OS-Log] PR Merged: backend (#101)"
    assert msg["From"] == "sender@example.com"
    assert msg["To"] == "team@example.com"

    # Verify plain text content
    plain_content = msg.get_body(preferencelist=("plain",)).get_content()
    assert "ISSUE DETAILS" in plain_content
    assert "EXECUTION SUMMARY" in plain_content
    assert "KEY LEARNINGS" in plain_content
    assert sample_reflection_output.issue_details in plain_content
    assert sample_reflection_output.key_learnings[0] in plain_content

    # Verify HTML alternative
    html_content = msg.get_body(preferencelist=("html",)).get_content()
    assert "backend (#101)" in html_content
    assert "Issue Details" in html_content
    assert "Execution Summary" in html_content
    assert "Key Learnings (3)" in html_content


@pytest.mark.asyncio
async def test_smtp_send_starttls(sample_hydrated_context, sample_reflection_output):
    """Verify port 587 uses smtplib.SMTP, starttls(), and login()."""
    dispatcher = EmailDispatcher(
        smtp_email="bot@example.com",
        smtp_password="app-password-xyz",
        smtp_host="smtp.example.com",
        smtp_port=587,
        recipient_email="alerts@example.com",
        use_tls=True,
    )

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance

    with patch("smtplib.SMTP", return_value=mock_smtp_instance) as mock_smtp_class:
        await dispatcher.send_reflection_email(sample_hydrated_context, sample_reflection_output)

        mock_smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=30.0)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("bot@example.com", "app-password-xyz")
        mock_smtp_instance.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_smtp_send_ssl(sample_hydrated_context, sample_reflection_output):
    """Verify port 465 uses smtplib.SMTP_SSL directly."""
    dispatcher = EmailDispatcher(
        smtp_email="bot@example.com",
        smtp_password="app-password-xyz",
        smtp_host="smtp.example.com",
        smtp_port=465,
        recipient_email="alerts@example.com",
    )

    mock_ssl_instance = MagicMock()
    mock_ssl_instance.__enter__.return_value = mock_ssl_instance

    with patch("smtplib.SMTP_SSL", return_value=mock_ssl_instance) as mock_ssl_class:
        await dispatcher.send_reflection_email(sample_hydrated_context, sample_reflection_output)

        mock_ssl_class.assert_called_once_with("smtp.example.com", 465, timeout=30.0)
        mock_ssl_instance.login.assert_called_once_with("bot@example.com", "app-password-xyz")
        mock_ssl_instance.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_smtp_authentication_failure_handling(sample_hydrated_context, sample_reflection_output):
    """Verify that SMTPAuthenticationError is caught and raised cleanly."""
    dispatcher = EmailDispatcher(
        smtp_email="bot@example.com",
        smtp_password="bad-password",
        smtp_host="smtp.example.com",
        smtp_port=587,
        recipient_email="alerts@example.com",
    )

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance
    mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        with pytest.raises(smtplib.SMTPAuthenticationError):
            await dispatcher.send_reflection_email(sample_hydrated_context, sample_reflection_output)


def test_password_never_in_logs(caplog, sample_hydrated_context, sample_reflection_output):
    """Verify password and tokens never leak into logger output."""
    import io
    import logging
    from app.logging_config import SanitizedFormatter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SanitizedFormatter())
    test_logger = logging.getLogger("test_auth_logger")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)

    test_logger.info("Connecting with password=secret-cleartext-pass and Bearer ghp_1234567890abcdef1234567890")
    handler.flush()

    log_text = stream.getvalue()
    assert "secret-cleartext-pass" not in log_text
    assert "ghp_1234567890abcdef" not in log_text
    assert "***REDACTED***" in log_text

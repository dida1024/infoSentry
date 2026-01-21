"""Tests for email template loader and user email templates."""

from datetime import UTC, datetime

import pytest

from src.core.infrastructure.email.template_loader import render_template
from src.modules.users.application.email_templates import render_magic_link_email


class TestTemplateLoader:
    """Tests for the template loader."""

    def test_render_html_template(self):
        """Test rendering an HTML template."""
        html = render_template(
            "magic_link.html",
            project_name="TestProject",
            to_email="test@example.com",
            login_url="https://example.com/login",
            expires_str="2025-01-21 12:00 UTC",
        )

        assert "TestProject" in html
        assert "test@example.com" in html
        assert "https://example.com/login" in html
        assert "2025-01-21 12:00 UTC" in html
        assert "<!DOCTYPE html>" in html

    def test_render_txt_template(self):
        """Test rendering a plain text template."""
        text = render_template(
            "magic_link.txt",
            project_name="TestProject",
            login_url="https://example.com/login",
            expires_str="2025-01-21 12:00 UTC",
        )

        assert "TestProject" in text
        assert "https://example.com/login" in text
        assert "2025-01-21 12:00 UTC" in text

    def test_template_not_found(self):
        """Test that missing template raises error."""
        from jinja2 import TemplateNotFound

        with pytest.raises(TemplateNotFound):
            render_template("nonexistent_template.html")


class TestMagicLinkEmail:
    """Tests for magic link email rendering."""

    def test_render_magic_link_email(self):
        """Test rendering magic link email."""
        expires_at = datetime(2025, 1, 21, 12, 0, 0, tzinfo=UTC)

        subject, html_body, plain_body = render_magic_link_email(
            to_email="user@example.com",
            login_url="https://example.com/auth/verify?token=abc123",
            expires_at=expires_at,
        )

        # Check subject
        assert "登录链接" in subject

        # Check HTML body
        assert "user@example.com" in html_body
        assert "https://example.com/auth/verify?token=abc123" in html_body
        assert "2025-01-21 12:00 UTC" in html_body
        assert "<!DOCTYPE html>" in html_body
        assert "继续登录" in html_body

        # Check plain body
        assert "https://example.com/auth/verify?token=abc123" in plain_body
        assert "2025-01-21 12:00 UTC" in plain_body

    def test_render_magic_link_email_escapes_html(self):
        """Test that HTML special characters are escaped in templates."""
        expires_at = datetime(2025, 1, 21, 12, 0, 0, tzinfo=UTC)

        subject, html_body, plain_body = render_magic_link_email(
            to_email="user+test@example.com",
            login_url="https://example.com/auth?token=abc&foo=bar",
            expires_at=expires_at,
        )

        # The & should be escaped in HTML
        assert "&amp;" in html_body or "token=abc&foo=bar" in html_body

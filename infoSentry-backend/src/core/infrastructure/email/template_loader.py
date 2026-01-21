"""Simple email template loader using Jinja2.

Templates are stored in resources/email_templates/ directory.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Template directory relative to this file
_TEMPLATES_DIR = (
    Path(__file__).parent.parent.parent.parent.parent / "resources" / "email_templates"
)

_env: Environment | None = None


def _get_env() -> Environment:
    """Get or create Jinja2 environment (lazy initialization)."""
    global _env
    if _env is None:
        if not _TEMPLATES_DIR.exists():
            raise FileNotFoundError(
                f"Email templates directory not found: {_TEMPLATES_DIR}"
            )
        _env = Environment(
            loader=FileSystemLoader(_TEMPLATES_DIR),
            autoescape=select_autoescape(["html", "xml"]),
        )
    return _env


def render_template(name: str, **variables: object) -> str:
    """Render an email template file.

    Args:
        name: Template file name (e.g. "magic_link.html")
        **variables: Template variables

    Returns:
        Rendered template string

    Raises:
        jinja2.TemplateNotFound: If template file not found
        jinja2.TemplateError: If template rendering fails
    """
    env = _get_env()
    template = env.get_template(name)
    return template.render(**variables)

"""Render email templates (plain text + simple HTML, no images or links; NFR12.2)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.platform.email.port import EmailTemplate

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

_environment = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=False),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)


@dataclass(frozen=True)
class RenderedEmail:
    """A rendered message ready for a transport."""

    subject: str
    text: str
    html: str


def render_email(template: EmailTemplate, variables: Mapping[str, Any]) -> RenderedEmail:
    """Render the subject, plain-text and HTML parts of ``template``.

    Raises:
        jinja2.UndefinedError: If a variable the template needs is missing.
    """
    name = template.value
    subject = _environment.get_template(f"{name}.subject.txt").render(**variables).strip()
    text = _environment.get_template(f"{name}.txt").render(**variables)
    html = _environment.get_template(f"{name}.html").render(**variables)
    return RenderedEmail(subject=subject, text=text, html=html)

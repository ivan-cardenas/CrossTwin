"""
``{% info_help "<key>" %}`` renders a card's "?" button with its help entry
from core/indicator_help.py (what it is, how it is measured, equations).

    {% load indicator_help %}
    {% info_help "water.supply_security" %}

Equations are written for people: ``{a | b}`` becomes a stacked fraction and
``^(x)`` a superscript; everything else is escaped text.
"""
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from core.indicator_help import HELP

register = template.Library()

_FRACTION = re.compile(r"\{([^{}|]+)\|([^{}]+)\}")
_SUPERSCRIPT = re.compile(r"\^\(([^()]+)\)")


@register.filter
def friendly_equation(text):
    """Escape an equation and render its fractions and superscripts as HTML."""
    html = escape(text)
    html = _FRACTION.sub(
        lambda m: (
            '<span class="eq-frac"><span class="eq-num">{}</span>'
            '<span class="eq-den">{}</span></span>'
        ).format(m.group(1).strip(), m.group(2).strip()),
        html,
    )
    html = _SUPERSCRIPT.sub(r"<sup>\1</sup>", html)
    return mark_safe(html)


@register.inclusion_tag("partials/_info_btn.html")
def info_help(key):
    """The "?" button of card `key`; an unknown key renders the button with only its key as title."""
    entry = HELP.get(key)
    if entry is None:
        return {"title": key, "help": None}
    return {"title": entry["title"], "help": entry}

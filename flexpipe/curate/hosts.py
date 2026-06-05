"""
Host name normalization.

Normalizes free-text host names to standardized categories using an ordered
rule set loaded from ``flexpipe/data/hosts/host_rules.yaml``.  Rules are
evaluated top-down; first match wins.

Current categories: human, swine, avian, mouse, ferret, camel, dog.
Unknown hosts are returned as-is (lowercased, semicolon-split base).

Extracted verbatim from ``scripts/curate.py`` (the ``_norm_host`` closure
and its supporting regexes, lines 434–469).

Phase 3: rule tables are loaded from ``flexpipe/data/hosts/host_rules.yaml``
so a new pathogen can add host categories without editing Python.
"""

from __future__ import annotations

import logging
import re
from typing import Callable

from flexpipe.data import load_data_yaml

logger = logging.getLogger(__name__)


def _compile_condition(cond: dict) -> Callable[[str], bool]:
    """Compile a single YAML condition dict into a callable predicate."""
    t = cond["type"]
    if t == "regex":
        pattern = re.compile(cond["pattern"], re.I)
        return lambda bl, _p=pattern: bool(_p.match(bl))
    if t == "startswith":
        values = tuple(cond["values"])
        return lambda bl, _v=values: any(bl.startswith(v) for v in _v)
    if t == "literal":
        values = frozenset(cond["values"])
        return lambda bl, _v=values: bl in _v
    if t == "contains":
        value = cond["value"]
        return lambda bl, _v=value: _v in bl
    if t == "contains_any":
        keywords = tuple(cond["keywords"])
        return lambda bl, _kw=keywords: any(kw in bl for kw in _kw)
    raise ValueError(f"Unknown condition type in host_rules.yaml: {t!r}")


def _compile_rules(rules_data: list) -> list:
    """Return a list of (target, [condition_callables]) tuples."""
    compiled = []
    for rule in rules_data:
        target = rule["target"]
        conds = [_compile_condition(c) for c in rule.get("conditions", [])]
        compiled.append((target, conds))
    return compiled


_rules_yaml = load_data_yaml("flexpipe.data.hosts", "host_rules.yaml")
_COMPILED_RULES = _compile_rules(_rules_yaml["rules"])  # type: ignore[index]


def build_rules(override: str | None = None) -> list:
    """Compile host-normalization rules from a YAML file.

    Args:
        override: Optional path to a replacement ``host_rules.yaml``.  When
            ``None`` the bundled default is used.

    Returns:
        List of ``(target, [condition_callables])`` tuples suitable for use as
        the *rules* argument of :func:`normalize_host`.
    """

    rules_data = load_data_yaml("flexpipe.data.hosts", "host_rules.yaml", override=override)
    return _compile_rules(rules_data["rules"])  # type: ignore[index]


def normalize_host(raw: str, rules: list | None = None) -> str:
    """Normalize a free-text host name to a standard category.

    Rules are evaluated in order; the first matching rule wins.  A rule
    matches if ANY of its conditions is satisfied (OR semantics within a rule).

    Special targets:
    - ``""`` (empty string): sequence should be dropped.
    - *fallback*: base name (before first ``;``), lowercased.

    Args:
        raw: Raw host string from metadata (may contain semicolons or scientific names).
        rules: Optional compiled rules list (from :func:`build_rules`).  Falls
            back to the module-level default when ``None``.

    Returns:
        Normalized category string, or ``""`` for hosts to be dropped.
    """
    s = raw.strip()
    if not s:
        return s
    base = s.split(";")[0].strip()
    bl = base.lower()

    compiled = rules if rules is not None else _COMPILED_RULES
    for target, conds in compiled:
        if any(cond(bl) for cond in conds):
            return target
    return bl


# Alias retained for any external callers
_norm_host = normalize_host

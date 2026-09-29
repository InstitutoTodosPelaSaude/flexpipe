"""Resolve the build's ``auspice_config.json`` against the run's parameters.

The build ships one display config.  A build inferred without a time scale
(``parameters.timetree: false``) has no ``num_date`` on any node, so a config
asking Auspice to measure distance in time, or to colour or filter by date,
points at data the dataset does not carry.  This module produces the workdir
copy that ``augur export`` actually reads.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)

TIME_KEYS = {"num_date"}


def resolve_auspice_config(raw: dict[str, Any], timetree: bool = True) -> dict[str, Any]:
    """Return *raw* adjusted for a run with or without a time scale.

    With ``timetree=True`` the config is returned unchanged.  Without a time
    scale, ``display_defaults.distance_measure`` falls back to divergence and
    any colouring or filter keyed on a date is dropped, since those entries
    would reference attributes ``augur refine`` never wrote.

    The ``panels`` list is left alone: a map still works without dates, it just
    loses the animation, and which panels a build shows stays the build's call.
    """
    out = copy.deepcopy(raw)
    if timetree:
        return out

    display = out.get("display_defaults")
    if isinstance(display, dict) and display.get("distance_measure") != "div":
        logger.info(
            "No time scale in this run: display_defaults.distance_measure %r -> 'div'",
            display.get("distance_measure"),
        )
        display["distance_measure"] = "div"

    colorings = out.get("colorings")
    if isinstance(colorings, list):
        kept = [c for c in colorings if not _is_time_key(c)]
        if len(kept) != len(colorings):
            logger.info(
                "No time scale in this run: dropped %d date colouring(s)",
                len(colorings) - len(kept),
            )
        out["colorings"] = kept

    filters = out.get("filters")
    if isinstance(filters, list):
        kept_filters = [f for f in filters if str(f) not in TIME_KEYS]
        if len(kept_filters) != len(filters):
            logger.info(
                "No time scale in this run: dropped %d date filter(s)",
                len(filters) - len(kept_filters),
            )
        out["filters"] = kept_filters

    return out


def _is_time_key(coloring: Any) -> bool:
    if isinstance(coloring, dict):
        return str(coloring.get("key", "")) in TIME_KEYS
    return str(coloring) in TIME_KEYS

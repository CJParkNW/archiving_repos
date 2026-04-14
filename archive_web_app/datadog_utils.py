"""
Optional Datadog integration shared by pipeline.py and app.py.

All public functions are no-ops when DATADOG_API_KEY is not set,
so the rest of the app never needs to guard against DD being absent.
"""
import logging
import os
import time

from dotenv import load_dotenv

# load_dotenv here makes this module self-contained regardless of the
# order in which the caller invokes load_dotenv itself.
load_dotenv()

logger = logging.getLogger("repo_archiver.datadog")

_dd_enabled = False
_dd_api = None

_api_key = os.getenv("DATADOG_API_KEY")
if _api_key:
    try:
        from datadog import initialize, api as _dd_api_module
        initialize(api_key=_api_key)
        _dd_api = _dd_api_module
        _dd_enabled = True
    except Exception as _exc:
        logger.warning("Datadog initialization failed: %s", _exc)
else:
    logger.info(
        "DATADOG_API_KEY not set — "
        "Datadog metrics/events will be skipped."
    )


def send_metric(
    metric: str,
    value: float,
    tags: list[str] | None = None,
) -> None:
    """Send a single gauge to Datadog, or no-op if DD is not configured."""
    if not _dd_enabled:
        return
    try:
        _dd_api.Metric.send(
            metric=metric,
            points=[[int(time.time()), value]],
            tags=tags or [],
        )
    except Exception as exc:
        logger.warning(
            "Datadog metric send failed (%s): %s", metric, exc
        )


def send_metrics_batch(metrics: list[dict]) -> None:
    """
    Send multiple metrics in a single API call.

    Each dict must have 'metric' (str) and 'points' (float), and
    optionally 'tags' (list[str]).  A timestamp is added automatically.

    Using a single request keeps per-repo cardinality cheap and ensures
    Datadog correctly attributes each data point to the right tag set.
    """
    if not _dd_enabled or not metrics:
        return
    now = int(time.time())
    series = [
        {
            "metric": m["metric"],
            "points": [[now, m["points"]]],
            "tags": m.get("tags", []),
        }
        for m in metrics
    ]
    try:
        _dd_api.Metric.send(series)
        logger.info(
            "Datadog batch: %d series submitted.", len(series)
        )
    except Exception as exc:
        logger.warning("Datadog batch metric send failed: %s", exc)


def send_event(
    title: str,
    text: str,
    tags: list[str] | None = None,
) -> None:
    """Send an event to Datadog, or no-op if DD is not configured."""
    if not _dd_enabled:
        return
    try:
        _dd_api.Event.create(title=title, text=text, tags=tags or [])
    except Exception as exc:
        logger.warning(
            "Datadog event send failed (%s): %s", title, exc
        )

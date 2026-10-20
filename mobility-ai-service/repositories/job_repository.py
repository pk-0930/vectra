"""Compatibility import for the retired, unscoped legacy jobs adapter.

The jobs table is retained for reviewed ownership reconciliation, not normal
application access. Current API/worker paths use PostgresPlatformRepository's
form analyses. Keeping this explicit failure prevents accidentally reviving the
old globally readable queue store through JobService's legacy-adapter fallback.
"""
from config.postgres_config import PostgresConfig


class PostgresJobRepository:
    def __init__(self, config: PostgresConfig):
        raise RuntimeError(
            "Legacy jobs have no verified business ownership. "
            "Use scoped form analyses; reconcile legacy jobs separately."
        )

"""Explicit spans only. The caller chooses boundaries and storage."""
from contextlib import contextmanager
from time import perf_counter_ns
from uuid import uuid4
from .protocol import SCHEMA


@contextmanager
def span(sink, *, run, scope, environment, workload, work_units=1):
    start = perf_counter_ns()
    status = 'ok'
    try:
        yield
    except BaseException:
        status = 'error'
        raise
    finally:
        sink(dict(schema=SCHEMA, run=run, event_id=uuid4().hex, scope=scope,
                  environment=environment, workload=workload, work_units=work_units,
                  start_ns=start, end_ns=perf_counter_ns(), status=status))

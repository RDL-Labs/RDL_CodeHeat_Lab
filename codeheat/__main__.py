"""Deterministic protocol demonstration, not a timing benchmark."""
import json
from .protocol import Inspector, Model, SCHEMA

m = Model('baseline-v1', 'observation', 'synthetic', '100-rays', 100, theta=2,
          decay_per_second=0)
observer = Inspector('demo', [m])
for i, duration in enumerate([100, 100, 200, 200, 100, 100, 100]):
    event = dict(schema=SCHEMA, run='demo', event_id=str(i), scope='observation',
                 environment='synthetic', workload='100-rays', work_units=1,
                 start_ns=i*1000, end_ns=i*1000+duration, status='ok')
    print(json.dumps(observer.ingest(event)))

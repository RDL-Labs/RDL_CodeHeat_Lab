"""CodeHeat/0.1 wire validation and bounded local inspection policy."""
from dataclasses import dataclass
import math

SCHEMA = 'codeheat.span.v1'


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('nonnegative_finite_number_required')
    return value


def validate(event):
    required = {'schema', 'run', 'event_id', 'scope', 'environment', 'workload',
                'start_ns', 'end_ns', 'work_units', 'status'}
    if set(event) != required or event['schema'] != SCHEMA:
        raise ValueError('event_schema')
    for key in ('run', 'event_id', 'scope', 'environment', 'workload'):
        if type(event[key]) is not str or not 0 < len(event[key]) <= 128:
            raise ValueError('event_identity')
    for key in ('start_ns', 'end_ns'):
        if type(event[key]) is not int or event[key] < 0:
            raise ValueError('event_clock')
    if event['end_ns'] < event['start_ns']:
        raise ValueError('event_clock_order')
    if number(event['work_units']) == 0:
        raise ValueError('positive_work_units_required')
    if event['status'] not in ('ok', 'error'):
        raise ValueError('event_status')
    return event


@dataclass(frozen=True)
class Model:
    ref: str
    scope: str
    environment: str
    workload: str
    ns_per_unit: float
    theta: float = 3.0
    decay_per_second: float = 0.1
    detail_samples: int = 3

    def __post_init__(self):
        for value in (self.ref, self.scope, self.environment, self.workload):
            if type(value) is not str or not 0 < len(value) <= 128:
                raise ValueError('model_identity')
        for value in (self.ns_per_unit, self.theta):
            if number(value) == 0:
                raise ValueError('positive_model_parameter')
        number(self.decay_per_second)
        if type(self.detail_samples) is not int or not 1 <= self.detail_samples <= 16:
            raise ValueError('detail_budget')


class Inspector:
    """One run and fixed models; explicit capacity refusal, no silent eviction."""
    def __init__(self, run, models, capacity=10000):
        if type(run) is not str or not run or type(capacity) is not int or capacity < 1:
            raise ValueError('inspector_config')
        if not 1 <= len(models) <= 64 or len({m.scope for m in models}) != len(models):
            raise ValueError('model_scope_capacity')
        self.run = run
        self.models = {m.scope: m for m in models}
        self.capacity = capacity
        self.receipts = {}
        self.state = {}

    def ingest(self, event):
        validate(event)
        if event['run'] != self.run:
            raise ValueError('run_mismatch')
        identity = event['event_id']
        if identity in self.receipts:
            original, receipt = self.receipts[identity]
            if event != original:
                raise ValueError('event_conflict')
            return dict(receipt)
        if len(self.receipts) >= self.capacity:
            raise ValueError('event_capacity')
        scope = event['scope']
        m = self.models.get(scope)
        cost = event['end_ns'] - event['start_ns']
        result = dict(event_id=identity, scope=scope, duration_ns=cost,
                      model_ref=m.ref if m else None, status='not_comparable',
                      E=None, H=None, mode=None, reason=None)
        if m is None:
            result['reason'] = 'model_unavailable'
        elif (event['environment'], event['workload']) != (m.environment, m.workload):
            result['reason'] = 'context_mismatch'
        elif event['status'] != 'ok':
            result['reason'] = 'operation_error'
        else:
            old = self.state.get(scope, dict(H=0., end_ns=event['start_ns'], remaining=0))
            if event['start_ns'] < old['end_ns']:
                raise ValueError('scope_overlap_or_reordering')
            expected = m.ns_per_unit * event['work_units']
            if not math.isfinite(expected):
                raise ValueError('expected_cost_overflow')
            difference = (cost - expected) / expected
            if not math.isfinite(difference):
                raise ValueError('difference_overflow')
            elapsed = (event['end_ns'] - old['end_ns']) / 1e9
            H = min(m.theta * 4, max(0., old['H'] - elapsed * m.decay_per_second)
                    + max(0., difference))
            remaining = max(0, old['remaining'] - 1)
            trigger = old['remaining'] == 0 and H >= m.theta
            accumulated = H
            if trigger:
                remaining = m.detail_samples
                H = 0.  # Local inspection-cycle reset, not model reconstruction.
            self.state[scope] = dict(H=H, end_ns=event['end_ns'], remaining=remaining)
            result.update(status='compared', E=difference, H=H,
                          H_before_cycle_reset=accumulated,
                          expected_ns=expected, inspection_triggered=trigger,
                          mode='detail_requested' if remaining else 'coarse',
                          remaining_detail_samples=remaining)
        self.receipts[identity] = (dict(event), dict(result))
        return result

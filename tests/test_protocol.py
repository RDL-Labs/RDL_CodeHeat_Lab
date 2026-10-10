import unittest
from codeheat.protocol import Inspector, Model, SCHEMA
from codeheat.collector import span


def event(i=0, duration=100, **kw):
    return dict(dict(schema=SCHEMA, run='r', event_id=str(i), scope='sense',
        environment='env', workload='w', work_units=1,
        start_ns=i*1000, end_ns=i*1000+duration, status='ok'), **kw)


class ProtocolTests(unittest.TestCase):
    def observer(self, **kw):
        return Inspector('r', [Model('m1','sense','env','w',100,theta=2,decay_per_second=0,detail_samples=2)], **kw)

    def test_accumulate_detail_and_return(self):
        o=self.observer()
        self.assertEqual(o.ingest(event(0,200))['H'],1)
        self.assertTrue(o.ingest(event(1,200))['inspection_triggered'])
        self.assertEqual(o.ingest(event(2))['mode'],'detail_requested')
        self.assertEqual(o.ingest(event(3))['mode'],'coarse')

    def test_known_expensive_cost_is_not_difference(self):
        o=Inspector('r',[Model('m','sense','env','w',1000000)])
        r=o.ingest(event(duration=1000000))
        self.assertEqual(r['E'],0)
        self.assertEqual(r['duration_ns'],1000000)

    def test_retry_at_capacity_and_conflict(self):
        o=self.observer(capacity=1);r=o.ingest(event())
        self.assertEqual(o.ingest(event()),r)
        r['H']=99
        self.assertEqual(o.ingest(event())['H'],0)
        with self.assertRaisesRegex(ValueError,'conflict'):o.ingest(event(duration=120))
        with self.assertRaisesRegex(ValueError,'capacity'):o.ingest(event(1))

    def test_unknown_and_error_do_not_change_state(self):
        for kw in ({'scope':'missing'},{'environment':'other'},{'status':'error'}):
            o=self.observer()
            self.assertEqual(o.ingest(event(**kw))['status'],'not_comparable')
            self.assertEqual(o.state,{})

    def test_bad_inputs_are_atomic(self):
        for kw in ({'work_units':0},{'work_units':float('nan')},{'run':'other'},
                   {'start_ns':-1},{'end_ns':-1},{'start_ns':True}):
            o=self.observer()
            with self.assertRaises(ValueError):o.ingest(event(**kw))
            self.assertEqual(o.receipts,{})

    def test_overlap_refused(self):
        o=self.observer();o.ingest(event())
        with self.assertRaisesRegex(ValueError,'overlap'):o.ingest(event(1,start_ns=50))
        self.assertEqual(len(o.receipts),1)

    def test_negative_difference_not_hidden(self):
        r=self.observer().ingest(event(duration=50))
        self.assertEqual(r['E'],-.5);self.assertEqual(r['H'],0)

    def test_elapsed_decay_and_work_units(self):
        o=Inspector('r',[Model('m','sense','env','w',100,theta=3,decay_per_second=1)])
        self.assertGreater(o.ingest(event(0,200))['H'],.9)
        r=o.ingest(event(1,200,start_ns=2_000_000_000,end_ns=2_000_000_200,work_units=2))
        self.assertEqual(r['E'],0)
        self.assertEqual(r['H'],0)

    def test_scopes_do_not_mix(self):
        o=Inspector('r',[Model('m1','sense','env','w',100,decay_per_second=0),
                         Model('m2','other','env','w',100,decay_per_second=0)])
        o.ingest(event(0,200))
        self.assertEqual(o.ingest(event(1,100,scope='other'))['H'],0)
        self.assertEqual(o.state['sense']['H'],1)

    def test_collector_error_and_units(self):
        rows=[]
        with self.assertRaisesRegex(RuntimeError,'original'):
            with span(rows.append,run='r',scope='sense',environment='env',workload='w'):
                raise RuntimeError('original')
        self.assertEqual(rows[0]['status'],'error')
        self.assertGreaterEqual(rows[0]['end_ns'],rows[0]['start_ns'])


if __name__=='__main__':unittest.main()

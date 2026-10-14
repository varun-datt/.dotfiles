import json, os, sys, tempfile, types, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status  # noqa: E402

NOW = 1_800_000_000


class RowsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = self.tmp.name
        self.ps = ''
        for p in (mock.patch.object(status, 'RUN', self.run_dir),
                  mock.patch.object(status, 'subprocess', types.SimpleNamespace(run=lambda *a, **k: types.SimpleNamespace(stdout=self.ps))),
                  mock.patch.object(status, 'time', types.SimpleNamespace(time=lambda: NOW))):
            p.start()
            self.addCleanup(p.stop)

    def worker(self, name, started_ago, events):
        start = os.path.join(self.run_dir, name + '.start')
        with open(start, 'w') as f:
            f.write(str(NOW - started_ago))
        os.utime(start, (NOW - started_ago, NOW - started_ago))
        jl = os.path.join(self.run_dir, name + '.jsonl')
        with open(jl, 'w') as f:
            f.writelines(json.dumps(e) + '\n' for e in events)
        os.utime(jl, (NOW - started_ago + 60, NOW - started_ago + 60))

    def states(self):
        return {r['name']: r['state'] for r in status.rows()}

    def test_an_errored_round_is_superseded_once_a_later_round_of_its_item_starts(self):
        failed = [{'type': 'model.call_finished'}, {'type': 'result', 'exitCode': 1}]
        self.worker('a', 4000, failed)
        self.worker('a-fix1', 3000, failed)
        self.worker('a-resume2', 600, [{'type': 'model.call_finished'}])
        self.worker('b', 1000, failed)
        self.ps = '1 copilot -n ow-a-resume2\n'
        self.assertEqual(self.states(), {'a': 'superseded', 'a-fix1': 'superseded', 'a-resume2': 'running', 'b': 'ERRORED'})

    def test_a_later_round_of_another_item_supersedes_nothing(self):
        self.worker('a', 2000, [{'type': 'result', 'exitCode': 1}])
        self.worker('ab-fix1', 1000, [{'type': 'model.call_finished'}])
        self.assertEqual(self.states(), {'a': 'ERRORED', 'ab-fix1': 'DIED (no result)'})

    def test_a_session_error_round_is_superseded_like_a_non_zero_exit(self):
        self.worker('d-review', 2000, [{'type': 'model.call_finished'}, {'type': 'session.error'}, {'type': 'result', 'exitCode': 0}])
        self.worker('d-rereview', 1000, [{'type': 'model.call_finished'}, {'type': 'result', 'exitCode': 0}])
        self.assertEqual(self.states(), {'d-review': 'superseded', 'd-rereview': 'done'})

    def test_a_finished_round_stays_done_after_a_later_round(self):
        self.worker('c', 2000, [{'type': 'model.call_finished'}, {'type': 'result', 'exitCode': 0}])
        self.worker('c-review', 1000, [{'type': 'model.call_finished'}, {'type': 'result', 'exitCode': 0}])
        self.assertEqual(self.states(), {'c': 'done', 'c-review': 'done'})


if __name__ == '__main__':
    unittest.main()

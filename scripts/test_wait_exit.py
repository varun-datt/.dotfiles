import importlib.machinery
import importlib.util
import io
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "dotfiles", "dot_local", "bin", "executable_wait-exit")


def load():
    loader = importlib.machinery.SourceFileLoader("wait_exit", SCRIPT)
    spec = importlib.util.spec_from_loader("wait_exit", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def orphan_sleep(seconds):
    # Not our child, as a check started in another terminal is not the waiter's child.
    out = subprocess.run(["/bin/sh", "-c", f"sleep {seconds} >/dev/null 2>&1 & echo $!"],
                         capture_output=True, text=True, check=True)
    return int(out.stdout.strip())


def kill_quietly(pid):
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run(*args, timeout=20):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True,
                          timeout=timeout, stdin=subprocess.DEVNULL)


def start(*args):
    return subprocess.Popen([sys.executable, SCRIPT, *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, stdin=subprocess.DEVNULL)


def finish(p):
    p.communicate(timeout=10)
    return p.returncode


def write_later(path, text, delay):
    def go():
        time.sleep(delay)
        with open(path, "w") as f:
            f.write(text)
    t = threading.Thread(target=go)
    t.start()
    return t


class Pid(unittest.TestCase):
    def test_returns_soon_after_the_process_ends(self):
        pid = orphan_sleep(1.5)
        self.addCleanup(kill_quietly, pid)
        t0 = time.monotonic()
        r = run("--pid", str(pid))
        took = time.monotonic() - t0
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, rf"^pid {pid} ended after \d+ s\n$")
        self.assertGreater(took, 1.2)
        self.assertLess(took, 2.9)

    def test_a_pid_already_gone_returns_at_once(self):
        p = subprocess.Popen(["/usr/bin/true"])
        p.wait()
        t0 = time.monotonic()
        r = run("--pid", str(p.pid))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, f"pid {p.pid} was not running\n")
        self.assertLess(time.monotonic() - t0, 2)

    def test_another_users_process_is_waited_on(self):
        r = run("--pid", "1", "--timeout", "0.5")
        self.assertEqual(r.returncode, 124, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "pid 1 still running after 0.5 s\n")

    def test_timeout_exits_124(self):
        pid = orphan_sleep(30)
        self.addCleanup(kill_quietly, pid)
        t0 = time.monotonic()
        r = run("--pid", str(pid), "--timeout", "0.5")
        self.assertEqual(r.returncode, 124)
        self.assertEqual(r.stdout, f"pid {pid} still running after 0.5 s\n")
        self.assertLess(time.monotonic() - t0, 3)

    def test_two_waiters_on_one_process_both_return(self):
        pid = orphan_sleep(1)
        self.addCleanup(kill_quietly, pid)
        a, b = start("--pid", str(pid)), start("--pid", str(pid))
        self.assertEqual(finish(a), 0)
        self.assertEqual(finish(b), 0)

    def test_cancel_exits_130_without_a_traceback(self):
        pid = orphan_sleep(30)
        self.addCleanup(kill_quietly, pid)
        p = start("--pid", str(pid))
        time.sleep(0.5)
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=10)
        self.assertEqual(p.returncode, 130)
        self.assertNotIn("Traceback", err)
        self.assertIn("cancelled", err)


class PollFallback(unittest.TestCase):
    def setUp(self):
        self.mod = load()

    def test_the_poll_ends_gone_and_times_out(self):
        pid = orphan_sleep(1)
        self.addCleanup(kill_quietly, pid)
        self.assertEqual(self.mod.wait_pid_poll(pid, None), "ended")
        self.assertEqual(self.mod.wait_pid_poll(pid, None), "gone")
        self.assertEqual(self.mod.wait_pid_poll(1, time.monotonic() + 0.3), "timeout")

    def test_it_is_used_without_kqueue_or_pidfd(self):
        with mock.patch.object(self.mod, "select", mock.Mock(spec=[])), \
                mock.patch.object(self.mod, "os", mock.Mock(spec=["kill"], kill=os.kill)), \
                mock.patch.object(self.mod, "wait_pid_poll", return_value="ended") as poll:
            self.assertEqual(self.mod.wait_pid(1, None), "ended")
        poll.assert_called_once_with(1, None)


class File(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "check.exit")

    def test_exits_with_the_code_written(self):
        t = write_later(self.path, "2\n", 0.5)
        r = run("--file", self.path)
        t.join()
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, f"{self.path}: exit 2\n")

    def test_zero_is_success(self):
        t = write_later(self.path, "0\n", 0.2)
        r = run("--file", self.path)
        t.join()
        self.assertEqual(r.returncode, 0)

    def test_an_empty_or_partial_file_keeps_it_waiting(self):
        open(self.path, "w").close()
        p = start("--file", self.path)
        time.sleep(0.6)
        self.assertIsNone(p.poll(), "returned on an empty file")
        with open(self.path, "w") as f:
            f.write("exit")
        time.sleep(0.6)
        self.assertIsNone(p.poll(), "returned on text that is not a number")
        with open(self.path, "w") as f:
            f.write("7\n")
        p.communicate(timeout=10)
        self.assertEqual(p.returncode, 7)

    def test_a_file_from_an_earlier_run_is_read_at_once(self):
        with open(self.path, "w") as f:
            f.write("3\n")
        t0 = time.monotonic()
        r = run("--file", self.path)
        self.assertEqual(r.returncode, 3)
        self.assertLess(time.monotonic() - t0, 2)

    def test_a_code_out_of_range_fails(self):
        with open(self.path, "w") as f:
            f.write("256\n")
        r = run("--file", self.path)
        self.assertEqual(r.returncode, 1)
        self.assertIn("not an exit code", r.stdout)

    def test_timeout_exits_124(self):
        r = run("--file", self.path, "--timeout", "0.5")
        self.assertEqual(r.returncode, 124)
        self.assertEqual(r.stdout, f"{self.path}: no exit code after 0.5 s\n")

    def test_two_waiters_on_one_file_both_return(self):
        a, b = start("--file", self.path), start("--file", self.path)
        time.sleep(0.3)
        with open(self.path, "w") as f:
            f.write("4\n")
        self.assertEqual(finish(a), 4)
        self.assertEqual(finish(b), 4)


class Dots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "check.exit")

    def test_dots_while_waiting_then_the_failed_code_ends_the_wait(self):
        t = write_later(self.path, "1\n", 0.9)
        r = run("--file", self.path, "--dots", "0.2")
        t.join()
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout, rf"^\.{{2,}}\n{self.path}: exit 1\n$")

    def test_a_code_already_written_prints_no_dots(self):
        with open(self.path, "w") as f:
            f.write("0\n")
        r = run("--file", self.path, "--dots", "0.2")
        self.assertEqual(r.stdout, f"{self.path}: exit 0\n")

    def test_the_timeout_still_applies(self):
        t0 = time.monotonic()
        r = run("--file", self.path, "--dots", "0.2", "--timeout", "0.7")
        self.assertEqual(r.returncode, 124)
        self.assertLess(time.monotonic() - t0, 2.5)
        self.assertRegex(r.stdout, rf"^\.+\n{self.path}: no exit code after 0.7 s\n$")

    def test_a_pid_that_ends_between_dots_is_ended_not_gone(self):
        pid = orphan_sleep(1)
        self.addCleanup(kill_quietly, pid)
        r = run("--pid", str(pid), "--dots", "0.3")
        self.assertEqual(r.returncode, 0)
        self.assertRegex(r.stdout, rf"^\.+\npid {pid} ended after \d+ s\n$")

    def test_dots_must_be_positive(self):
        r = run("--file", self.path, "--dots", "0")
        self.assertEqual(r.returncode, 2)

    def test_a_pid_gone_after_a_dot_is_reported_ended(self):
        mod = load()
        with mock.patch.object(mod, "wait_pid", side_effect=["timeout", "gone"]), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(mod.main(["--pid", "5", "--dots", "0.01"]), 0)
        self.assertRegex(out.getvalue(), r"^\.\npid 5 ended after \d+ s\n$")


class Usage(unittest.TestCase):
    def test_bad_use_exits_2(self):
        for args in ([], ["--pid", "1", "--file", "x"], ["--pid", "abc"], ["--pid", "0"],
                     ["--pid", "-1"], ["--file", "x", "--timeout", "-1"]):
            with self.subTest(args=args):
                r = run(*args)
                self.assertEqual(r.returncode, 2, r.stdout)
                self.assertIn("usage", r.stderr)

    def test_no_option_matches_processes_by_text(self):
        r = run("--help")
        self.assertNotRegex(r.stdout, r"--(pattern|name|match|grep)")


if __name__ == "__main__":
    unittest.main()

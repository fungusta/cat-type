"""Regression tests for live CI output and hung-test diagnostics."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest

from scripts import run_ci_tests


class CiRunnerTests(unittest.TestCase):
    def test_streams_progress_before_child_exits_and_preserves_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            release = Path(directory) / 'release'

            class Output(io.StringIO):
                def write(self, value):
                    if 'child ready' in value:
                        release.touch()
                    return super().write(value)

            output = Output()
            code = (
                "import pathlib,time,sys; print('child ready', end='', flush=True); "
                f"p=pathlib.Path({str(release)!r}); "
                "deadline=time.monotonic()+3\n"
                "while not p.exists() and time.monotonic()<deadline: time.sleep(.01)\n"
                "sys.exit(7 if p.exists() else 8)"
            )
            with contextlib.redirect_stdout(output):
                result, captured = run_ci_tests._run_streaming(
                    [sys.executable, '-u', '-c', code], timeout=5
                )
            self.assertEqual(result, 7)
            self.assertEqual(captured, 'child ready')
            self.assertEqual(output.getvalue(), captured)

    def test_timeout_stops_child_and_reports_failure(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result, captured = run_ci_tests._run_streaming(
                [sys.executable, '-u', '-c', "import time; print('running'); time.sleep(30)"],
                timeout=2,
            )
        self.assertEqual(result, 124)
        self.assertIn('running', captured)
        self.assertIn('::error title=Test timeout::', output.getvalue())

    def test_timeout_is_bounded_when_descendant_inherits_output(self):
        import time
        output = io.StringIO()
        code = (
            "import subprocess,sys,time; "
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(8)']); "
            "print('descendant started', flush=True); time.sleep(30)"
        )
        started = time.monotonic()
        with contextlib.redirect_stdout(output):
            result, captured = run_ci_tests._run_streaming(
                [sys.executable, '-u', '-c', code], timeout=2,
            )
        self.assertEqual(result, 124)
        self.assertIn('descendant started', captured)
        self.assertLess(time.monotonic() - started, 5)

    def test_timeout_is_bounded_after_parent_exits_with_inherited_pipe(self):
        import time
        output = io.StringIO()
        code = (
            "import subprocess,sys; "
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(8)']); "
            "print('parent exiting', flush=True)"
        )
        started = time.monotonic()
        with contextlib.redirect_stdout(output):
            result, captured = run_ci_tests._run_streaming(
                [sys.executable, '-u', '-c', code], timeout=2,
            )
        self.assertEqual(result, 124)
        self.assertIn('parent exiting', captured)
        self.assertLess(time.monotonic() - started, 5)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows job lifecycle')
    def test_timeout_kills_descendant_after_parent_exits(self):
        import time
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'survived'
            descendant = f"import pathlib,time; time.sleep(4); pathlib.Path({str(marker)!r}).touch()"
            code = (
                "import subprocess,sys; "
                f"subprocess.Popen([sys.executable, '-c', {descendant!r}]); "
                "print('parent exiting', flush=True)"
            )
            with contextlib.redirect_stdout(io.StringIO()):
                result, captured = run_ci_tests._run_streaming(
                    [sys.executable, '-u', '-c', code], timeout=2,
                )
            self.assertEqual(result, 124)
            self.assertIn('parent exiting', captured)
            time.sleep(4.1)
            self.assertFalse(marker.exists(), 'orphan descendant survived timeout')

    def test_timeout_drains_pending_output_and_finishes_utf8_decoder(self):
        import time
        with tempfile.TemporaryDirectory() as directory:
            release = Path(directory) / 'release'

            class SlowOutput(io.StringIO):
                def write(self, value):
                    if 'ready' in value:
                        release.touch()
                        time.sleep(2.1)
                    return super().write(value)

            code = (
                "import pathlib,time,os; print('ready', flush=True); "
                f"p=pathlib.Path({str(release)!r})\n"
                "while not p.exists(): time.sleep(.01)\n"
                "os.write(1, b'final traceback\\n\\xe2\\x82'); time.sleep(30)"
            )
            output = SlowOutput()
            with contextlib.redirect_stdout(output):
                result, captured = run_ci_tests._run_streaming(
                    [sys.executable, '-u', '-c', code], timeout=2,
                )
            self.assertEqual(result, 124)
            self.assertIn('final traceback\n\ufffd', captured)

    def test_hung_unittest_emits_stack_before_timeout(self):
        from unittest.mock import patch
        import os
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / 'test_hung_fixture.py'
            module.write_text('import unittest, time\nclass Hung(unittest.TestCase):\n def test_wait(self):\n  time.sleep(30)\n')
            with patch.dict(os.environ, {"PYTHONPATH": directory}), contextlib.redirect_stdout(output):
                result, captured = run_ci_tests._run_streaming(
                    run_ci_tests._test_command(['test_hung_fixture'], traceback_interval=.1),
                    timeout=2,
                )
        self.assertEqual(result, 124)
        self.assertIn('test_wait (test_hung_fixture.Hung.test_wait)', captured)
        self.assertIn('Timeout (', captured)
        self.assertIn('test_hung_fixture.py", line 4 in test_wait', captured)

    def test_main_preserves_failure_details_from_streamed_stderr(self):
        from unittest.mock import patch
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / 'test_runner_fixture.py'
            module.write_text('import unittest\nclass Failure(unittest.TestCase):\n def test_bad(self):\n  self.fail("100% broken")\n')
            import os
            env = dict(os.environ, PYTHONPATH=directory)
            with patch.dict(os.environ, env), patch.object(run_ci_tests, 'TEST_MODULES', ('test_runner_fixture',)), patch.object(sys, 'platform', 'darwin'), contextlib.redirect_stdout(output):
                result = run_ci_tests.main()
        self.assertEqual(result, 1)
        self.assertIn('::error title=Automated test failure::test_bad (test_runner_fixture.Failure.test_bad)', output.getvalue())
        self.assertIn('AssertionError: 100%25 broken', output.getvalue())


if __name__ == '__main__':
    unittest.main()

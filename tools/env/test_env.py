"""Pinned-environment regression tests; run by the local gate inside Linux."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


def module(name):
    spec = importlib.util.spec_from_file_location('env_' + name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


installer = module('install')
launcher = module('run')
checker = module('check')


class EnvironmentTests(unittest.TestCase):
    def test_nonformal_mode_never_calls_solver(self):
        with patch.object(checker, 'run') as run:
            self.assertEqual(checker.solver_controls(skip=True), 'not run (explicit no-formal request)')
            run.assert_not_called()

    def test_default_solver_controls_and_bad_results(self):
        with patch.object(checker, 'run', side_effect=['unsat', 'sat']) as run:
            self.assertEqual(checker.solver_controls(), 'pass')
            self.assertEqual(run.call_count, 2)
        for replies in (['sat'], ['unsat', 'unsat']):
            with patch.object(checker, 'run', side_effect=replies):
                with self.assertRaises(RuntimeError): checker.solver_controls()

    def setUp(self):
        output = Path(__file__).resolve().parents[2] / 'build/test_env'
        output.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=output)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_download_checksum_and_corrupt_cache(self):
        source = self.root/'source'; source.write_bytes(b'known content')
        item = {'name': 'test', 'url': source.as_uri(), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        dest = self.root/'download'; dest.write_bytes(b'corrupt cache')
        installer.fetch(item, dest)
        self.assertEqual(dest.read_bytes(), b'known content')
        item['sha256'] = '0'*64
        with self.assertRaisesRegex(RuntimeError, 'CHECKSUM'): installer.fetch(item, dest)

    def setup_launcher(self):
        env = self.root/'tools/env'; env.mkdir(parents=True)
        state = self.root/'build/env'; state.mkdir(parents=True)
        lock = {'base': 'base@sha256:abc', 'certificate_base': 'trust@sha256:def',
                'apt_snapshot': 'date', 'platform': 'linux/amd64'}
        (env/'lock.json').write_text(json.dumps(lock))
        (env/'Dockerfile').write_text('base@sha256:abc trust@sha256:def date')
        for attr, value in [('ROOT', self.root), ('ENV', env), ('STATE', state)]:
            patcher = patch.object(launcher, attr, value); patcher.start(); self.addCleanup(patcher.stop)
        (state/'image.json').write_text(json.dumps({'image': 'sha256:immutable', 'inputs_sha256': launcher.fingerprint()}))
        return env, state

    def test_immutable_image_and_only_repository_mount(self):
        self.setup_launcher()
        with patch.object(sys, 'argv', ['run.py', 'run', '--', 'python3', 'tools/ci.py']), patch.object(launcher.subprocess, 'call', return_value=7) as call:
            self.assertEqual(launcher.main(), 7)
        command = call.call_args.args[0]
        self.assertIn('sha256:immutable', command)
        self.assertEqual(command.count('--mount'), 1)
        self.assertEqual(command[command.index('--mount')+1], f'type=bind,source={self.root},target=/work')
        self.assertEqual(command[command.index('--network')+1], 'none')

    def test_changed_inputs_reject_run(self):
        env, _ = self.setup_launcher(); (env/'Dockerfile').write_text('base@sha256:abc trust@sha256:def date changed')
        with patch.object(sys, 'argv', ['run.py', 'run']), patch.object(launcher.subprocess, 'call') as call, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): launcher.main()
            call.assert_not_called()

    def test_missing_receipt_reject_run(self):
        _, state = self.setup_launcher(); (state/'image.json').unlink()
        with patch.object(sys, 'argv', ['run.py', 'run']), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): launcher.main()

    def test_changes_during_build_reject_receipt(self):
        env, state = self.setup_launcher()
        (state/'image-id.txt').write_text('sha256:new')
        def changed():
            (env/'new-input').write_text('changed while building')
            return 0
        with patch.object(sys, 'argv', ['run.py', 'build']), patch.object(launcher.subprocess, 'Popen') as process:
            process.return_value.stdout = []
            process.return_value.wait.side_effect = changed
            with self.assertRaisesRegex(RuntimeError, 'changed during build'): launcher.main()
        self.assertEqual(json.loads((state/'image.json').read_text())['image'], 'sha256:immutable')


if __name__ == '__main__': unittest.main()

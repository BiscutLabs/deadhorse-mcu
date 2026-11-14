"""Behavioral fixtures: each isolated violation and its valid counterpart."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from check_structure import check

OUTPUT = Path(__file__).resolve().parents[1] / 'build/test_structure'


class StructureTests(unittest.TestCase):
    def setUp(self):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=OUTPUT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, path, text=''):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
        return dest

    def block(self, name='demo'):
        self.put(f'hw/ip/{name}/README.md')
        self.put(f'hw/ip/{name}/src/main/scala/Demo.scala')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.STDOUT)

    def expect(self, rule=None):
        found = check(self.root)
        self.assertEqual([line.split()[0] for line in found], [rule] if rule else [])

    def test_root_bad(self): self.put('unexpected.txt'); self.expect('ROOT_FILES')
    def test_root_clean(self): self.put('README.md'); self.expect()
    def test_shape_bad(self): self.put('hw/ip/demo/README.md'); self.expect('BLOCK_SHAPE')
    def test_shape_clean(self): self.block(); self.expect()
    def test_name_bad(self): self.block('BadName'); self.expect('BLOCK_NAME')
    def test_name_clean(self): self.block('good_name2'); self.block('_template'); self.expect()
    def test_rtl_bad(self): self.put('hw/lib/src/main/scala/readme.txt'); self.expect('RTL_ONLY')
    def test_rtl_clean(self): self.put('hw/lib/src/test/scala/.gitkeep'); self.expect()
    def test_sv_bad(self): self.put('hw/top/chip/chip.sv'); self.expect('SV_VENDOR_ONLY')
    def test_sv_clean(self): self.put('tools/spikes/test/design.sv'); self.expect()
    def test_symlink_bad(self):
        dest = self.put('docs/target.txt')
        (dest.parent/'link').symlink_to('target.txt'); self.expect('NO_SYMLINK')
    def test_symlink_clean(self): self.put('docs/regular.txt'); self.expect()
    def test_large_bad(self): self.put('docs/large.txt', 'x' * (1024*1024+1)); self.expect('NO_LARGE')
    def test_large_clean(self): self.put('docs/boundary.txt', 'x' * (1024*1024)); self.expect()
    def test_large_allow(self):
        self.put('docs/large.txt', 'x' * (1024*1024+1))
        self.put('tools/structure_allow.json', '{"large": ["docs/large.txt"]}'); self.expect()
    def test_generated_bad(self): self.put('dv/wave.vcd'); self.expect('NO_GENERATED')
    def test_generated_clean(self): self.put('docs/results.md'); self.expect()
    def test_wrapper_bad(self): self.put('tools/build.ps1'); self.expect('NO_PLATFORM_WRAPPER')
    def test_wrapper_clean(self): self.put('tools/build.py'); self.expect()
    def test_links_bad(self): self.put('docs/page.md', '[missing](lost.md)'); self.expect('REL_LINKS')
    def test_links_clean(self):
        self.put('docs/other page.md')
        self.put('docs/page.md', '[a](other%20page.md#anchor) [b](https://example.org) [c](#local)\n'
                 '[d](<other page.md> "title")\n```md\n[code](missing.md)\n```\n`[code](missing.md)`')
        self.expect()
    def test_links_reference_bad(self): self.put('docs/page.md', '[label]: lost.md\n'); self.expect('REL_LINKS')
    def test_links_parentheses_clean(self):
        self.put('docs/file(name).md')
        self.put('docs/page.md', '[a](file(name).md) [b](file\\(name\\).md)\n[c]: file(name).md\n')
        self.expect()
    def test_links_parentheses_missing(self):
        self.put('docs/page.md', '[a](missing(name).md)'); self.expect('REL_LINKS')
    def test_links_encoded_delimiters(self):
        self.put('docs/file#name.md'); self.put('docs/file?name.md')
        self.put('docs/page.md', '[a](file%23name.md) [b](file%3Fname.md#anchor)'); self.expect()
    def test_links_absolute(self):
        for target in ('/etc/passwd', 'C:/file.txt', '%2Fetc/passwd'):
            with self.subTest(target=target):
                self.put('docs/page.md', f'[a]({target})'); self.expect('REL_LINKS')
    def test_vendor_bad(self): self.put('hw/vendor/demo/README.md'); self.expect('VENDOR_LOCK')
    def test_vendor_clean(self): self.put('hw/vendor/demo/demo.lock.json', '{}'); self.expect()
    def test_git_only_tracked(self):
        self.git('init', '-q'); self.put('README.md'); self.git('add', 'README.md')
        self.put('unexpected.txt'); self.expect()
        self.assertEqual(len(check(self.root, include_untracked=True)), 1)
    def test_git_tracked_build(self):
        self.git('init', '-q'); self.put('build/result.txt'); self.git('add', 'build/result.txt')
        self.expect('NO_GENERATED')
    def test_git_symlink_mode_on_plain_file(self):
        self.git('init', '-q')
        self.put('docs/target.txt'); self.put('docs/link', 'target.txt')
        oid = self.git('hash-object', '-w', 'docs/link').decode().strip()
        self.git('update-index', '--add', '--cacheinfo', f'120000,{oid},docs/link')
        self.expect('NO_SYMLINK')
    def test_nongit_ignored_outputs(self):
        for name in ('build', 'scratch', '.git'): self.put(f'{name}/wave.vcd')
        self.expect()
    def test_obj_dir(self): self.put('dv/obj_dir/generated.cpp'); self.expect('NO_GENERATED')
    def test_cli_failure(self):
        self.put('unexpected.txt')
        p = subprocess.run(['python3', str(Path(__file__).with_name('check_structure.py')), str(self.root)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn('ROOT_FILES unexpected.txt:', p.stdout)


if __name__ == '__main__': unittest.main()

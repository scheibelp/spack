import spack
from spack import *
from spack.version import Version, VersionList
from spack.package import Package

import os
import shutil
from tempfile import mkdtemp
import unittest


class TestPackage(Package):
    version('1.1', 'hash1.1')
    version('1.2', 'hash1.1')

    url = "http://example.com/testpackage-1.1"

    def setup(self, stage, patch_fun=None, patches=None):
        if patch_fun:
            self.patch = patch_fun
        if patches:
            self.patches = patches

        self.did_stage = False
        self.test_stage = stage

    def do_stage(self):
        self.did_stage = True

    @property
    def is_extension(self):
        return False

    @property
    def stage(self):
        return self.test_stage


class MockPatch(object):
    def apply(self):
        pass


class MockSpec(object):
    def __init__(self):
        self.versions = VersionList([Version('1.1')])
        self.version = self.versions.highest()
        self.concrete = True


class MockStage(object):
    def __init__(self, src_dir):
        self.src_dir = src_dir
        self.restaged = False
    
    def restage(self):
        self.restaged = True

    def chdir_to_source(self):
        os.chdir(self.src_dir)

    @property
    def source_path(self):
        return self.src_dir


class PackageTest(unittest.TestCase):
    def setUp(self):
        super(PackageTest, self).setUp()
        self.stage_src_dir = mkdtemp()
        self.test_stage = MockStage(self.stage_src_dir)

    def tearDown(self):
        super(PackageTest, self).tearDown()
        shutil.rmtree(self.stage_src_dir, True)

    def test_patch_nothing_to_apply(self):
        spec = MockSpec()
        pkg = TestPackage(spec)
        pkg.setup(self.test_stage)
        pkg.do_patch()

    def test_patch_has_patch_function(self):
        spec = MockSpec()
        pkg = TestPackage(spec)

        self.applied_patch = False

        def patch_fun():
            self.applied_patch = True

        pkg.setup(self.test_stage, patch_fun=patch_fun)
        pkg.do_patch()

        self.assertTrue(self.applied_patch)

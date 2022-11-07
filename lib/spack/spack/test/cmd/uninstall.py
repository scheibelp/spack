# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import pytest
import sys

import llnl.util.tty as tty

import spack.store
from spack.main import SpackCommand, SpackCommandError

uninstall = SpackCommand("uninstall")
install = SpackCommand("install")


class MockArgs(object):
    def __init__(self, packages, all=False, force=False, dependents=False):
        self.packages = packages
        self.all = all
        self.force = force
        self.dependents = dependents
        self.yes_to_all = True


@pytest.mark.db
def test_multiple_matches(mutable_database):
    """Test unable to uninstall when multiple matches."""
    with pytest.raises(SpackCommandError):
        uninstall("-y", "mpileaks")


@pytest.mark.db
def test_installed_dependents(mutable_database):
    """Test can't uninstall when there are installed dependents."""
    with pytest.raises(SpackCommandError):
        uninstall("-y", "libelf")


@pytest.mark.db
def test_recursive_uninstall(mutable_database):
    """Test recursive uninstall."""
    uninstall("-y", "-a", "--dependents", "callpath")

    all_specs = spack.store.layout.all_specs()
    assert len(all_specs) == 9
    # query specs with multiple configurations
    mpileaks_specs = [s for s in all_specs if s.satisfies("mpileaks")]
    callpath_specs = [s for s in all_specs if s.satisfies("callpath")]
    mpi_specs = [s for s in all_specs if s.satisfies("mpi")]

    assert len(mpileaks_specs) == 0
    assert len(callpath_specs) == 0
    assert len(mpi_specs) == 3


@pytest.mark.db
@pytest.mark.regression("3690")
@pytest.mark.parametrize("constraint,expected_number_of_specs", [("dyninst", 8), ("libelf", 6)])
def test_uninstall_spec_with_multiple_roots(
    constraint, expected_number_of_specs, mutable_database
):
    uninstall("-y", "-a", "--dependents", constraint)

    all_specs = spack.store.layout.all_specs()
    assert len(all_specs) == expected_number_of_specs


@pytest.mark.db
@pytest.mark.parametrize("constraint,expected_number_of_specs", [("dyninst", 14), ("libelf", 14)])
def test_force_uninstall_spec_with_ref_count_not_zero(
    constraint, expected_number_of_specs, mutable_database
):
    uninstall("-f", "-y", constraint)

    all_specs = spack.store.layout.all_specs()
    assert len(all_specs) == expected_number_of_specs


@pytest.mark.db
def test_force_uninstall_and_reinstall_by_hash(mutable_database):
    """Test forced uninstall and reinstall of old specs."""
    # this is the spec to be removed
    callpath_spec = spack.store.db.query_one("callpath ^mpich")
    dag_hash = callpath_spec.dag_hash()

    # ensure can look up by hash and that it's a dependent of mpileaks
    def validate_callpath_spec(installed):
        assert installed is True or installed is False

        specs = spack.store.db.get_by_hash(dag_hash, installed=installed)
        assert len(specs) == 1 and specs[0] == callpath_spec

        specs = spack.store.db.get_by_hash(dag_hash[:7], installed=installed)
        assert len(specs) == 1 and specs[0] == callpath_spec

        specs = spack.store.db.get_by_hash(dag_hash, installed=any)
        assert len(specs) == 1 and specs[0] == callpath_spec

        specs = spack.store.db.get_by_hash(dag_hash[:7], installed=any)
        assert len(specs) == 1 and specs[0] == callpath_spec

        specs = spack.store.db.get_by_hash(dag_hash, installed=not installed)
        assert specs is None

        specs = spack.store.db.get_by_hash(dag_hash[:7], installed=not installed)
        assert specs is None

        mpileaks_spec = spack.store.db.query_one("mpileaks ^mpich")
        assert callpath_spec in mpileaks_spec

        spec = spack.store.db.query_one("callpath ^mpich", installed=installed)
        assert spec == callpath_spec

        spec = spack.store.db.query_one("callpath ^mpich", installed=any)
        assert spec == callpath_spec

        spec = spack.store.db.query_one("callpath ^mpich", installed=not installed)
        assert spec is None

    validate_callpath_spec(True)

    uninstall("-y", "-f", "callpath ^mpich")

    # ensure that you can still look up by hash and see deps, EVEN though
    # the callpath spec is missing.
    validate_callpath_spec(False)

    # BUT, make sure that the removed callpath spec is not in queries
    def db_specs():
        all_specs = spack.store.layout.all_specs()
        return (
            all_specs,
            [s for s in all_specs if s.satisfies("mpileaks")],
            [s for s in all_specs if s.satisfies("callpath")],
            [s for s in all_specs if s.satisfies("mpi")],
        )

    all_specs, mpileaks_specs, callpath_specs, mpi_specs = db_specs()
    total_specs = len(all_specs)
    assert total_specs == 14
    assert len(mpileaks_specs) == 3
    assert len(callpath_specs) == 2
    assert len(mpi_specs) == 3

    # Now, REINSTALL the spec and make sure everything still holds
    install("--fake", "/%s" % dag_hash[:7])

    validate_callpath_spec(True)

    all_specs, mpileaks_specs, callpath_specs, mpi_specs = db_specs()
    assert len(all_specs) == total_specs + 1  # back to total_specs+1
    assert len(mpileaks_specs) == 3
    assert len(callpath_specs) == 3  # back to 3
    assert len(mpi_specs) == 3


@pytest.mark.db
@pytest.mark.regression("15773")
def test_in_memory_consistency_when_uninstalling(mutable_database, monkeypatch):
    """Test that uninstalling doesn't raise warnings"""

    def _warn(*args, **kwargs):
        raise RuntimeError("a warning was triggered!")

    monkeypatch.setattr(tty, "warn", _warn)
    # Now try to uninstall and check this doesn't trigger warnings
    uninstall("-y", "-a")


import spack.environment

pytest.mark.skipif(sys.platform == "win32", reason="Envs unsupported on Windows")
class TestUninstallFromEnv(object):
    env = SpackCommand("env")
    add = SpackCommand("add")
    concretize = SpackCommand("concretize")
    find = SpackCommand("find")

    @pytest.fixture
    def environment_setup(self, mutable_mock_env_path, config, mock_packages, mutable_database):
        TestUninstallFromEnv.env("create", "e1")
        e1 = spack.environment.read("e1")
        with e1:
            TestUninstallFromEnv.add("dt-diamond-left")
            TestUninstallFromEnv.add("dt-diamond-bottom")
            TestUninstallFromEnv.concretize()
            install("--fake")

        TestUninstallFromEnv.env("create", "e2")
        e2 = spack.environment.read("e2")
        with e2:
            TestUninstallFromEnv.add("dt-diamond-right")
            TestUninstallFromEnv.add("dt-diamond-bottom")
            TestUninstallFromEnv.concretize()
            install("--fake")

    def test_basic_env_sanity(self, environment_setup):
        for env_name in ["e1", "e2"]:
            e = spack.environment.read(env_name)
            with e:
                for _, concretized_spec in e.concretized_specs():
                    assert concretized_spec.package.installed

    def test_uninstall_force_dependency_shared_between_envs(self, environment_setup):
        e1 = spack.environment.read("e1")
        with e1:
            uninstall("-f", "-y", "--dependents", "dt-diamond-bottom")

            for _, concretized_spec in e1.concretized_specs():
                assert not concretized_spec.package.installed

        # Everything in e2 depended on dt-diamond-bottom, so should also
        # have been uninstalled
        e2 = spack.environment.read("e2")
        with e2:
            for _, concretized_spec in e2.concretized_specs():
                assert not concretized_spec.package.installed

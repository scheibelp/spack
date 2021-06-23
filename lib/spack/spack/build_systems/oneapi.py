# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

"""Common utilities for managing intel oneapi packages.

"""

import getpass
import shutil
import platform
from os.path import basename, dirname, isdir

from spack.package import Package
from spack.util.environment import EnvironmentModifications
from spack.util.executable import Executable

from llnl.util.filesystem import find_headers, find_libraries, join_path


class IntelOneApiPackage(Package):
    """Base class for Intel oneAPI packages."""

    homepage = 'https://software.intel.com/oneapi'

    phases = ['install']

    # oneAPI license does not allow mirroring outside of the
    # organization (e.g. University/Company).
    redistribute_source = False

    @property
    def component_dir(self):
        """Subdirectory for this component in the install prefix."""
        raise NotImplementedError

    @property
    def component_path(self):
        """Path to component <prefix>/<component>/<version>."""
        return join_path(self.prefix, self.component_dir, str(self.spec.version))

    def install(self, spec, prefix, installer_path=None):
        """Shared install method for all oneapi packages."""

        # intel-oneapi-compilers overrides the installer_path when
        # installing fortran, which comes from a spack resource
        if installer_path is None:
            installer_path = basename(self.url_for_version(spec.version))

        if platform.system() == 'Linux':
            # Intel installer assumes and enforces that all components
            # are installed into a single prefix. Spack wants to
            # install each component in a separate prefix. The
            # installer mechanism is implemented by saving install
            # information in a directory called installercache for
            # future runs. The location of the installercache depends
            # on the userid. For root it is always in /var/intel. For
            # non-root it is in $HOME/intel.
            #
            # The method for preventing this install from interfering
            # with other install depends on the userid. For root, we
            # delete the installercache before and after install. For
            # non root we redefine the HOME environment variable.
            if getpass.getuser() == 'root':
                shutil.rmtree('/var/intel/installercache', ignore_errors=True)

            bash = Executable('bash')

            # Installer writes files in ~/intel set HOME so it goes to prefix
            bash.add_default_env('HOME', prefix)

            bash(installer_path,
                 '-s', '-a', '-s', '--action', 'install',
                 '--eula', 'accept',
                 '--install-dir', prefix)

            if getpass.getuser() == 'root':
                shutil.rmtree('/var/intel/installercache', ignore_errors=True)

        # Some installers have a bug and do not return an error code when failing
        if not isdir(join_path(prefix, self.component_dir)):
            raise RuntimeError('install failed')

    def setup_run_environment(self, env):
        """Adds environment variables to the generated module file.

        These environment variables come from running:

        .. code-block:: console

           $ source {prefix}/{component}/{version}/env/vars.sh
        """
        env.extend(EnvironmentModifications.from_sourcing_file(
            join_path(self.component_path, 'env', 'vars.sh')))


class IntelOneApiLibraryPackage(IntelOneApiPackage):
    """Base class for Intel oneAPI library packages."""

    @property
    def headers(self):
        include_path = join_path(self.component_path, 'include')
        return find_headers('*', include_path, recursive=True)

    @property
    def libs(self):
        lib_path = join_path(self.component_path, 'lib', 'intel64')
        lib_path = lib_path if isdir(lib_path) else dirname(lib_path)
        return find_libraries('*', root=lib_path, shared=True, recursive=True)

##############################################################################
# Copyright (c) 2013, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory.
#
# This file is part of Spack.
# Written by Todd Gamblin, tgamblin@llnl.gov, All rights reserved.
# LLNL-CODE-647188
#
# For details, see https://github.com/llnl/spack
# Please also see the LICENSE file for our notice and the LGPL.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License (as published by
# the Free Software Foundation) version 2.1 dated February 1999.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the IMPLIED WARRANTY OF
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the terms and
# conditions of the GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
##############################################################################
import argparse
import os

import llnl.util.tty as tty

import spack
import spack.cmd
from spack import join_path, mkdirp
from spack.directory_layout import YamlDirectoryLayout, _check_concrete

description = "Build and install packages"

def setup_parser(subparser):
    subparser.add_argument(
        '-i', '--ignore-dependencies', action='store_true', dest='ignore_deps',
        help="Do not try to install dependencies of requested packages.")
    subparser.add_argument(
        '-j', '--jobs', action='store', type=int,
        help="Explicitly set number of make jobs.  Default is #cpus.")
    subparser.add_argument(
        '--keep-prefix', action='store_true', dest='keep_prefix',
        help="Don't remove the install prefix if installation fails.")
    subparser.add_argument(
        '--keep-stage', action='store_true', dest='keep_stage',
        help="Don't remove the build stage if installation succeeds.")
    subparser.add_argument(
        '-n', '--no-checksum', action='store_true', dest='no_checksum',
        help="Do not check packages against checksum")
    subparser.add_argument(
        '-v', '--verbose', action='store_true', dest='verbose',
        help="Display verbose build output while installing.")
    subparser.add_argument(
        '--fake', action='store_true', dest='fake',
        help="Fake install.  Just remove the prefix and touch a fake file in it.")
    subparser.add_argument(
        '--destdir', dest='destdir',
        help="Install to a different location than the prefix")
    subparser.add_argument(
        '--install-root', dest='install_root',
        help="Install to the specified directory (and check this directory for prior installs)")
    subparser.add_argument(
        'packages', nargs=argparse.REMAINDER, help="specs of packages to install")


class CustomDirectoryLayout(YamlDirectoryLayout):
    def __init__(self, root, destDir=None):
        super(CustomDirectoryLayout, self).__init__(root)
        self.destDir = destDir

    #TODO: specs will have to start generating different prefixes depending on
    #whether they are version-agnostic
    def relative_path_for_spec(self, spec):
        _check_concrete(spec)
        dir_name = "%s-%s-%s" % (
            spec.name,
            spec.version,
            spec.dag_hash(self.hash_len))

        #path = join_path(
        #    spec.architecture,
        #    "%s-%s" % (spec.compiler.name, spec.compiler.version),
        #    dir_name)

        return dir_name

    def _redirect(self, path):
        """
        For operations in directory_layout that do writes.
        """
        if self.destDir:
            if path.startswith(os.sep):
                path = path[len(os.sep):]
            return join_path(self.destDir, path)
        else:
            return path

    def build_log_path(self, spec):
        return self._redirect(super(CustomDirectoryLayout, self).build_log_path(spec))

    def create_install_directory(self, spec):
        _check_concrete(spec)

        path = self._redirect(self.path_for_spec(spec))
        spec_file_path = self._redirect(self.spec_file_path(spec))

        if os.path.isdir(path):
            if not os.path.isfile(spec_file_path):
                raise InconsistentInstallDirectoryError(
                    'No spec file found at path %s' % spec_file_path)

            installed_spec = self.read_spec(spec_file_path)
            if installed_spec == self.spec:
                raise InstallDirectoryAlreadyExistsError(path)

            if spec.dag_hash() == installed_spec.dag_hash():
                raise SpecHashCollisionError(installed_hash, spec_hash)
            else:
                raise InconsistentInstallDirectoryError(
                    'Spec file in %s does not match hash!' % spec_file_path)

        print self._redirect(self.metadata_path(spec))
        mkdirp(self._redirect(self.metadata_path(spec)))
        self.write_spec(spec, spec_file_path)

def install(parser, args):
    if not args.packages:
        tty.die("install requires at least one package argument")

    if args.install_root:
        spack.install_layout = CustomDirectoryLayout(args.install_root, args.destdir)

    if args.jobs is not None:
        if args.jobs <= 0:
            tty.die("The -j option must be a positive integer!")

    if args.no_checksum:
        spack.do_checksum = False        # TODO: remove this global.

    specs = spack.cmd.parse_specs(args.packages, concretize=True)
    for spec in specs:   
        package = spack.repo.get(spec)
        if args.destdir:
            #TODO: need to make sure that all dependencies are already installed
            spec.install_root = join_path(args.destdir, spack.install_layout.root)
            spack.destdir = args.destdir
        with spack.installed_db.write_transaction():
            package.do_install(
                keep_prefix=args.keep_prefix,
                keep_stage=args.keep_stage,
                ignore_deps=args.ignore_deps,
                make_jobs=args.jobs,
                verbose=args.verbose,
                fake=args.fake)

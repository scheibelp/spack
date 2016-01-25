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

import llnl.util.tty as tty

import spack
import spack.cmd
from spack import join_path
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
        '--install-dir', dest='install_dir',
        help="Install to the specified directory (and check this directory for prior installs)")
    subparser.add_argument(
        'packages', nargs=argparse.REMAINDER, help="specs of packages to install")


class CustomDirectoryLayout(YamlDirectoryLayout):
    def __init__(self, root):
        super(CustomDirectoryLayout, self).__init__(root)

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


def install(parser, args):
    if not args.packages:
        tty.die("install requires at least one package argument")

    if args.install_dir:
        spack.install_layout = CustomDirectoryLayout(args.install_dir)

    if args.jobs is not None:
        if args.jobs <= 0:
            tty.die("The -j option must be a positive integer!")

    if args.no_checksum:
        spack.do_checksum = False        # TODO: remove this global.

    specs = spack.cmd.parse_specs(args.packages, concretize=True)

    topSpec = iter(specs).next()
    for spec in topSpec.traverse(order='post'):
        package = spack.db.get(spec)
        print package.name, package.installed
        print package.prefix

    for spec in specs:
        package = spack.db.get(spec)
        with spack.installed_db.write_transaction():
            package.do_install(
                keep_prefix=args.keep_prefix,
                keep_stage=args.keep_stage,
                ignore_deps=args.ignore_deps,
                make_jobs=args.jobs,
                verbose=args.verbose,
                fake=args.fake)

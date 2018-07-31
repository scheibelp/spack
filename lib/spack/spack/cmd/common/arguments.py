##############################################################################
# Copyright (c) 2013-2018, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory.
#
# This file is part of Spack.
# Created by Todd Gamblin, tgamblin@llnl.gov, All rights reserved.
# LLNL-CODE-647188
#
# For details, see https://github.com/spack/spack
# Please also see the NOTICE and LICENSE files for our notice and the LGPL.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License (as
# published by the Free Software Foundation) version 2.1, February 1999.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the IMPLIED WARRANTY OF
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the terms and
# conditions of the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
##############################################################################

import argparse

import spack.cmd
import spack.config
import spack.environment
import spack.modules
import spack.spec
import spack.store
from spack.util.pattern import Args

__all__ = ['add_common_arguments']

_arguments = {}


def add_common_arguments(parser, list_of_arguments):
    """Extend a parser with extra arguments

    Args:
        parser: parser to be extended
        list_of_arguments: arguments to be added to the parser
    """
    for argument in list_of_arguments:
        if argument not in _arguments:
            message = 'Trying to add non existing argument "{0}" to a command'
            raise KeyError(message.format(argument))
        x = _arguments[argument]
        parser.add_argument(*x.flags, **x.kwargs)


class ConstraintAction(argparse.Action):
    """Constructs a list of specs based on constraints from the command line

    An instance of this class is supposed to be used as an argument action
    in a parser. It will read a constraint and will attach a function to the
    arguments that accepts optional keyword arguments.

    To obtain the specs from a command the function must be called.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        # Query specs from command line
        self.values = values
        namespace.constraint = values
        namespace.specs = self._specs
        self.env = None if not hasattr(namespace, 'env') else namespace.env

    def _specs(self, **kwargs):
        qspecs = spack.cmd.parse_specs(self.values)

        if self.env:
            kwargs['hashes'] = set(self.env.specs_by_hash.keys())

        # return everything for an empty query.
        if not qspecs:
            return spack.store.db.query(**kwargs)

        # Return only matching stuff otherwise.
        specs = {}
        for spec in qspecs:
            for s in spack.store.db.query(spec, **kwargs):
                # This is fast for already-concrete specs
                specs[s.dag_hash()] = s

        return sorted(specs.values())


class EnvAction(argparse.Action):
    """Records the environment to which a command applies."""
    def __call__(self, parser, namespace, env_name, option_string=None):
        namespace.env = spack.environment.read(env_name)


_arguments['env'] = Args(
    '-e', '--env', action=EnvAction, default=None,
    help="run this command on a specific environment")

_arguments['constraint'] = Args(
    'constraint', nargs=argparse.REMAINDER, action=ConstraintAction,
    help='constraint to select a subset of installed packages')

_arguments['yes_to_all'] = Args(
    '-y', '--yes-to-all', action='store_true', dest='yes_to_all',
    help='assume "yes" is the answer to every confirmation request')

_arguments['recurse_dependencies'] = Args(
    '-r', '--dependencies', action='store_true', dest='recurse_dependencies',
    help='recursively traverse spec dependencies')

_arguments['recurse_dependents'] = Args(
    '-R', '--dependents', action='store_true', dest='dependents',
    help='also uninstall any packages that depend on the ones given '
    'via command line')

_arguments['clean'] = Args(
    '--clean',
    action='store_false',
    default=spack.config.get('config:dirty'),
    dest='dirty',
    help='unset harmful variables in the build environment (default)')

_arguments['dirty'] = Args(
    '--dirty',
    action='store_true',
    default=spack.config.get('config:dirty'),
    dest='dirty',
    help='preserve user environment in the spack build environment (danger!)')

_arguments['long'] = Args(
    '-l', '--long', action='store_true',
    help='show dependency hashes as well as versions')

_arguments['very_long'] = Args(
    '-L', '--very-long', action='store_true',
    help='show full dependency hashes as well as versions')

_arguments['jobs'] = Args(
    '-j', '--jobs', action='store', type=int, dest='jobs',
    help="explicitely set number of make jobs. default is #cpus")

_arguments['tags'] = Args(
    '-t', '--tags', action='append',
    help='filter a package query by tags')

_arguments['jobs'] = Args(
    '-j', '--jobs', action='store', type=int, dest="jobs",
    help="explicitly set number of make jobs, default is #cpus.")

_arguments['install_status'] = Args(
    '-I', '--install-status', action='store_true', default=False,
    help='show install status of packages. packages can be: '
         'installed [+], missing and needed by an installed package [-], '
         'or not installed (no annotation)')

_arguments['no_checksum'] = Args(
    '-n', '--no-checksum', action='store_true', default=False,
    help="do not use checksums to verify downloadeded files (unsafe)")

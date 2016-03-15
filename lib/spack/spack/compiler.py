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
import os
import re
import itertools
from datetime import datetime

import llnl.util.tty as tty
from llnl.util.lang import memoized
from llnl.util.filesystem import join_path

import spack.error
import spack.spec
from spack.util.multiproc import parmap
from spack.util.executable import *
from spack.util.environment import get_path
from spack.version import Version

__all__ = ['Compiler', 'get_compiler_version']

def _verify_executables(*paths):
    for path in paths:
        if not os.path.isfile(path) and os.access(path, os.X_OK):
            raise CompilerAccessError(path)


_version_cache = {}

def get_compiler_version(compiler_path, version_arg, regex='(.*)'):
    if not compiler_path in _version_cache:
        compiler = Executable(compiler_path)
        output = compiler(version_arg, output=str, error=str)

        match = re.search(regex, output)
        _version_cache[compiler_path] = match.group(1) if match else 'unknown'

    return _version_cache[compiler_path]


def dumpversion(compiler_path):
    """Simple default dumpversion method -- this is what gcc does."""
    return get_compiler_version(compiler_path, '-dumpversion')


class Compiler(object):
    """This class encapsulates a Spack "compiler", which includes C,
       C++, and Fortran compilers.  Subclasses should implement
       support for specific compilers, their possible names, arguments,
       and how to identify the particular type of compiler."""

    # Subclasses use possible names of C compiler
    cc_names = []

    # Subclasses use possible names of C++ compiler
    cxx_names = []

    # Subclasses use possible names of Fortran 77 compiler
    f77_names = []

    # Subclasses use possible names of Fortran 90 compiler
    fc_names = []

    # Optional prefix regexes for searching for this type of compiler.
    # Prefixes are sometimes used for toolchains, e.g. 'powerpc-bgq-linux-'
    prefixes = []

    # Optional suffix regexes for searching for this type of compiler.
    # Suffixes are used by some frameworks, e.g. macports uses an '-mp-X.Y'
    # version suffix for gcc.
    suffixes = [r'-.*']

    # Names of generic arguments used by this compiler
    arg_rpath   = '-Wl,-rpath,%s'

    # argument used to get C++11 options
    cxx11_flag = "-std=c++11"


    def __init__(self, cspec, cc, cxx, f77, fc):
        def check(exe):
            if exe is None:
                return None
            _verify_executables(exe)
            return exe

        self.cc  = check(cc)
        self.cxx = check(cxx)
        self.f77 = check(f77)
        self.fc  = check(fc)

        self.spec = cspec


    @property
    def version(self):
        return self.spec.version

    #
    # Compiler classes have methods for querying the version of
    # specific compiler executables.  This is used when discovering compilers.
    #
    # Compiler *instances* are just data objects, and can only be
    # constructed from an actual set of executables.
    #

    @classmethod
    def default_version(cls, cc):
        """Override just this to override all compiler version functions."""
        return dumpversion(cc)

    @classmethod
    def cc_version(cls, cc):
        return cls.default_version(cc)

    @classmethod
    def cxx_version(cls, cxx):
        return cls.default_version(cxx)

    @classmethod
    def f77_version(cls, f77):
        return cls.default_version(f77)

    @classmethod
    def fc_version(cls, fc):
        return cls.default_version(fc)


    @classmethod
    def _find_matches_in_path(cls, compiler_names, detect_version, *path):
        """Finds compilers in the paths supplied.

           Looks for all combinations of ``compiler_names`` with the
           ``prefixes`` and ``suffixes`` defined for this compiler
           class.  If any compilers match the compiler_names,
           prefixes, or suffixes, uses ``detect_version`` to figure
           out what version the compiler is.

           This returns a dict with compilers grouped by (prefix,
           suffix, version) tuples.  This can be further organized by
           find().
        """
        if not path:
            path = get_path('PATH')

        prefixes = [''] + cls.prefixes
        suffixes = [''] + cls.suffixes

        checks = []
        for directory in path:
            if not (os.path.isdir(directory) and
                    os.access(directory, os.R_OK | os.X_OK)):
                continue

            files = os.listdir(directory)
            for exe in files:
                full_path = join_path(directory, exe)

                prod = itertools.product(prefixes, compiler_names, suffixes)
                for pre, name, suf in prod:
                    regex = r'^(%s)%s(%s)$' % (pre, re.escape(name), suf)

                    match = re.match(regex, exe)
                    if match:
                        key = (full_path,) + match.groups()
                        checks.append(key)

        def check(key):
            try:
                full_path, prefix, suffix = key
                version = detect_version(full_path)
                return (version, prefix, suffix, full_path)
            except ProcessError, e:
                tty.debug("Couldn't get version for compiler %s" % full_path, e)
                return None
            except Exception, e:
                # Catching "Exception" here is fine because it just
                # means something went wrong running a candidate executable.
                tty.debug("Error while executing candidate compiler %s" % full_path,
                          "%s: %s" %(e.__class__.__name__, e))
                return None

        successful = [key for key in parmap(check, checks) if key is not None]
        return dict(((v, p, s), path) for v, p, s, path in successful)

    @classmethod
    def find(cls, *path):
        """Try to find this type of compiler in the user's
           environment. For each set of compilers found, this returns
           compiler objects with the cc, cxx, f77, fc paths and the
           version filled in.

           This will search for compilers with the names in cc_names,
           cxx_names, etc. and it will group them if they have common
           prefixes, suffixes, and versions.  e.g., gcc-mp-4.7 would
           be grouped with g++-mp-4.7 and gfortran-mp-4.7.
        """
        dicts = parmap(
            lambda t: cls._find_matches_in_path(*t),
            [(cls.cc_names,  cls.cc_version)  + tuple(path),
             (cls.cxx_names, cls.cxx_version) + tuple(path),
             (cls.f77_names, cls.f77_version) + tuple(path),
             (cls.fc_names,  cls.fc_version)  + tuple(path)])

        all_keys = set()
        for d in dicts:
            all_keys.update(d)

        compilers = {}
        for k in all_keys:
            ver, pre, suf = k

            # Skip compilers with unknown version.
            if ver == 'unknown':
                continue

            paths = tuple(pn[k] if k in pn else None for pn in dicts)
            spec = spack.spec.CompilerSpec(cls.name, ver)

            if ver in compilers:
                prev = compilers[ver]

                # prefer the one with more compilers.
                prev_paths = [prev.cc, prev.cxx, prev.f77, prev.fc]
                newcount  = len([p for p in paths      if p is not None])
                prevcount = len([p for p in prev_paths if p is not None])

                # Don't add if it's not an improvement over prev compiler.
                if newcount <= prevcount:
                    continue

            compilers[ver] = cls(spec, *paths)

        return list(compilers.values())


    def __repr__(self):
        """Return a string representation of the compiler toolchain."""
        return self.__str__()


    def __str__(self):
        """Return a string representation of the compiler toolchain."""
        return "%s(%s)" % (
            self.name, '\n     '.join((str(s) for s in (self.cc, self.cxx, self.f77, self.fc))))


class CompilerAccessError(spack.error.SpackError):
    def __init__(self, path):
        super(CompilerAccessError, self).__init__(
            "'%s' is not a valid compiler." % path)


class InvalidCompilerError(spack.error.SpackError):
    def __init__(self):
        super(InvalidCompilerError, self).__init__(
            "Compiler has no executables.")

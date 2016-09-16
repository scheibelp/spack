##############################################################################
# Copyright (c) 2013-2016, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory.
#
# This file is part of Spack.
# Created by Todd Gamblin, tgamblin@llnl.gov, All rights reserved.
# LLNL-CODE-647188
#
# For details, see https://github.com/llnl/spack
# Please also see the LICENSE file for our notice and the LGPL.
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
"""
This module contains all routines related to setting up the package
build environment.  All of this is set up by package.py just before
install() is called.

There are two parts to the build environment:

1. Python build environment (i.e. install() method)

   This is how things are set up when install() is called.  Spack
   takes advantage of each package being in its own module by adding a
   bunch of command-like functions (like configure(), make(), etc.) in
   the package's module scope.  Ths allows package writers to call
   them all directly in Package.install() without writing 'self.'
   everywhere.  No, this isn't Pythonic.  Yes, it makes the code more
   readable and more like the shell script from which someone is
   likely porting.

2. Build execution environment

   This is the set of environment variables, like PATH, CC, CXX,
   etc. that control the build.  There are also a number of
   environment variables used to pass information (like RPATHs and
   other information about dependencies) to Spack's compiler wrappers.
   All of these env vars are also set up here.

Skimming this module is a nice way to get acquainted with the types of
calls you can make from within the install() function.
"""
import glob
import os
import sys
import shutil
import multiprocessing
import platform

import llnl.util.tty as tty
from llnl.util.filesystem import *

import spack
from spack.environment import EnvironmentModifications, validate
from spack.util.environment import *
from spack.util.executable import Executable, which

#
# This can be set by the user to globally disable parallel builds.
#
SPACK_NO_PARALLEL_MAKE = 'SPACK_NO_PARALLEL_MAKE'

#
# These environment variables are set by
# set_build_environment_variables and used to pass parameters to
# Spack's compiler wrappers.
#
SPACK_ENV_PATH = 'SPACK_ENV_PATH'
SPACK_DEPENDENCIES = 'SPACK_DEPENDENCIES'
SPACK_PREFIX = 'SPACK_PREFIX'
SPACK_INSTALL = 'SPACK_INSTALL'
SPACK_DEBUG = 'SPACK_DEBUG'
SPACK_SHORT_SPEC = 'SPACK_SHORT_SPEC'
SPACK_DEBUG_LOG_DIR = 'SPACK_DEBUG_LOG_DIR'


# Platform-specific library suffix.
dso_suffix = 'dylib' if sys.platform == 'darwin' else 'so'


class MakeExecutable(Executable):
    """Special callable executable object for make so the user can
       specify parallel or not on a per-invocation basis.  Using
       'parallel' as a kwarg will override whatever the package's
       global setting is, so you can either default to true or false
       and override particular calls.

       Note that if the SPACK_NO_PARALLEL_MAKE env var is set it overrides
       everything.
    """

    def __init__(self, name, jobs, destdir=None):
        super(MakeExecutable, self).__init__(name)
        self.jobs = jobs
        self.destdir = destdir

    def __call__(self, *args, **kwargs):
        disable = env_flag(SPACK_NO_PARALLEL_MAKE)
        parallel = not disable and kwargs.get('parallel', self.jobs > 1)

        if parallel:
            jobs = "-j%d" % self.jobs
            args = (jobs,) + args

        if self.destdir and 'install' in args:
            args = ("DESTDIR={0}".format(self.destdir),) + args

        return super(MakeExecutable, self).__call__(*args, **kwargs)


def load_module(mod):
    """Takes a module name and removes modules until it is possible to
    load that module. It then loads the provided module. Depends on the
    modulecmd implementation of modules used in cray and lmod.
    """
    # Create an executable of the module command that will output python code
    modulecmd = which('modulecmd')
    modulecmd.add_default_arg('python')

    # Read the module and remove any conflicting modules
    # We do this without checking that they are already installed
    # for ease of programming because unloading a module that is not
    # loaded does nothing.
    text = modulecmd('show', mod, output=str, error=str).split()
    for i, word in enumerate(text):
        if word == 'conflict':
            exec(compile(modulecmd('unload', text[i + 1], output=str,
                                   error=str), '<string>', 'exec'))
    # Load the module now that there are no conflicts
    load = modulecmd('load', mod, output=str, error=str)
    exec(compile(load, '<string>', 'exec'))


def get_path_from_module(mod):
    """Inspects a TCL module for entries that indicate the absolute path
    at which the library supported by said module can be found.
    """
    # Create a modulecmd executable
    modulecmd = which('modulecmd')
    modulecmd.add_default_arg('python')

    # Read the module
    text = modulecmd('show', mod, output=str, error=str).split('\n')
    # If it lists its package directory, return that
    for line in text:
        if line.find(mod.upper() + '_DIR') >= 0:
            words = line.split()
            return words[2]

    # If it lists a -rpath instruction, use that
    for line in text:
        rpath = line.find('-rpath/')
        if rpath >= 0:
            return line[rpath + 6:line.find('/lib')]

    # If it lists a -L instruction, use that
    for line in text:
        L = line.find('-L/')
        if L >= 0:
            return line[L + 2:line.find('/lib')]

    # If it sets the LD_LIBRARY_PATH or CRAY_LD_LIBRARY_PATH, use that
    for line in text:
        if line.find('LD_LIBRARY_PATH') >= 0:
            words = line.split()
            path = words[2]
            return path[:path.find('/lib')]
    # Unable to find module path
    return None


def set_compiler_environment_variables(pkg, env):
    assert(pkg.spec.concrete)
    compiler = pkg.compiler
    flags = pkg.spec.compiler_flags

    # Set compiler variables used by CMake and autotools
    assert all(key in compiler.link_paths for key in (
        'cc', 'cxx', 'f77', 'fc'))

    # Populate an object with the list of environment modifications
    # and return it
    # TODO : add additional kwargs for better diagnostics, like requestor,
    # ttyout, ttyerr, etc.
    link_dir = spack.build_env_path

    # Set SPACK compiler variables so that our wrapper knows what to call
    if compiler.cc:
        env.set('SPACK_CC', compiler.cc)
        env.set('CC', join_path(link_dir, compiler.link_paths['cc']))
    if compiler.cxx:
        env.set('SPACK_CXX', compiler.cxx)
        env.set('CXX', join_path(link_dir, compiler.link_paths['cxx']))
    if compiler.f77:
        env.set('SPACK_F77', compiler.f77)
        env.set('F77', join_path(link_dir, compiler.link_paths['f77']))
    if compiler.fc:
        env.set('SPACK_FC',  compiler.fc)
        env.set('FC', join_path(link_dir, compiler.link_paths['fc']))

    # Set SPACK compiler rpath flags so that our wrapper knows what to use
    env.set('SPACK_CC_RPATH_ARG',  compiler.cc_rpath_arg)
    env.set('SPACK_CXX_RPATH_ARG', compiler.cxx_rpath_arg)
    env.set('SPACK_F77_RPATH_ARG', compiler.f77_rpath_arg)
    env.set('SPACK_FC_RPATH_ARG',  compiler.fc_rpath_arg)

    # Add every valid compiler flag to the environment, prefixed with "SPACK_"
    for flag in spack.spec.FlagMap.valid_compiler_flags():
        # Concreteness guarantees key safety here
        if flags[flag] != []:
            env.set('SPACK_' + flag.upper(), ' '.join(f for f in flags[flag]))

    env.set('SPACK_COMPILER_SPEC', str(pkg.spec.compiler))

    for mod in compiler.modules:
        load_module(mod)

    return env


def set_build_environment_variables(pkg, env, dirty=False):
    """
    This ensures a clean install environment when we build packages.

    Arguments:
    dirty -- skip unsetting the user's environment settings.
    """
    # Add spack build environment path with compiler wrappers first in
    # the path. We add both spack.env_path, which includes default
    # wrappers (cc, c++, f77, f90), AND a subdirectory containing
    # compiler-specific symlinks.  The latter ensures that builds that
    # are sensitive to the *name* of the compiler see the right name
    # when we're building with the wrappers.
    #
    # Conflicts on case-insensitive systems (like "CC" and "cc") are
    # handled by putting one in the <build_env_path>/case-insensitive
    # directory.  Add that to the path too.
    env_paths = []
    compiler_specific = join_path(spack.build_env_path, pkg.compiler.name)
    for item in [spack.build_env_path, compiler_specific]:
        env_paths.append(item)
        ci = join_path(item, 'case-insensitive')
        if os.path.isdir(ci):
            env_paths.append(ci)

    for item in reversed(env_paths):
        env.prepend_path('PATH', item)
    env.set_path(SPACK_ENV_PATH, env_paths)

    # Prefixes of all of the package's dependencies go in SPACK_DEPENDENCIES
    dep_prefixes = [d.prefix
                    for d in pkg.spec.traverse(root=False, deptype='build')]
    env.set_path(SPACK_DEPENDENCIES, dep_prefixes)
    # Add dependencies to CMAKE_PREFIX_PATH
    env.set_path('CMAKE_PREFIX_PATH', dep_prefixes)

    # Install prefix
    env.set(SPACK_PREFIX, pkg.prefix)

    # Install root prefix
    env.set(SPACK_INSTALL, spack.install_path)

    # Stuff in here sanitizes the build environemnt to eliminate
    # anything the user has set that may interfere.
    if not dirty:
        # Remove these vars from the environment during build because they
        # can affect how some packages find libraries.  We want to make
        # sure that builds never pull in unintended external dependencies.
        env.unset('LD_LIBRARY_PATH')
        env.unset('LIBRARY_PATH')
        env.unset('CPATH')
        env.unset('LD_RUN_PATH')
        env.unset('DYLD_LIBRARY_PATH')

        # Remove any macports installs from the PATH.  The macports ld can
        # cause conflicts with the built-in linker on el capitan.  Solves
        # assembler issues, e.g.:
        #    suffix or operands invalid for `movq'"
        path = get_path('PATH')
        for p in path:
            if '/macports/' in p:
                env.remove_path('PATH', p)

    # Add bin directories from dependencies to the PATH for the build.
    bin_dirs = reversed(
        filter(os.path.isdir, ['%s/bin' % prefix for prefix in dep_prefixes]))
    for item in bin_dirs:
        env.prepend_path('PATH', item)

    # Working directory for the spack command itself, for debug logs.
    if spack.debug:
        env.set(SPACK_DEBUG, 'TRUE')
    env.set(SPACK_SHORT_SPEC, pkg.spec.short_spec)
    env.set(SPACK_DEBUG_LOG_DIR, spack.spack_working_dir)

    # Add any pkgconfig directories to PKG_CONFIG_PATH
    for pre in dep_prefixes:
        for directory in ('lib', 'lib64', 'share'):
            pcdir = join_path(pre, directory, 'pkgconfig')
            if os.path.isdir(pcdir):
                env.prepend_path('PKG_CONFIG_PATH', pcdir)

    if pkg.spec.architecture.target.module_name:
        load_module(pkg.spec.architecture.target.module_name)

    return env


class RedirectionInstallContext(object):
    """
    Provides file commands which redirect paths relative to a specified
    directory; furthermore it only redirects paths with a specified prefix.
    For example if the prefix is /x/y/ and the destination directory is
    /redirect/, then creating a file /x/y/z will actually create a file in
    /redirect/x/y/z. For the purposes of matching against the prefix, /x/y
    will be considered a match with /x/y/.

    For commands that return file paths, the provided commands strip off the
    redirect prefix (when it is present), which ensures they are safe to use
    as symlink targets (for example).

    Paths used as locations for file commands (e.g. when copying, moving, or
    deleting) should be redirected (if they target the package prefix).
    """
    def __init__(self, pkgPrefix, destdir):
        if not pkgPrefix.endswith(os.sep):
            pkgPrefix += os.sep
        self.pkgPrefix = pkgPrefix
        self.destdir = destdir

    def redirect_path(self, path):
        path = os.path.abspath(path)
        # Append os.sep so that if self.pkgPrefix = "/x/y/z/", it will be
        # considered a prefix of "/x/y/z".
        if self.destdir and (path + os.sep).startswith(self.pkgPrefix):
            if path.startswith(os.sep):
                path = path[len(os.sep):]
            return join_path(self.destdir, path)
        else:
            return path

    def strip_destdir(self, path):
        path = os.path.abspath(path)
        if self.destdir and path.startswith(self.destdir):
            path = os.sep + path[len(self.destdir):]
        return path

    def install_redirect(self, src, dst):
        install(src, self.redirect_path(dst))

    def mkdirp_redirect(self, *paths):
        paths = list(self.redirect_path(x) for x in paths)
        mkdirp(*paths)

    def symlink_redirect(self, src, dst, force=False):
        # Redirects dst, removes DESTDIR from src. Does not need to assume that
        # src intends pkgPrefix as a prefix but does assume that no intended
        # prefix has DESTDIR as a prefix.
        srcPath = self.strip_destdir(src)
        if force:
            force_symlink(srcPath, self.redirect_path(dst))
        else:
            os.symlink(srcPath, self.redirect_path(dst))

    def pwd_redirect(self):
        return self.strip_destdir(os.getcwd())

    def force_symlink_redirect(self, src, dst):
        self.symlink_redirect(src, dst, force=True)

    def working_dir_redirect(self, dirname, **kwargs):
        return working_dir(self.redirect_path(dirname), **kwargs)

    def glob_redirect(self, pathPattern):
        return list(self.strip_destdir(x) for x in
                    glob.glob(self.redirect_path(pathPattern)))

    def open_redirect(self, path, *args):
        return open(self.redirect_path(path), *args)


class RedirectedCommand(object):
    def __init__(self, fn, redirContext, numPaths=1):
        self.fn = fn
        self.redirCtxt = redirContext
        self.numPaths = numPaths

    def __call__(self, *args, **kwargs):
        newArgs = list(args[:-self.numPaths])
        newArgs.extend(self.redirCtxt.redirect_path(p)
                       for p in args[-self.numPaths:])
        return self.fn(*newArgs, **kwargs)


def set_module_variables_for_package(pkg, module):
    """Populate the module scope of install() with some useful functions.
       This makes things easier for package writers.
    """
    # number of jobs spack will build with.
    jobs = multiprocessing.cpu_count()
    if not pkg.parallel:
        jobs = 1
    elif pkg.make_jobs:
        jobs = pkg.make_jobs

    m = module
    m.make_jobs = jobs

    pkgCtxt = pkg.installCtxt
    destdir = pkgCtxt.destdir

    # TODO: make these build deps that can be installed if not found.
    m.make  = MakeExecutable('make', jobs, destdir)
    m.gmake = MakeExecutable('gmake', jobs, destdir)
    m.make_redir = MakeExecutable('make-redir', jobs, destdir)
    m.scons = MakeExecutable('scons', jobs)

    # easy shortcut to os.environ
    m.env = os.environ

    # Find the configure script in the archive path
    # Don't use which for this; we want to find it in the current dir.
    m.configure = Executable('./configure')

    m.cmake = Executable('cmake')
    m.ctest = Executable('ctest')

    # standard CMake arguments
    m.std_cmake_args = ['-DCMAKE_INSTALL_PREFIX=%s' % pkg.prefix,
                        '-DCMAKE_BUILD_TYPE=RelWithDebInfo']
    if platform.mac_ver()[0]:
        m.std_cmake_args.append('-DCMAKE_FIND_FRAMEWORK=LAST')

    # Set up CMake rpath
    m.std_cmake_args.append('-DCMAKE_INSTALL_RPATH_USE_LINK_PATH=FALSE')
    m.std_cmake_args.append('-DCMAKE_INSTALL_RPATH=%s' %
                            ":".join(get_rpaths(pkg)))

    # Put spack compiler paths in module scope.
    link_dir = spack.build_env_path
    m.spack_cc = join_path(link_dir, pkg.compiler.link_paths['cc'])
    m.spack_cxx = join_path(link_dir, pkg.compiler.link_paths['cxx'])
    m.spack_f77 = join_path(link_dir, pkg.compiler.link_paths['f77'])
    m.spack_fc  = join_path(link_dir, pkg.compiler.link_paths['fc'])

    # Emulate some shell commands for convenience
    if pkgCtxt.destdir:
        m.pwd = pkgCtxt.pwd_redirect
        m.symlink = pkgCtxt.symlink_redirect
        m.mkdirp  = pkgCtxt.mkdirp_redirect
        m.glob_redirect = pkgCtxt.glob_redirect

        m.cd = RedirectedCommand(os.chdir, pkgCtxt, 1)
        m.mkdir = RedirectedCommand(os.mkdir, pkgCtxt, 1)
        m.makedirs = RedirectedCommand(os.makedirs, pkgCtxt, 1)
        m.remove = RedirectedCommand(os.remove, pkgCtxt, 1)
        m.removedirs = RedirectedCommand(os.removedirs, pkgCtxt, 1)

        m.install = pkgCtxt.install_redirect
        m.install_tree = RedirectedCommand(install_tree, pkgCtxt, 2)
        m.move = RedirectedCommand(shutil.move, pkgCtxt, 2)
        m.rmtree = RedirectedCommand(shutil.rmtree, pkgCtxt, 1)
        m.cp = RedirectedCommand(which('cp'), pkgCtxt, 2)

        # These are only set for redirected installations of pkg
        m.working_dir  = pkgCtxt.working_dir_redirect
        m.open = pkgCtxt.open_redirect
        m.force_symlink = pkgCtxt.force_symlink_redirect
    else:
        m.glob_redirect = glob.glob
        m.pwd = os.getcwd
        m.cd = os.chdir
        m.mkdir = os.mkdir
        m.makedirs = os.makedirs
        m.remove = os.remove
        m.removedirs = os.removedirs
        m.symlink = os.symlink
        m.cp = which('cp')

        m.mkdirp  = mkdirp
        m.install = install
        m.install_tree = install_tree
        m.move = shutil.move
        m.rmtree = shutil.rmtree

    # Useful directories within the prefix are encapsulated in
    # a Prefix object.
    m.prefix = pkg.prefix

    # Platform-specific library suffix.
    m.dso_suffix = dso_suffix


def get_rpaths(pkg):
    """Get a list of all the rpaths for a package."""
    rpaths = [pkg.prefix.lib, pkg.prefix.lib64]
    deps = pkg.spec.dependencies(deptype='link')
    rpaths.extend(d.prefix.lib for d in deps
                  if os.path.isdir(d.prefix.lib))
    rpaths.extend(d.prefix.lib64 for d in deps
                  if os.path.isdir(d.prefix.lib64))
    # Second module is our compiler mod name. We use that to get rpaths from
    # module show output.
    if pkg.compiler.modules and len(pkg.compiler.modules) > 1:
        rpaths.append(get_path_from_module(pkg.compiler.modules[1]))
    return rpaths


def parent_class_modules(cls):
    """
    Get list of super class modules that are all descend from spack.Package
    """
    if not issubclass(cls, spack.Package) or issubclass(spack.Package, cls):
        return []
    result = []
    module = sys.modules.get(cls.__module__)
    if module:
        result = [module]
    for c in cls.__bases__:
        result.extend(parent_class_modules(c))
    return result


def load_external_modules(pkg):
    """ traverse the spec list and find any specs that have external modules.
    """
    for dep in list(pkg.spec.traverse()):
        if dep.external_module:
            load_module(dep.external_module)


def setup_package(pkg, dirty=False):
    """Execute all environment setup routines."""
    spack_env = EnvironmentModifications()
    run_env = EnvironmentModifications()

    # Before proceeding, ensure that specs and packages are consistent
    #
    # This is a confusing behavior due to how packages are
    # constructed.  `setup_dependent_package` may set attributes on
    # specs in the DAG for use by other packages' install
    # method. However, spec.package will look up a package via
    # spack.repo, which defensively copies specs into packages.  This
    # code ensures that all packages in the DAG have pieces of the
    # same spec object at build time.
    #
    # This is safe for the build process, b/c the build process is a
    # throwaway environment, but it is kind of dirty.
    #
    # TODO: Think about how to avoid this fix and do something cleaner.
    for s in pkg.spec.traverse():
        s.package.spec = s

    set_compiler_environment_variables(pkg, spack_env)
    set_build_environment_variables(pkg, spack_env, dirty)
    pkg.spec.architecture.platform.setup_platform_environment(pkg, spack_env)
    load_external_modules(pkg)
    # traverse in postorder so package can use vars from its dependencies
    spec = pkg.spec
    for dspec in pkg.spec.traverse(order='post', root=False, deptype='build'):
        # If a user makes their own package repo, e.g.
        # spack.repos.mystuff.libelf.Libelf, and they inherit from
        # an existing class like spack.repos.original.libelf.Libelf,
        # then set the module variables for both classes so the
        # parent class can still use them if it gets called.
        spkg = dspec.package
        modules = parent_class_modules(spkg.__class__)
        for mod in modules:
            set_module_variables_for_package(spkg, mod)
        set_module_variables_for_package(spkg, spkg.module)

        # Allow dependencies to modify the module
        dpkg = dspec.package
        dpkg.setup_dependent_package(pkg.module, spec)
        dpkg.setup_dependent_environment(spack_env, run_env, spec)

    set_module_variables_for_package(pkg, pkg.module)
    pkg.setup_environment(spack_env, run_env)

    # Make sure nothing's strange about the Spack environment.
    validate(spack_env, tty.warn)
    spack_env.apply_modifications()


def fork(pkg, function, dirty=False):
    """Fork a child process to do part of a spack build.

    :param pkg: pkg whose environemnt we should set up the forked process for.
    :param function: arg-less function to run in the child process.
    :param dirty: If True, do NOT clean the environment before building.

    Usage::

       def child_fun():
           # do stuff
       build_env.fork(pkg, child_fun)

    Forked processes are run with the build environment set up by
    spack.build_environment.  This allows package authors to have
    full control over the environment, etc. without affecting
    other builds that might be executed in the same spack call.

    If something goes wrong, the child process is expected to print
    the error and the parent process will exit with error as
    well. If things go well, the child exits and the parent
    carries on.
    """

    try:
        pid = os.fork()
    except OSError as e:
        raise InstallError("Unable to fork build process: %s" % e)

    if pid == 0:
        # Give the child process the package's build environment.
        setup_package(pkg, dirty=dirty)

        try:
            # call the forked function.
            function()

            # Use os._exit here to avoid raising a SystemExit exception,
            # which interferes with unit tests.
            os._exit(0)

        except spack.error.SpackError as e:
            e.die()

        except:
            # Child doesn't raise or return to main spack code.
            # Just runs default exception handler and exits.
            sys.excepthook(*sys.exc_info())
            os._exit(1)

    else:
        # Parent process just waits for the child to complete.  If the
        # child exited badly, assume it already printed an appropriate
        # message.  Just make the parent exit with an error code.
        pid, returncode = os.waitpid(pid, 0)
        if returncode != 0:
            message = "Installation process had nonzero exit code : {code}"
            strcode = str(returncode)
            raise InstallError(message.format(code=strcode))


class InstallError(spack.error.SpackError):
    """Raised when a package fails to install"""

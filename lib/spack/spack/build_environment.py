"""
This module contains all routines related to setting up the package
build environment.  All of this is set up by package.py just before
install() is called.

There are two parts to the bulid environment:

1. Python build environment (i.e. install() method)

   This is how things are set up when install() is called.  Spack
   takes advantage of each package being in its own module by adding a
   bunch of command-like functions (like configure(), make(), etc.) in
   the package's module scope.  Ths allows package writers to call
   them all directly in Package.install() without writing 'self.'
   everywhere.  No, this isn't Pythonic.  Yes, it makes the code more
   readable and more like the shell script from whcih someone is
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
import os
import sys
import shutil
import multiprocessing
import platform
from llnl.util.filesystem import *

import spack
import spack.compilers as compilers
from spack.util.executable import Executable, which
from spack.util.environment import *

#
# This can be set by the user to globally disable parallel builds.
#
SPACK_NO_PARALLEL_MAKE = 'SPACK_NO_PARALLEL_MAKE'

#
# These environment variables are set by
# set_build_environment_variables and used to pass parameters to
# Spack's compiler wrappers.
#
SPACK_ENV_PATH         = 'SPACK_ENV_PATH'
SPACK_DEPENDENCIES     = 'SPACK_DEPENDENCIES'
SPACK_PREFIX           = 'SPACK_PREFIX'
SPACK_INSTALL          = 'SPACK_INSTALL'
SPACK_DEBUG            = 'SPACK_DEBUG'
SPACK_SHORT_SPEC       = 'SPACK_SHORT_SPEC'
SPACK_DEBUG_LOG_DIR    = 'SPACK_DEBUG_LOG_DIR'


class MakeExecutable(Executable):
    """Special callable executable object for make so the user can
       specify parallel or not on a per-invocation basis.  Using
       'parallel' as a kwarg will override whatever the package's
       global setting is, so you can either default to true or false
       and override particular calls.

       Note that if the SPACK_NO_PARALLEL_MAKE env var is set it overrides
       everything.
    """
    def __init__(self, name, jobs):
        super(MakeExecutable, self).__init__(name)
        self.jobs = jobs

    def __call__(self, *args, **kwargs):
        disable = env_flag(SPACK_NO_PARALLEL_MAKE)
        parallel = not disable and kwargs.get('parallel', self.jobs > 1)

        if parallel:
            jobs = "-j%d" % self.jobs
            args = (jobs,) + args

        return super(MakeExecutable, self).__call__(*args, **kwargs)


def set_compiler_environment_variables(pkg):
    assert(pkg.spec.concrete)
    compiler = pkg.compiler

    # Set compiler variables used by CMake and autotools
    assert all(key in pkg.compiler.link_paths
               for key in ('cc', 'cxx', 'f77', 'fc'))

    link_dir = spack.build_env_path
    os.environ['CC']  = join_path(link_dir, pkg.compiler.link_paths['cc'])
    os.environ['CXX'] = join_path(link_dir, pkg.compiler.link_paths['cxx'])
    os.environ['F77'] = join_path(link_dir, pkg.compiler.link_paths['f77'])
    os.environ['FC']  = join_path(link_dir, pkg.compiler.link_paths['fc'])

    # Set SPACK compiler variables so that our wrapper knows what to call
    if compiler.cc:
        os.environ['SPACK_CC']  = compiler.cc
    if compiler.cxx:
        os.environ['SPACK_CXX'] = compiler.cxx
    if compiler.f77:
        os.environ['SPACK_F77'] = compiler.f77
    if compiler.fc:
        os.environ['SPACK_FC']  = compiler.fc

    os.environ['SPACK_COMPILER_SPEC']  = str(pkg.spec.compiler)


def set_build_environment_variables(pkg):
    """This ensures a clean install environment when we build packages.
    """
    # Add spack build environment path with compiler wrappers first in
    # the path. We add both spack.env_path, which includes default
    # wrappers (cc, c++, f77, f90), AND a subdirectory containing
    # compiler-specific symlinks.  The latter ensures that builds that
    # are sensitive to the *name* of the compiler see the right name
    # when we're building wtih the wrappers.
    #
    # Conflicts on case-insensitive systems (like "CC" and "cc") are
    # handled by putting one in the <build_env_path>/case-insensitive
    # directory.  Add that to the path too.
    env_paths = []
    def add_env_path(path):
        env_paths.append(path)
        ci = join_path(path, 'case-insensitive')
        if os.path.isdir(ci): env_paths.append(ci)
    add_env_path(spack.build_env_path)
    add_env_path(join_path(spack.build_env_path, pkg.compiler.name))

    path_put_first("PATH", env_paths)
    path_set(SPACK_ENV_PATH, env_paths)

    # Prefixes of all of the package's dependencies go in
    # SPACK_DEPENDENCIES
    dep_prefixes = [d.prefix for d in pkg.spec.traverse(root=False)]
    path_set(SPACK_DEPENDENCIES, dep_prefixes)

    # Install prefix
    os.environ[SPACK_PREFIX] = pkg.prefix

    # Install root prefix
    os.environ[SPACK_INSTALL] = spack.install_path

    # Remove these vars from the environment during build because they
    # can affect how some packages find libraries.  We want to make
    # sure that builds never pull in unintended external dependencies.
    pop_keys(os.environ, "LD_LIBRARY_PATH", "LD_RUN_PATH", "DYLD_LIBRARY_PATH")

    # Add bin directories from dependencies to the PATH for the build.
    bin_dirs = ['%s/bin' % prefix for prefix in dep_prefixes]
    path_put_first('PATH', [bin for bin in bin_dirs if os.path.isdir(bin)])

    # Working directory for the spack command itself, for debug logs.
    if spack.debug:
        os.environ[SPACK_DEBUG] = "TRUE"
    os.environ[SPACK_SHORT_SPEC] = pkg.spec.short_spec
    os.environ[SPACK_DEBUG_LOG_DIR] = spack.spack_working_dir

    # Add dependencies to CMAKE_PREFIX_PATH
    path_set("CMAKE_PREFIX_PATH", dep_prefixes)

    # Add any pkgconfig directories to PKG_CONFIG_PATH
    pkg_config_dirs = []
    for p in dep_prefixes:
        for libdir in ('lib', 'lib64'):
            pcdir = join_path(p, libdir, 'pkgconfig')
            if os.path.isdir(pcdir):
                pkg_config_dirs.append(pcdir)
    path_set("PKG_CONFIG_PATH", pkg_config_dirs)


def set_module_variables_for_package(pkg, m):
    """Populate the module scope of install() with some useful functions.
       This makes things easier for package writers.
    """
    # number of jobs spack will to build with.
    jobs = multiprocessing.cpu_count()
    if not pkg.parallel:
        jobs = 1
    elif pkg.make_jobs:
        jobs = pkg.make_jobs
    m.make_jobs = jobs

    # TODO: make these build deps that can be installed if not found.
    m.make  = MakeExecutable('make', jobs)
    m.gmake = MakeExecutable('gmake', jobs)

    # easy shortcut to os.environ
    m.env = os.environ

    # Find the configure script in the archive path
    # Don't use which for this; we want to find it in the current dir.
    m.configure = Executable('./configure')

    # TODO: shouldn't really use "which" here.  Consider adding notion
    # TODO: of build dependencies, as opposed to link dependencies.
    # TODO: Currently, everything is a link dependency, but tools like
    # TODO: this shouldn't be.
    m.cmake = which("cmake")

    # standard CMake arguments
    m.std_cmake_args = ['-DCMAKE_INSTALL_PREFIX=%s' % pkg.prefix,
                        '-DCMAKE_BUILD_TYPE=RelWithDebInfo']
    if platform.mac_ver()[0]:
        m.std_cmake_args.append('-DCMAKE_FIND_FRAMEWORK=LAST')

    # Set up CMake rpath
    m.std_cmake_args.append('-DCMAKE_INSTALL_RPATH_USE_LINK_PATH=FALSE')
    m.std_cmake_args.append('-DCMAKE_INSTALL_RPATH=%s' % ":".join(get_rpaths(pkg)))

    # Put spack compiler paths in module scope.
    link_dir = spack.build_env_path
    m.spack_cc  = join_path(link_dir, pkg.compiler.link_paths['cc'])
    m.spack_cxx = join_path(link_dir, pkg.compiler.link_paths['cxx'])
    m.spack_f77 = join_path(link_dir, pkg.compiler.link_paths['f77'])
    m.spack_f90 = join_path(link_dir, pkg.compiler.link_paths['fc'])

    # Emulate some shell commands for convenience
    m.pwd          = os.getcwd
    m.cd           = os.chdir
    m.mkdir        = os.mkdir
    m.makedirs     = os.makedirs
    m.remove       = os.remove
    m.removedirs   = os.removedirs
    m.symlink      = os.symlink

    m.mkdirp       = mkdirp
    m.install      = install
    m.install_tree = install_tree
    m.rmtree       = shutil.rmtree
    m.move         = shutil.move

    # Useful directories within the prefix are encapsulated in
    # a Prefix object.
    m.prefix  = pkg.prefix


def get_rpaths(pkg):
    """Get a list of all the rpaths for a package."""
    rpaths = [pkg.prefix.lib, pkg.prefix.lib64]
    rpaths.extend(d.prefix.lib for d in pkg.spec.dependencies.values()
                  if os.path.isdir(d.prefix.lib))
    rpaths.extend(d.prefix.lib64 for d in pkg.spec.dependencies.values()
                  if os.path.isdir(d.prefix.lib64))
    return rpaths


def parent_class_modules(cls):
    """Get list of super class modules that are all descend from spack.Package"""
    if not issubclass(cls, spack.Package) or issubclass(spack.Package, cls):
        return []
    result = []
    module = sys.modules.get(cls.__module__)
    if module:
        result = [ module ]
    for c in cls.__bases__:
        result.extend(parent_class_modules(c))
    return result


def setup_package(pkg):
    """Execute all environment setup routines."""
    set_compiler_environment_variables(pkg)
    set_build_environment_variables(pkg)

    # If a user makes their own package repo, e.g.
    # spack.repos.mystuff.libelf.Libelf, and they inherit from
    # an existing class like spack.repos.original.libelf.Libelf,
    # then set the module variables for both classes so the
    # parent class can still use them if it gets called.
    modules = parent_class_modules(pkg.__class__)
    for mod in modules:
        set_module_variables_for_package(pkg, mod)

    # Allow dependencies to set up environment as well.
    for dep_spec in pkg.spec.traverse(root=False):
        dep_spec.package.setup_dependent_environment(
            pkg.module, dep_spec, pkg.spec)


def fork(pkg, function):
    """Fork a child process to do part of a spack build.

    Arguments:

    pkg -- pkg whose environemnt we should set up the
           forked process for.
    function -- arg-less function to run in the child process.

    Usage:
       def child_fun():
           # do stuff
       build_env.fork(pkg, child_fun)

    Forked processes are run with the build environemnt set up by
    spack.build_environment.  This allows package authors to have
    full control over the environment, etc. without offecting
    other builds that might be executed in the same spack call.

    If something goes wrong, the child process is expected toprint
    the error and the parent process will exit with error as
    well. If things go well, the child exits and the parent
    carries on.
    """
    try:
        pid = os.fork()
    except OSError, e:
        raise InstallError("Unable to fork build process: %s" % e)

    if pid == 0:
        # Give the child process the package's build environemnt.
        setup_package(pkg)

        try:
            # call the forked function.
            function()

            # Use os._exit here to avoid raising a SystemExit exception,
            # which interferes with unit tests.
            os._exit(0)

        except spack.error.SpackError, e:
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
            raise InstallError("Installation process had nonzero exit code."
                .format(str(returncode)))


class InstallError(spack.error.SpackError):
    """Raised when a package fails to install"""

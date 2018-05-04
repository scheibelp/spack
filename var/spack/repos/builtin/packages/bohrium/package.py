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
from spack import *
from spack.package_test import compare_output
from spack.util.executable import Executable
import llnl.util.tty as tty
import os


class Bohrium(CMakePackage, CudaPackage):
    """Library for automatic acceleration of array operations"""

    homepage    = "http://bh107.org"
    url         = "https://github.com/bh107/bohrium/archive/v0.8.9.tar.gz"
    maintainers = ['mfherbst']

    #
    # Versions
    #
    version("develop", git="https://github.com/bh107/bohrium.git",
            branch="master")
    version('0.9.0', checksum="6f6379f1555de5a6a19138beac891a470df7df1fc9594e2b9404cf01b6e17d93")

    #
    # Variants
    #
    variant("cuda", default=True,
            description="Build with CUDA code generator")
    variant('opencl', default=True,
            description="Build with OpenCL code generator")
    variant('openmp', default=True,
            description="Build with OpenMP code generator")

    variant('node', default=True,
            description="Build the node vector engine manager")
    variant('proxy', default=False,
            description="Build the proxy vector engine manager")
    variant('python', default=True,
            description="Build the numpy-like bridge "
            "to enable use from python")
    variant('cbridge', default=True,
            description="Build the bridge interface towards plain C")

    variant('blas', default=True,
            description="Build with BLAS extension methods")
    variant('lapack', default=True,
            description="Build with LAPACK extension methods")
    variant('opencv', default=True,
            description="Build with OpenCV extension methods")

    #
    # Conflicts and extensions
    #
    conflicts('%intel')
    conflicts('%clang@:3.5')
    conflicts('%gcc@:4.7')
    extends('python', when="+python")

    # Bohrium needs at least one vector engine and
    # at least one vector engine manager
    conflicts('~node~proxy')
    conflicts('~openmp~opencl~cuda')

    #
    # Dependencies
    #
    depends_on('cmake@2.8:', type="build")
    depends_on('boost+system+serialization+filesystem+regex')

    # cuda dependencies managed by CudaPackage class
    depends_on('opencl', when="+opencl")

    # NOTE The lapacke interface and hence netlib-lapack
    #      is the strictly required lapack provider
    #      for bohrium right now.
    depends_on('netlib-lapack+lapacke', when="+lapack")
    depends_on('blas', when="+blas")

    # Make sure an appropriate opencv is used
    depends_on('opencv+imgproc', when="+opencv")
    depends_on('opencv+imgproc+cuda', when="+opencv+cuda")
    depends_on('opencv+imgproc+openmp', when="+opencv+openmp")
    depends_on('opencv+imgproc+openmp+cuda', when="+opencv+openmp+cuda")

    depends_on('python', type="build", when="~python")
    depends_on('python', type=("build", "link", "test"), when="+python")
    depends_on('py-numpy', type=("build", "test", "run"), when="+python")
    depends_on('swig', type="build", when="+python")
    depends_on('py-cython', type="build", when="+python")

    depends_on('zlib', when="+proxy")

    @property
    def config_file(self):
        """Return the path of the Bohrium system-wide configuration file"""
        return join_path(self.prefix.etc.bohrium, "config.ini")

    #
    # Settings and cmake cache
    #
    def cmake_args(self):
        spec = self.spec

        # Sanity check
        cuda_arch = spec.variants['cuda_arch'].value
        if "+cuda" in spec and len(cuda_arch) >= 1 and cuda_arch[0]:
            # TODO Add cuda_arch support to Bohrium once the basic setup
            #      via Spack works.
            raise InstallError(
                "Bohrium does not support setting the CUDA architecture yet."
            )

        args = [
            # Choose a particular python version
            "-DPYTHON_EXECUTABLE:FILEPATH=" + spec['python'].command.path,
            #
            # Hard-disable Jupyter, since this would override a config
            # file in the user's home directory in some cases during
            # the configuration stage.
            "-DJUPYTER_FOUND=FALSE",
            "-DJUPYTER_EXECUTABLE=FALSE",
            #
            # Force the configuration file to appear at a sensible place
            "-DFORCE_CONFIG_PATH=" + os.path.dirname(self.config_file),
            #
            # Vector engine managers
            "-DVEM_NODE=" + str("+node" in spec),
            "-DVEM_PROXY=" + str("+proxy" in spec),
            #
            # Bridges and interfaces
            "-DBRIDGE_BHXX=ON",
            "-DBRIDGE_C=" + str("+cbridge" in spec or "+python" in spec),
            "-DBRIDGE_NPBACKEND=" + str("+python" in spec),
            "-DNO_PYTHON3=ON",  # Only build python version we provide
        ]

        #
        # Vector engines
        #
        args += [
            "-DVE_OPENCL=" + str("+opencl" in spec),
            "-DVE_CUDA=" + str("+cuda" in spec),
        ]

        if "+openmp" in spec:
            args += [
                "-DVE_OPENMP=ON",
                "-DOPENMP_FOUND=True",
                "-DVE_OPENMP_COMPILER_CMD=" + self.compiler.cc,
            ]
        else:
            args += ["-DVE_OPENMP=OFF", "-DOPENMP_FOUND=False"]

        #
        # Extension methods
        #
        if "+blas" in spec:
            args += [
                "-DEXT_BLAS=ON",
                "-DCBLAS_FOUND=True",
                "-DCBLAS_LIBRARIES=" + spec["blas"].libs.joined(";"),
                "-DCBLAS_INCLUDES=" + spec["blas"].prefix.include,
            ]
        else:
            args += ["-DEXT_BLAS=OFF", "-DDCBLAS_FOUND=False"]

        if "+lapack" in spec:
            args += [
                "-DEXT_LAPACK=ON",
                "-DLAPACKE_FOUND=True",
                "-DLAPACKE_LIBRARIES=" + spec["lapack"].libs.joined(";"),
                "-DLAPACKE_INCLUDE_DIR=" + spec["lapack"].prefix.include,
            ]
        else:
            args += ["-DEXT_LAPACK=OFF", "-DLAPACKE_FOUND=False"]

        if "+opencv" in spec:
            args += [
                "-DEXT_OPENCV=ON",
                "-DOpenCV_FOUND=True",
                "-DOpenCV_INCLUDE_DIRS=" + spec["opencv"].prefix.include,
                "-DOpenCV_LIBS=" + spec["opencv"].libs.joined(";"),
            ]
        else:
            args += ["-DEXT_OPENCV=OFF", "-DOpenCV_FOUND=False"]

        # TODO Other extension methods are not ready yet,
        #      because of missing packages in Spack
        args += [
            "-DEXT_CLBLAS=OFF",      # clBLAS missing
            # Bohrium visualizer extension method
            "-DEXT_VISUALIZER=OFF",  # freeglut missing
        ]
        return args

    #
    # Environment setup
    #
    def setup_environment(self, spack_env, run_env):
        # Bohrium needs an extra include dir apart from
        # the self.prefix.include dir
        run_env.prepend_path("CPATH", self.prefix.include.bohrium)
        run_env.set("BH_CONFIG", self.config_file)

    #
    # Quick tests
    #
    @run_after('install')
    @on_package_attributes(run_tests=True)
    def check_install(self):
        spec = self.spec
        test_env = {}

        # Make sure the correct config is found
        test_env["BH_CONFIG"] = self.config_file

        # Remove the lib/spackenv directory from the PATH variable when
        # executing the tests, becauses it messes with the JIT compilation
        # inside Bohrium
        paths = os.environ['PATH'].split(':')
        paths = [p for p in paths if "spack/env" not in p]
        test_env["PATH"] = ":".join(paths)

        # Add the PYTHONPATH to bohrium to the PYTHONPATH environment
        pythonpaths = [p for p in os.environ["PYTHONPATH"].split(":")]
        pythonpaths.append(join_path(self.prefix,
                                     spec['python'].package.site_packages_dir))
        test_env["PYTHONPATH"] = ":".join(pythonpaths)

        # Collect the stacks which should be available:
        stacks = ["default"]
        if "+openmp" in spec:
            stacks.append("openmp")
        if "+cuda" in spec:
            stacks.append("cuda")
        if "+opencl" in spec:
            stacks.append("opencl")

        # C++ compiler and compiler flags
        cxx = Executable(self.compiler.cxx)
        cxx_flags = ["-I", self.prefix.include,
                     "-I", self.prefix.include.bohrium,
                     "-L", self.prefix.lib, "-lbh", "-lbhxx"]

        # Compile C++ test program
        file_cxxadd = join_path(os.path.dirname(self.module.__file__),
                                "cxxadd.cpp")
        cxx("-o", "test_cxxadd", file_cxxadd, *cxx_flags)
        test_cxxadd = Executable("./test_cxxadd")

        # Build python test commandline
        file_pyadd = join_path(os.path.dirname(self.module.__file__),
                               "pyadd.py")
        test_pyadd = Executable(spec['python'].command.path + " " + file_pyadd)

        # Run tests for each available stack
        for bh_stack in stacks:
            tty.info("Testing with bohrium stack '" + bh_stack + "'")
            test_env["BH_STACK"] = bh_stack

            cpp_output = test_cxxadd(output=str, env=test_env)
            compare_output(cpp_output, "Success!\n")

            # Python test (if +python)
            if "+python" in spec:
                py_output = test_pyadd(output=str, env=test_env)
                compare_output(py_output, "Success!\n")

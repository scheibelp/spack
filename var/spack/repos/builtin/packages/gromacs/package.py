##############################################################################
# Copyright (c) 2013-2017, Lawrence Livermore National Security, LLC.
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


class Gromacs(CMakePackage):
    """GROMACS (GROningen MAchine for Chemical Simulations) is a molecular
    dynamics package primarily designed for simulations of proteins, lipids
    and nucleic acids. It was originally developed in the Biophysical
    Chemistry department of University of Groningen, and is now maintained
    by contributors in universities and research centers across the world.

    GROMACS is one of the fastest and most popular software packages
    available and can run on CPUs as well as GPUs. It is free, open source
    released under the GNU General Public License. Starting from version 4.6,
    GROMACS is released under the GNU Lesser General Public License.
    """

    homepage = 'http://www.gromacs.org'
    url = 'http://ftp.gromacs.org/gromacs/gromacs-5.1.2.tar.gz'

    version('2018', '6467ffb1575b8271548a13abfba6374c')
    version('2016.4', '19c8b5c85f3ec62df79d2249a3c272f8')
    version('2016.3', 'e9e3a41bd123b52fbcc6b32d09f8202b')
    version('5.1.4', 'ba2e34d59b3982603b4935d650c08040')
    version('5.1.2', '614d0be372f1a6f1f36382b7a6fcab98')
    version('develop', git='https://github.com/gromacs/gromacs', branch='master')

    variant('mpi', default=True, description='Activate MPI support')
    variant('shared', default=True,
            description='Enables the build of shared libraries')
    variant(
        'double', default=False,
        description='Produces a double precision version of the executables')
    variant('plumed', default=False, description='Enable PLUMED support')
    variant('cuda', default=False, description='Enable CUDA support')
    variant('build_type', default='RelWithDebInfo',
            description='The build type to build',
            values=('Debug', 'Release', 'RelWithDebInfo', 'MinSizeRel',
                    'Reference', 'RelWithAssert', 'Profile'))

    depends_on('mpi', when='+mpi')
    depends_on('plumed+mpi', when='+plumed+mpi')
    depends_on('plumed~mpi', when='+plumed~mpi')
    depends_on('fftw')
    depends_on('cmake@2.8.8:', type='build')
    depends_on('cmake@3.4.3:', type='build', when='@2018:')
    depends_on('cuda', when='+cuda')

    def patch(self):
        if '+plumed' in self.spec:
            self.spec['plumed'].package.apply_patch(self)

        #files = list(glob.glob('CMakeLists.txt')) + list(glob.glob('*.cmake'))

        cmakelists = find('.', 'CMakeLists.txt', True)
        dotcmake = find('.', "*.cmake", True)
        to_update = list(cmakelists) + list(dotcmake)
        system_ff = FileFilter(*to_update)
        system_ff.filter(r'include_directories\(SYSTEM ', r'include_directories(')

    def cmake_args(self):

        options = []

        #options.append('-DCMAKE_CXX_COMPILER_EXTERNAL_TOOLCHAIN:STRING=/opt/gcc/7.2.0/snos/')

        #options.append('-DCMAKE_C_COMPILER=/global/homes/s/scheibel/spack/lib/spack/env/gcc/gcc')
        #options.append('-DCMAKE_CXX_COMPILER=/global/homes/s/scheibel/spack/lib/spack/env/c++')

        #options.append('-DENABLE_PRECOMPILED_HEADERS:BOOL=OFF')

        #options.append('-DCMAKE_C_IMPLICIT_INCLUDE_DIRECTORIES:STRING=/usr/include/')
        #options.append('-DCMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES:STRING=/usr/include/')

        #options.append('-DCMAKE_INCLUDE_PATH:STRING=/opt/gcc/7.2.0/snos/include/g++/')

        if '+mpi' in self.spec:
            options.append('-DGMX_MPI:BOOL=ON')

        if '+double' in self.spec:
            options.append('-DGMX_DOUBLE:BOOL=ON')

        if '~shared' in self.spec:
            options.append('-DBUILD_SHARED_LIBS:BOOL=OFF')
            options.append('-DCMAKE_SKIP_BUILD_RPATH:BOOL=TRUE')
            options.append('-DGMX_BUILD_SHARED_EXE:BOOL=OFF')

        if '+cuda' in self.spec:
            options.append('-DGMX_GPU:BOOL=ON')
            options.append('-DCUDA_TOOLKIT_ROOT_DIR:STRING=' +
                           self.spec['cuda'].prefix)

        return options

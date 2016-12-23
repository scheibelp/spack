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
from spack import *


class Octopus(Package):
    """A real-space finite-difference (time-dependent) density-functional
    theory code."""

    homepage = "http://www.tddft.org/programs/octopus/"
    url      = "http://www.tddft.org/programs/octopus/down.php?file=5.0.1/octopus-5.0.1.tar.gz"

    version('5.0.1', '2b6392ab67b843f9d4ca7413fc07e822')

    depends_on('blas')
    depends_on('gsl')
    depends_on('lapack')
    depends_on('libxc')
    depends_on('mpi')
    depends_on('fftw+mpi')

    # optional dependencies:
    # TODO: scalapack, metis, parmetis, netcdf, etsf-io, sparskit, arpack,
    # feast, libfm, pfft, isf, pnfft

    def install(self, spec, prefix):
        lapack = spec['lapack'].lapack_libs
        blas = spec['blas'].blas_libs
        args = []
        args.extend([
            '--prefix=%s' % prefix,
            '--with-blas=%s' % blas.ld_flags,
            '--with-lapack=%s' % lapack.ld_flags,
            '--with-gsl-prefix=%s' % spec['gsl'].prefix,
            '--with-libxc-prefix=%s' % spec['libxc'].prefix,
            'CC=%s' % spec['mpi'].mpicc,
            'FC=%s' % spec['mpi'].mpifc,
            '--enable-mpi',
            '--with-fft-lib=-L%s -lfftw3' % spec['fftw'].prefix.lib
            # --with-blacs=${prefix}/lib/libscalapack.dylib
            # --with-netcdf-prefix=netcdf-fortran
            # --with-etsf-io-prefix=
            # --with-sparskit=${prefix}/lib/libskit.a
            # --with-pfft-prefix=${prefix} --with-mpifftw-prefix=${prefix}
            # --with-arpack=${prefix}/lib/libarpack.dylib
            # --with-parpack=${prefix}/lib/libparpack.dylib
            # --with-metis-prefix=${prefix} --with-parmetis-prefix=${prefix}
            # --with-berkeleygw-prefix=${prefix}
        ])

        # When preprocessor expands macros (i.e. CFLAGS) defined as quoted
        # strings the result may be > 132 chars and is terminated.
        # This will look to a compiler as an Unterminated character constant
        # and produce Line truncated errors. To vercome this, add flags to
        # let compiler know that the entire line is meaningful.
        # TODO: For the lack of better approach, assume that clang is mixed
        # with GNU fortran.
        if spec.satisfies('%clang') or spec.satisfies('%gcc'):
            args.extend([
                'FCFLAGS=-O2 -ffree-line-length-none'
            ])

        configure(*args)
        make()
        # short tests take forever...
        # make('check-short')
        make('install')

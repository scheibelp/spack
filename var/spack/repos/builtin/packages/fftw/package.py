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


from spack import *


class Fftw(Package):
    """
    FFTW is a C subroutine library for computing the discrete Fourier transform (DFT) in one or more dimensions, of
    arbitrary input size, and of both real and complex data (as well as of even/odd data, i.e. the discrete cosine/sine
    transforms or DCT/DST). We believe that FFTW, which is free software, should become the FFT library of choice for
    most applications.
    """
    homepage = "http://www.fftw.org"
    url      = "http://www.fftw.org/fftw-3.3.4.tar.gz"

    version('3.3.4', '2edab8c06b24feeb3b82bbb3ebf3e7b3')

    variant('float', default=True, description='Produces a single precision version of the library')
    variant('long_double', default=True, description='Produces a long double precision version of the library')
    variant('quad', default=False, description='Produces a quad precision version of the library (works only with GCC and libquadmath)')

    variant('mpi', default=False, description='Activate MPI support')

    depends_on('mpi', when='+mpi')

    # TODO : add support for architecture specific optimizations as soon as targets are supported

    def install(self, spec, prefix):
        options = ['--prefix=%s' % prefix,
                   '--enable-shared',
                   '--enable-threads',
                   '--enable-openmp']
        if not self.compiler.f77 or not self.compiler.fc:
            options.append("--disable-fortran")
        if '+mpi' in spec:
            options.append('--enable-mpi')

        configure(*options)
        make()
        make("install")

        if '+float' in spec:
            configure('--enable-float', *options)
            make()
            make("install")
        if '+long_double' in spec:
            configure('--enable-long-double', *options)
            make()
            make("install")
        if '+quad' in spec:
            configure('--enable-quad-precision', *options)
            make()
            make("install")

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


class Libpsl(AutotoolsPackage):
    """libpsl - C library to handle the Public Suffix List."""

    homepage = "https://github.com/rockdaboot/libpsl"
    url      = "https://github.com/rockdaboot/libpsl/releases/download/libpsl-0.17.0/libpsl-0.17.0.tar.gz"

    version('0.17.0', 'fed13f33d0d6dc13ef24de255630bfcb')

    depends_on('icu4c')

    depends_on('gettext', type='build')
    depends_on('pkgconfig', type='build')
    depends_on('python@2.7:', type='build')

    depends_on('valgrind~mpi~boost', type='test')

    def configure_args(self):
        spec = self.spec

        args = [
            'PYTHON={0}'.format(spec['python'].command.path),
        ]

        if self.run_tests:
            args.append('--enable-valgrind-tests')
        else:
            args.append('--disable-valgrind-tests')

        return args

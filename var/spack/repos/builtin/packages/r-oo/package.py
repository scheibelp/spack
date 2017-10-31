##############################################################################
# Copyright (c) 2013-2017, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory.
#
# This file is part of Spack.
# Created by Todd Gamblin, tgamblin@llnl.gov, All rights reserved.
# LLNL-CODE-647188
#
# For details, see https://github.com/llnl/spack
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


class ROo(RPackage):
    """Methods and classes for object-oriented programming in R with
    or without references. Large effort has been made on making
    definition of methods as simple as possible with a minimum of
    maintenance for package developers. The package has been developed
    since 2001 and is now considered very stable. This is a
    cross-platform package implemented in pure R that defines
    standard S3 classes without any tricks."""

    homepage = "https://github.com/HenrikBengtsson/R.oo"
    url      = "https://cran.rstudio.com/src/contrib/R.oo_1.21.0.tar.gz"
    list_url = "https://cran.r-project.org/src/contrib/Archive/R.oo"

    version('1.21.0', 'f0062095c763faaeba30558303f68bc3')

    depends_on('r-methodss3', type=('build', 'run'))

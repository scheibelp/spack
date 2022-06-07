# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)


from spack.package import *


class PyThreadpoolctl(PythonPackage):
    """Python helpers to limit the number of threads used in the
    threadpool-backed of common native libraries used for scientific
    computing and data science (e.g. BLAS and OpenMP)."""

    homepage = "https://github.com/joblib/threadpoolctl"
    pypi = "threadpoolctl/threadpoolctl-2.0.0.tar.gz"

    version('3.0.0', sha256='d03115321233d0be715f0d3a5ad1d6c065fe425ddc2d671ca8e45e9fd5d7a52a')
    version('2.0.0', sha256='48b3e3e9ee079d6b5295c65cbe255b36a3026afc6dde3fb49c085cd0c004bbcf')

    depends_on('python@3.5:', type=('build', 'run'))
    depends_on('python@3.6:', type=('build', 'run'), when='@3.0.0:')
    depends_on('py-flit', type='build')

# Copyright 2013-2019 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack import *


class Gapbs(MakefilePackage):
    """The GAP Benchmark Suite is intended to help graph processing research by
    standardizing evaluations. Fewer differences between graph processing
    evaluations will make it easier to compare different research efforts and
    quantify improvements. The benchmark not only specifies graph kernels,
    input graphs, and evaluation methodologies, but it also provides an
    optimized baseline implementation (this repo). These baseline
    implementations are representative of state-of-the-art performance, and
    thus new contributions should outperform them to demonstrate an
    improvement."""

    homepage = "http://gap.cs.berkeley.edu/benchmark.html"
    url      = "https://github.com/sbeamer/gapbs/archive/v1.0.tar.gz"

    version('1.0', 'ac2efa793f44e58553449f42b9779f3ff2d47634')

    variant('serial', default=False, description='Version with no parallelism')

    def build(self, spec, prefix):
        cxx_flags = ['-O3', self.compiler.cxx11_flag]

        if '-serial' in spec:
            cxx_flags.append(self.compiler.openmp_flag)

        make('CXX_FLAGS=' + ' '.join(cxx_flags))

    def install(self, spec, prefix):
        mkdirp(prefix.bin)
        for app in ["bc", "bfs", "cc", "converter", "pr", "sssp", "tc"]:
            install(app, prefix.bin)

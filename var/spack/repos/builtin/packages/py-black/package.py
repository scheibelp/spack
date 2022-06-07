# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack.package import *


class PyBlack(PythonPackage):
    """Black is the uncompromising Python code formatter. By using it, you agree to
    cede control over minutiae of hand-formatting. In return, Black gives you
    speed, determinism, and freedom from pycodestyle nagging about formatting.
    """

    homepage = "https://github.com/psf/black"
    pypi = "black/black-22.1.0.tar.gz"

    maintainers = ['adamjstewart']

    version('22.3.0', sha256='35020b8886c022ced9282b51b5a875b6d1ab0c387b31a065b84db7c33085ca79')
    version('22.1.0', sha256='a7c0192d35635f6fc1174be575cb7915e92e5dd629ee79fdaf0dcfa41a80afb5')

    variant('d', default=False, description='enable blackd HTTP server')
    variant('colorama', default=False, description='enable colorama support')
    variant('uvloop', default=False, description='enable uvloop support')
    variant('jupyter', default=False, description='enable Jupyter support')

    # pyproject.toml
    depends_on('py-setuptools@45:', type=('build', 'run'))
    depends_on('py-setuptools-scm@6.3.1:+toml', type='build')

    # setup.py
    depends_on('python@3.6.2:', type=('build', 'run'))
    depends_on('py-click@8:', type=('build', 'run'))
    depends_on('py-platformdirs@2:', type=('build', 'run'))
    depends_on('py-tomli@1.1:', when='@22.3: ^python@:3.10', type=('build', 'run'))
    depends_on('py-tomli@1.1:', when='@22.1', type=('build', 'run'))
    depends_on('py-typed-ast@1.4.2:', when='^python@:3.7', type=('build', 'run'))
    depends_on('py-pathspec@0.9:', type=('build', 'run'))
    depends_on('py-dataclasses@0.6:', when='^python@:3.6', type=('build', 'run'))
    depends_on('py-typing-extensions@3.10:', when='^python@:3.9', type=('build', 'run'))
    depends_on('py-mypy-extensions@0.4.3:', type=('build', 'run'))
    depends_on('py-colorama@0.4.3:', when='+colorama', type=('build', 'run'))
    depends_on('py-aiohttp@3.7.4:', when='+d', type=('build', 'run'))
    depends_on('py-uvloop@0.15.2:', when='+uvloop', type=('build', 'run'))
    depends_on('py-ipython@7.8:', when='+jupyter', type=('build', 'run'))
    depends_on('py-tokenize-rt@3.2:', when='+jupyter', type=('build', 'run'))

    @property
    def import_modules(self):
        modules = ['blib2to3', 'blib2to3.pgen2', 'black']

        if '+d' in self.spec:
            modules.append('blackd')

        return modules

# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack import *


class PyHepunits(PythonPackage):
    """Units and constants in the HEP system of units."""

    git = "https://github.com/scikit-hep/hepunits.git"
    url = "https://pypi.io/packages/source/h/hepunits/hepunits-1.2.1.tar.gz"
    homepage = "https://github.com/scikit-hep/hepunits"

    tags = ['hep']

    maintainers = ['vvolkl']

    version('master', branch='master')
    version('1.2.1', sha256='b05b0dda32bf797806d506d7508d4eb23b78f34d67bbba9348a2b4a9712666fa')

    depends_on('python@2.7:2.8,3.5:', type=('build', 'run'))
    depends_on('py-setuptools', type='build')
    depends_on('py-setuptools-scm', type='build')
    depends_on('py-toml', type='build')

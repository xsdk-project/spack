# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack import *
from spack.operating_systems.mac_os import macos_version
import sys
import re


class Bison(AutotoolsPackage, GNUMirrorPackage):
    """Bison is a general-purpose parser generator that converts
    an annotated context-free grammar into a deterministic LR or
    generalized LR (GLR) parser employing LALR(1) parser tables."""

    homepage = "https://www.gnu.org/software/bison/"
    gnu_mirror_path = "bison/bison-3.6.4.tar.gz"

    executables = ['^bison$']

    version('3.6.4', sha256='8183de64b5383f3634942c7b151bf2577f74273b2731574cdda8a8f3a0ab13e9')
    version('3.6.3', sha256='4b4c4943931e811f1073006ce3d8ee022a02b11b501e9cbf4def3613b24a3e63')
    version('3.6.2', sha256='e28ed3aad934de2d1df68be209ac0b454f7b6d3c3d6d01126e5cd2cbadba089a')
    version('3.6.1', sha256='1120f8bfe2cc13e5e1e3f671dc41b1a535ca5a75a70d5b349c19da9d4389f74d')
    version('3.6', sha256='f630645e330bde5847266cc5c8194f0135ced75cced150358d9abe572b95f81c')
    version('3.5.3', sha256='34e201d963156618a0ea5bc87220f660a1e08403dd3c7c7903d4f38db3f40039')
    version('3.5.2', sha256='b4dbb6dd080f4db7f344f16506502973ca2b15f15c7dbbd1c1c278a456d094fa')
    version('3.5.1', sha256='4cef2322d96751be1c0d04f3e57adbb30e7fea83af9c00f98efa6e7509296f25')
    version('3.5', sha256='0b36200b9868ee289b78cefd1199496b02b76899bbb7e84ff1c0733a991313d1')
    version('3.4.2', sha256='ff3922af377d514eca302a6662d470e857bd1a591e96a2050500df5a9d59facf')
    version('3.4.1', sha256='7007fc89c216fbfaff5525359b02a7e5b612694df5168c74673f67055f015095')
    version('3.3.2', sha256='0fda1d034185397430eb7b0c9e140fb37e02fbfc53b90252fa5575e382b6dbd1')
    version('3.0.5', sha256='cd399d2bee33afa712bac4b1f4434e20379e9b4099bce47189e09a7675a2d566')
    version('3.0.4', sha256='b67fd2daae7a64b5ba862c66c07c1addb9e6b1b05c5f2049392cfd8a2172952e')
    version('2.7',   sha256='19bbe7374fd602f7a6654c131c21a15aebdc06cc89493e8ff250cb7f9ed0a831')

    # https://lists.gnu.org/archive/html/bug-bison/2019-08/msg00008.html
    patch('parallel.patch', when='@3.4.2')

    provides('yacc')

    depends_on('diffutils', type='build')
    depends_on('m4', type=('build', 'run'))
    depends_on('perl', type='build')
    depends_on('help2man', type='build')

    patch('pgi.patch', when='@3.0.4')
    patch('nvhpc.patch', when='%nvhpc')

    conflicts('%intel@:14', when='@3.4.2:',
              msg="Intel 14 has immature C11 support")

    if sys.platform == 'darwin' and macos_version() >= Version('10.13'):
        patch('secure_snprintf.patch', level=0, when='@3.0.4')

    build_directory = 'spack-build'

    @classmethod
    def determine_version(cls, exe):
        output = Executable(exe)('--version', output=str, error=str)
        match = re.search(r'bison \(GNU Bison\)\s+(\S+)', output)
        return match.group(1) if match else None

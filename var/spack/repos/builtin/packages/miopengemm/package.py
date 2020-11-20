# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack import *


class Miopengemm(CMakePackage):
    """An OpenCL general matrix multiplication (GEMM) API
    and kernel generator"""

    homepage = "https://github.com/ROCmSoftwarePlatform/MIOpenGEMM"
    url      = "https://github.com/ROCmSoftwarePlatform/MIOpenGEMM/archive/rocm-3.8.0.tar.gz"

    maintainers = ['srekolam', 'arjun-raj-kuppala']

    def url_for_version(self, version):
        if version == Version('1.1.6'):
            return "https://github.com/ROCmSoftwarePlatform/MIOpenGEMM/archive/1.1.6.tar.gz"
        url = "https://github.com/ROCmSoftwarePlatform/MIOpenGEMM/archive/rocm-{0}.tar.gz"
        return url.format(version)

    version('3.9.0', sha256='8e1273c35d50e9fd92e303d9bcbdd42ddbfda20844b3248428e16b54928f6dc2')
    version('3.8.0', sha256='d76f5b4b3b9d1e3589a92f667f39eab5b5ab54ec3c4e04d412035be3ec623547')
    version('3.7.0', sha256='392b280ca564b120f6b24ec1fe8782cba08a8a5fb52938e8bc3dc887d3fd08fa')
    version('1.1.6', sha256='9ab04903794c6a59432928eaec92c687d51e2b4fd29630cf227cbc49d56dc69b')

    variant('build_type', default='Release', values=("Release", "Debug"), description='CMake build type')

    depends_on('cmake@3:', type='build')
    depends_on('rocm-cmake@3.5.0', type='build', when='@1.1.6')
    depends_on('rocm-opencl@3.5.0', type='build', when='@1.1.6')
    for ver in ['3.7.0', '3.8.0', '3.9.0']:
        depends_on('rocm-cmake@' + ver, type='build', when='@' + ver)
        depends_on('rocm-opencl@' + ver, type='build', when='@' + ver)

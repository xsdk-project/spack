# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)


from spack import *


class Rocthrust(CMakePackage):
    """Thrust is a parallel algorithm library. This library has been ported to
       HIP/ROCm platform, which uses the rocPRIM library. The HIP ported
       library works on HIP/ROCm platforms"""

    homepage = "https://github.com/ROCmSoftwarePlatform/rocThrust"
    url      = "https://github.com/ROCmSoftwarePlatform/rocThrust/archive/rocm-3.8.0.tar.gz"

    maintainers = ['srekolam', 'arjun-raj-kuppala']

    version('3.9.0', sha256='65f5e74d72c5aaee90459468d693b212af7d56e31098ee8237b18d1b4d620eb0')
    version('3.8.0', sha256='39350aeb8bfbcd09e387717b2a05c7e3a19e0fa85ff4284b967bb8fae12f9013')
    version('3.7.0', sha256='4cb923dde5eec150a566cb10d23ee5c7ce3aa892c4dea94886a89d95b90f3bdd')
    version('3.5.0', sha256='0d1bac1129d17bb1259fd06f5c9cb4c1620d1790b5c295b866fb3442d18923cb')

    variant('build_type', default='Release', values=("Release", "Debug"),
            description='CMake build type')

    depends_on('cmake@3:', type='build')
    depends_on('numactl', when='@3.7.0')
    for ver in ['3.5.0', '3.7.0', '3.8.0', '3.9.0']:
        depends_on('hip@' + ver, type='build', when='@' + ver)
        depends_on('rocm-device-libs@' + ver, type='build', when='@' + ver)
        depends_on('comgr@' + ver, type='build', when='@' + ver)
        depends_on('hsa-rocr-dev@' + ver, type='build', when='@' + ver)
        depends_on('rocprim@' + ver, type='build', when='@' + ver)

    def setup_build_environment(self, env):
        env.set('CXX', self.spec['hip'].hipcc)

    def cmake_args(self):
        spec = self.spec

        args = [
            '-DCMAKE_MODULE_PATH={0}/cmake'.format(spec['hip'].prefix)
        ]

        return args

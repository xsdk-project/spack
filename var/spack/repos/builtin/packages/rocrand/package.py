# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)


from spack import *


class Rocrand(CMakePackage):
    """The rocRAND project provides functions that generate
       pseudo-random and quasi-random numbers."""

    homepage = "https://github.com/ROCmSoftwarePlatform/rocRAND"
    url      = "https://github.com/ROCmSoftwarePlatform/rocRAND/archive/rocm-3.8.0.tar.gz"

    maintainers = ['srekolam', 'arjun-raj-kuppala']

    version('3.9.0', sha256='a500a3a83be36b6c91aa062dc6eef1f9fc1d9ee62422d541cc279513d98efa91')
    version('3.8.0', sha256='79eb84d41363a46ed9bb18d9757cf6a419d2f48bb6a71b8e4db616a5007a6560')
    version('3.7.0', sha256='5e43fe07afe2c7327a692b3b580875bae6e6ee790e044c053fffafbfcbc14860')
    version('3.5.0', sha256='592865a45e7ef55ad9d7eddc8082df69eacfd2c1f3e9c57810eb336b15cd5732')

    depends_on('cmake@3.5.1:', type='build')
    depends_on('numactl', when='@3.7.0:')
    for ver in ['3.5.0', '3.7.0', '3.8.0', '3.9.0']:
        depends_on('hip@' + ver, type='build', when='@' + ver)
        depends_on('comgr@' + ver, type='build', when='@' + ver)
        depends_on('rocm-device-libs@' + ver, type='build', when='@' + ver)
        depends_on('llvm-amdgpu@' + ver, type='build', when='@' + ver)
        depends_on('rocminfo@' + ver, type='build', when='@' + ver)
        depends_on('hsa-rocr-dev@' + ver, type='build', when='@' + ver)

    def setup_build_environment(self, env):
        env.set('CXX', self.spec['hip'].hipcc)

    def cmake_args(self):
        args = ['-DBUILD_BENCHMARK=OFF',
                '-DBUILD_TEST=OFF']
        return args

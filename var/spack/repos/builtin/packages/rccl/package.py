# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack import *


class Rccl(CMakePackage):
    """RCCL (pronounced "Rickle") is a stand-alone library
    of standard collective communication routines for GPUs,
    implementing all-reduce, all-gather, reduce, broadcast,
    and reduce-scatter."""

    homepage = "https://github.com/RadeonOpenCompute/rccl"
    url      = "https://github.com/ROCmSoftwarePlatform/rccl/archive/rocm-3.7.0.tar.gz"

    maintainers = ['srekolam', 'arjun-raj-kuppala']

    version('3.9.0', sha256='ff9d03154d668093309ff814a33788f2cc093b3c627e78e42ae246e6017408b0')
    version('3.8.0', sha256='0b6676d06bdb1f65d511a95db9f842a3443def83d75759dfdf812b5e62d8c910')
    version('3.7.0', sha256='8273878ff71aac2e7adf5cc8562d2933034c6c6b3652f88fbe3cd4f2691036e3')
    version('3.5.0', sha256='290b57a66758dce47d0bfff3f5f8317df24764e858af67f60ddcdcadb9337253')

    patch('0001-Fix-numactl-path-issue.patch', when='@3.7.0:')

    depends_on('cmake@3:', type='build')
    for ver in ['3.5.0', '3.7.0', '3.8.0', '3.9.0']:
        depends_on('rocm-cmake@' + ver, type='build', when='@' + ver)
        depends_on('hip@' + ver, type=('build', 'run'), when='@' + ver)
        depends_on('rocm-device-libs@' + ver, type=('build', 'run'), when='@' + ver)
        depends_on('comgr@' + ver, type='build', when='@' + ver)
        depends_on('hsa-rocr-dev@' + ver, type='build', when='@' + ver)
        if ver in ['3.7.0', '3.8.0', '3.9.0']:
            depends_on('numactl@2.0.12', type=('build', 'link'), when='@' + ver)

    def setup_build_environment(self, env):
        env.set('CXX', self.spec['hip'].hipcc)

    def cmake_args(self):
        args = []
        if '@3.7.0:' in self.spec:
            numactl_prefix = self.spec['numactl'].prefix
            args.append('-DNUMACTL_DIR={0}'.format(numactl_prefix))
        return args

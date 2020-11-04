# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)


from spack import *


class HsaRocrDev(CMakePackage):
    """This repository includes the user mode API nterfaces and libraries
       necessary for host applications to launch computer kernels to available
       HSA ROCm kernel agents.AMD Heterogeneous System Architecture HSA -
       Linux HSA Runtime for Boltzmann (ROCm) platforms."""

    homepage = "https://github.com/RadeonOpenCompute/ROCR-Runtime"
    url      = "https://github.com/RadeonOpenCompute/ROCR-Runtime/archive/rocm-3.9.0.tar.gz"

    maintainers = ['srekolam', 'arjun-raj-kuppala']

    version('3.9.0', sha256='d722fb61f62037894957856f2c2d17231c4622bdf75db372321ee30206dceeb6')
    version('3.8.0', sha256='1dfad4d89d6c099e15073ed38e083bcf6cc463470dcc8a1e1b9e22060c060c72')
    version('3.7.0', sha256='0071d14431f73ce74574e61d0786f2b7cf34b14ea898a1f54b6e1b06b2d468c0')
    version('3.5.0', sha256='52c12eec3e3404c0749c70f156229786ee0c3e6d3c979aed9bbaea500fa1f3b8')

    variant('build_type', default='Release', values=("Release", "Debug"), description='CMake build type')

    depends_on('cmake@3:', type="build")
    depends_on('libelf@0.8:', type='link')
    for ver in ['3.5.0', '3.7.0', '3.8.0', '3.9.0']:
        depends_on('hsakmt-roct@' + ver, type=('link', 'run'), when='@' + ver)
    for ver in ['3.7.0', '3.8.0', '3.9.0']:
        depends_on('llvm-amdgpu@' + ver, type=('link', 'run'), when='@' + ver)

    # Both 3.5.0 and 3.7.0 force INSTALL_RPATH in different ways
    patch('0001-Do-not-set-an-explicit-rpath-by-default-since-packag.patch', when='@3.5.0')
    patch('0002-Remove-explicit-RPATH-again.patch', when='@3.7.0:')

    root_cmakelists_dir = 'src'

    def cmake_args(self):
        libelf_include = self.spec['libelf'].prefix.include.libelf
        args = ['-DLIBELF_INCLUDE_DIRS=%s' % libelf_include]

        if '@3.7.0:' in self.spec:
            args.append('-DIMAGE_SUPPORT=OFF')

        return args

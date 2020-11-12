# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)


from spack import *


class Rocblas(CMakePackage):
    """Radeon Open Compute BLAS library"""

    homepage = "https://github.com/ROCmSoftwarePlatform/rocBLAS/"
    url      = "https://github.com/ROCmSoftwarePlatform/rocBLAS/archive/rocm-3.5.0.tar.gz"

    maintainers = ['srekolam', 'arjun-raj-kuppala']

    version('3.9.0', sha256='3ecd2d9fd2be0e1697a191d143a2d447b53a91ae01afb50231d591136ad5e2fe')
    version('3.8.0', sha256='568a9da0360349b1b134d74cc67cbb69b43c06eeca7c33b50072cd26cd3d8900')
    version('3.7.0', sha256='9425db5f8e8b6f7fb172d09e2a360025b63a4e54414607709efc5acb28819642')
    version('3.5.0', sha256='8560fabef7f13e8d67da997de2295399f6ec595edfd77e452978c140d5f936f0')

    amdgpu_targets = ('all', 'gfx803', 'gfx900', 'gfx906', 'gfx908')

    variant('amdgpu_target', default='all', multi=True, values=amdgpu_targets)

    depends_on('cmake@3:', type='build')

    for ver in ['3.5.0', '3.7.0', '3.8.0', '3.9.0']:
        depends_on('rocm-cmake@' + ver, type='build', when='@' + ver)
        depends_on('rocm-device-libs@' + ver, type='build', when='@' + ver)
        depends_on('hip@' + ver, when='@' + ver)
        depends_on('comgr@' + ver, type='build', when='@' + ver)
        # used in Tensile
        depends_on('rocm-smi@' + ver, type='build', when='@' + ver)
        depends_on('llvm-amdgpu@' + ver, type='build', when='@' + ver)

    # This is the default library format since 3.7.0
    depends_on('msgpack-c@3:', when='@3.7:')

    depends_on('python', type='build')
    depends_on('py-virtualenv', type='build')
    depends_on('perl-file-which', type='build')
    depends_on('py-pyyaml', type='build')
    depends_on('py-wheel', type='build')
    depends_on('py-msgpack', type='build')

    resource(name='Tensile',
             git='https://github.com/ROCmSoftwarePlatform/Tensile.git',
             commit='f842a1a4427624eff6cbddb2405c36dec9a210cd',
             when='@3.5.0')

    resource(name='Tensile',
             git='https://github.com/ROCmSoftwarePlatform/Tensile.git',
             commit='af71ea890a893e647bf2cf4571a90297d65689ca',
             when='@3.7.0')

    resource(name='Tensile',
             git='https://github.com/ROCmSoftwarePlatform/Tensile.git',
             commit='9123205f9b5f95c96ff955695e942d2c3b321cbf',
             when='@3.8.0')

    resource(name='Tensile',
             git='https://github.com/ROCmSoftwarePlatform/Tensile.git',
             commit='b68edc65aaeed08c71b2b8622f69f83498b57d7a',
             when='@3.9.0')

    # Status: https://github.com/ROCmSoftwarePlatform/Tensile/commit/a488f7dadba34f84b9658ba92ce9ec5a0615a087
    # Not yet landed in 3.7.0, nor 3.8.0.
    patch('0001-Fix-compilation-error-with-StringRef-to-basic-string.patch', when='@:3.8')

    def setup_build_environment(self, env):
        env.set('CXX', self.spec['hip'].hipcc)

    def cmake_args(self):
        archs = ",".join(self.spec.variants['amdgpu_target'].value)

        tensile = join_path(self.stage.source_path, 'Tensile')

        args = [
            '-Damd_comgr_DIR={0}'.format(self.spec['comgr'].prefix),
            '-DBUILD_CLIENTS_TESTS=OFF',
            '-DBUILD_CLIENTS_BENCHMARKS=OFF',
            '-DBUILD_CLIENTS_SAMPLES=OFF',
            '-DRUN_HEADER_TESTING=OFF',
            '-DBUILD_WITH_TENSILE=ON',
            '-DTensile_TEST_LOCAL_PATH={0}'.format(tensile),
            '-DTensile_COMPILER=hipcc',
            '-DTensile_ARCHITECTURE={0}'.format(archs),
            '-DTensile_LOGIC=asm_full',
            '-DTensile_CODE_OBJECT_VERSION=V3',
            '-DBUILD_WITH_TENSILE_HOST={0}'.format(
                'ON' if '@3.7.0:' in self.spec else 'OFF'
            )
        ]

        if '@3.7.0:' in self.spec:
            args.append('-DTensile_LIBRARY_FORMAT=msgpack')

        return args

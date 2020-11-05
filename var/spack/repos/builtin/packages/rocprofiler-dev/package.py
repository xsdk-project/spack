# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)


from spack import *


class RocprofilerDev(CMakePackage):
    """ROCPROFILER library for AMD HSA runtime API extension support"""

    homepage = "https://github.com/ROCm-Developer-Tools/rocprofiler"
    url      = "https://github.com/ROCm-Developer-Tools/rocprofiler/archive/rocm-3.8.0.tar.gz"

    maintainers = ['srekolam', 'arjun-raj-kuppala']

    version('3.9.0', sha256='f07ddd9bf2f86550c8d243f887e9bde9d4f2ceec81ecc6393012aaf2a45999e8')
    version('3.8.0', sha256='38ad3ac20f60f3290ce750c34f0aad442354b1d0a56b81167a018e44ecdf7fff')
    version('3.7.0', sha256='d3f03bf850cbd86ca9dfe6e6cc6f559d8083b0f3ea4711d8260b232cb6fdd1cc')
    version('3.5.0', sha256='c42548dd467b7138be94ad68c715254eb56a9d3b670ccf993c43cd4d43659937')

    depends_on('cmake@3:', type='build')
    for ver in ['3.5.0', '3.7.0', '3.8.0', '3.9.0']:
        depends_on('hsakmt-roct@' + ver, type='build', when='@' + ver)
        depends_on('hsa-rocr-dev@' + ver, type='link', when='@' + ver)
        depends_on('rocminfo@' + ver, type='build', when='@' + ver)

    resource(name='roctracer-dev',
             url='https://github.com/ROCm-Developer-Tools/roctracer/archive/rocm-3.5.0.tar.gz',
             sha256='7af5326c9ca695642b4265232ec12864a61fd6b6056aa7c4ecd9e19c817f209e',
             expand=True,
             destination='',
             placement='roctracer',
             when='@3.5.0')

    resource(name='roctracer-dev',
             url='https://github.com/ROCm-Developer-Tools/roctracer/archive/rocm-3.7.0.tar.gz',
             sha256='6fa5b771e990f09c242237ab334b9f01039ec7d54ccde993e719c5d6577d1518',
             expand=True,
             destination='',
             placement='roctracer',
             when='@3.7.0')

    resource(name='roctracer-dev',
             url='https://github.com/ROCm-Developer-Tools/roctracer/archive/rocm-3.8.0.tar.gz',
             sha256='5154a84ce7568cd5dba756e9508c34ae9fc62f4b0b5731f93c2ad68b21537ed1',
             expand=True,
             destination='',
             placement='roctracer',
             when='@3.8.0')

    resource(name='roctracer-dev',
             url='https://github.com/ROCm-Developer-Tools/roctracer/archive/rocm-3.9.0.tar.gz',
             sha256='0678f9faf45058b16923948c66d77ba2c072283c975d167899caef969169b292',
             expand=True,
             destination='',
             placement='roctracer',
             when='@3.9.0')

    def patch(self):
        filter_file('${HSA_RUNTIME_LIB_PATH}/../include',
                    '${HSA_RUNTIME_LIB_PATH}/../include ${HSA_KMT_LIB_PATH}/..\
                     /include', 'test/CMakeLists.txt', string=True)

    def cmake_args(self):
        args = ['-DPROF_API_HEADER_PATH={0}/roctracer/inc/ext'.format(
                self.stage.source_path),
                '-DROCM_ROOT_DIR:STRING={0}/include'.format(
                self.spec['hsakmt-roct'].prefix)
                ]
        return args

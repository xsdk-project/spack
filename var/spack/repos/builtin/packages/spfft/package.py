# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)


from spack import *


class Spfft(CMakePackage, CudaPackage):
    """Sparse 3D FFT library with MPI, OpenMP, CUDA and ROCm support."""

    homepage = "https://github.com/eth-cscs/SpFFT"
    url      = "https://github.com/eth-cscs/SpFFT/archive/v0.9.8.zip"
    git      = "https://github.com/eth-cscs/SpFFT.git"

    version('develop', branch='develop')
    version('master', branch='master')

    version('0.9.13', sha256='5ccc93c9362bec14cfb6e31dd0e7ae7e48db0453ab49ebc9722041b69db759ef')
    version('0.9.12', sha256='1f7bf5164dcceb0e3bbce7d6ff9faef3145ad17cf3430149d40a98c43c010acc')
    version('0.9.11', sha256='36542a60378e8672654188dee006975ef9e10f502791459ff7ebf4b38451cb9b')
    version('0.9.10', sha256='9cbbb7ba5e53e17eeb45e809841d8272e5333f739c2442a99c3e255c1ddec3e9')
    version('0.9.9', sha256='a8fd7a2d767716bb73185ca03bf4c106c6981b79130f3e456e5d2e744a2b3ba0')
    version('0.9.8', sha256='f49fa51316bbfa68309e951d2375e1f6904120c93868cbe13bc2974c0b801a3f')

    variant('openmp', default=True, description="Build with OpenMP support")
    variant('mpi', default=True, description="enable MPI")
    variant('single_precision', default=False, description="Sinlge precision")
    variant('gpu_direct', default=False, description="GPU aware MPI")
    variant('static', default=False, description="build static library")
    variant('fortran', default=False, description="enable fortran")
    variant('build_type', default='Release', description='CMake build type',
            values=('Debug', 'Release', 'RelWithDebInfo'))
    depends_on('fftw-api@3')
    depends_on('mpi', when='+mpi')
    depends_on('cmake@3.11:', type='build')

    # ROCM variants + dependencies
    variant('rocm', default=False, description="Use ROCm backend")

    amdgpu_targets = (
        'gfx701', 'gfx801', 'gfx802', 'gfx803',
        'gfx900', 'gfx906', 'gfx908', 'gfx1010',
        'gfx1011', 'gfx1012'
    )

    depends_on('rocfft', when='+rocm')
    depends_on('hip', when='+rocm')
    depends_on('hsakmt-roct', when='+rocm', type='link')
    depends_on('hsa-rocr-dev', when='+rocm', type='link')
    variant('amdgpu_target', default='gfx803,gfx900,gfx906', multi=True, values=amdgpu_targets)

    depends_on('cuda@:10', when='@:0.9.11 +cuda')

    def cmake_args(self):
        spec = self.spec
        args = []
        if spec.satisfies('+openmp'):
            args += ["-DSPFFT_OMP=On"]
        if spec.satisfies('+mpi'):
            args += ["-DSPFFT_MPI=On"]
        if spec.satisfies('+single_precision'):
            args += ["-DSPFFT_SINGLE_PRECISION=On"]
        if spec.satisfies('+gpu_direct'):
            args += ["-DSPFFT_GPU_DIRECT=On"]
        if spec.satisfies('+cuda'):
            args += ["-DSPFFT_GPU_BACKEND=CUDA"]
        if spec.satisfies('+rocm'):
            archs = ",".join(self.spec.variants['amdgpu_target'].value)
            args += [
                '-DSPFFT_GPU_BACKEND=ROCM',
                '-DHIP_ROOT_DIR={0}'.format(spec['hip'].prefix),
                '-DHIP_HCC_FLAGS=--amdgpu-target={0}'.format(archs)
            ]
        if spec.satisfies('+fortran'):
            args += ["-DSPFFT_FORTAN=On"]
        if spec.satisfies('+static'):
            args += ["-DSPFFT_STATIC=On"]

        return args

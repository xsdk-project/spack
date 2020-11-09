# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)


from spack import *
import sys


class XsdkExamples(CMakePackage):
    """xSDK Examples show usage of libraries in the xSDK package."""

    homepage = 'http://xsdk.info'
    url      = 'https://github.com/xsdk-project/xsdk-examples/archive/v0.1.0.tar.gz'

    maintainers = ['acfisher', 'balay', 'balos1', 'luszczek']

    version('develop', git='https://github.com/xsdk-project/xsdk-examples.git',branch='master')
    version('0.6.0', git='https://github.com/xsdk-project/xsdk-examples.git',branch='master')
    version('0.1.0', sha256='d24cab1db7c0872b6474d69e598df9c8e25d254d09c425fb0a6a8d6469b8018f')

    variant('debug', default=False, description='Compile in debug mode')
    variant('cuda', default=False, description='Enable CUDA dependent packages')
    variant('trilinos', default=True, description='Enable trilinos package build')
    variant('datatransferkit', default=True, description='Enable datatransferkit package build')
    variant('omega-h', default=True, description='Enable omega-h package build')
    variant('strumpack', default=True, description='Enable strumpack package build')
    variant('dealii', default=True, description='Enable dealii package build')
    variant('phist', default=True, description='Enable phist package build')
    variant('ginkgo', default=True, description='Enable ginkgo package build')
    variant('libensemble', default=True, description='Enable py-libensemble package build')
    variant('precice', default=(sys.platform != 'darwin'),description='Enable precice package build')
    variant('butterflypack', default=True, description='Enable butterflypack package build')
    variant('heffte', default=True, description='Enable heffte package build')
    variant('slate', default=True, description='Enable slate package build')

    depends_on('hypre@develop+superlu-dist+shared', when='@develop')
    depends_on('hypre@2.20.0+superlu-dist+shared', when='@0.6.0')

    depends_on('mfem@develop+mpi+superlu-dist+petsc+sundials+examples+miniapps', when='@develop')
    depends_on('mfem@4.2.0+mpi+superlu-dist+petsc+sundials+examples+miniapps', when='@0.6.0')

    depends_on('superlu-dist@develop', when='@develop')
    depends_on('superlu-dist@6.4.0', when='@0.6.0')

    depends_on('trilinos@develop+hypre+superlu-dist+metis+hdf5~mumps+boost~suite-sparse+tpetra+nox+ifpack2+zoltan2+amesos2~exodus+dtk+intrepid2+shards gotype=int',
               when='@develop +trilinos')
    depends_on('trilinos@13.0.1+hypre+superlu-dist+metis+hdf5~mumps+boost~suite-sparse+tpetra+nox+ifpack2+zoltan2+amesos2~exodus~dtk+intrepid2+shards gotype=int',
               when='@0.6.0 +trilinos')
    depends_on('datatransferkit@3.1-rc2', when='@0.6.0 +trilinos +datatransferkit')

    depends_on('petsc +trilinos', when='+trilinos')
    depends_on('petsc +cuda', when='+cuda @0.6.0:')
    depends_on('petsc +batch', when='platform=cray @0.5.0:')
    depends_on('petsc@develop+mpi+hypre+superlu-dist+metis+hdf5~mumps+double~int64',
               when='@develop')
    depends_on('petsc@3.14.1+mpi+hypre+superlu-dist+metis+hdf5~mumps+double~int64',
               when='@0.6.0')

    depends_on('dealii +trilinos~adol-c', when='+trilinos +dealii')
    depends_on('dealii ~trilinos', when='~trilinos +dealii')
    depends_on('dealii@develop~assimp~python~doc~gmsh+petsc+slepc+mpi~int64+hdf5~netcdf+metis~sundials~ginkgo~symengine', when='@develop +dealii')
    depends_on('dealii@9.2.0~assimp~python~doc~gmsh+petsc+slepc+mpi~int64+hdf5~netcdf+metis~sundials~ginkgo~symengine', when='@0.6.0 +dealii')

    depends_on('pflotran@develop', when='@develop')
    depends_on('pflotran@xsdk-0.6.0', when='@0.6.0')

    depends_on('alquimia@develop', when='@develop')
    depends_on('alquimia@xsdk-0.6.0', when='@0.6.0')

    depends_on('sundials +cuda', when='+cuda @0.6.0:')
    depends_on('sundials +trilinos', when='+trilinos @0.6.0:')
    depends_on('sundials@develop~int64+hypre+petsc+superlu-dist', when='@develop')
    depends_on('sundials@5.5.0~int64+hypre+petsc+superlu-dist', when='@0.6.0')

    depends_on('plasma@20.9.20:', when='@develop %gcc@6.0:')
    depends_on('plasma@20.9.20:', when='@0.6.0 %gcc@6.0:')

    depends_on('magma@2.5.4', when='@develop +cuda')
    depends_on('magma@2.5.4', when='@0.6.0 +cuda')

    depends_on('amrex@develop', when='@develop %intel')
    depends_on('amrex@develop', when='@develop %gcc')
    depends_on('amrex@20.10', when='@0.6.0 %intel')
    depends_on('amrex@20.10', when='@0.6.0 %gcc')

    depends_on('slepc@develop', when='@develop')
    depends_on('slepc@3.14.0', when='@0.6.0')

    depends_on('omega-h +trilinos', when='+trilinos +omega-h')
    depends_on('omega-h ~trilinos', when='~trilinos +omega-h')
    depends_on('omega-h@develop', when='@develop +omega-h')
    depends_on('omega-h@9.32.5', when='@0.6.0 +omega-h')

    depends_on('strumpack ~cuda', when='~cuda @0.6.0:')
    depends_on('strumpack@master', when='@develop +strumpack')
    depends_on('strumpack@5.0.0', when='@0.6.0 +strumpack')

    depends_on('pumi@develop', when='@develop')
    depends_on('pumi@2.2.5', when='@0.6.0')

    tasmanian_openmp = '~openmp' if sys.platform == 'darwin' else '+openmp'
    depends_on('tasmanian@develop+xsdkflags+blas' + tasmanian_openmp, when='@develop')
    depends_on('tasmanian@develop+xsdkflags+blas+cuda+magma' + tasmanian_openmp, when='@develop +cuda')
    depends_on('tasmanian@7.3+xsdkflags+mpi+blas' + tasmanian_openmp, when='@0.6.0')
    depends_on('tasmanian@7.3+xsdkflags+mpi+blas+cuda+magma' + tasmanian_openmp, when='@0.6.0 +cuda')

    depends_on('phist kernel_lib=tpetra', when='+trilinos +phist')
    depends_on('phist kernel_lib=petsc', when='~trilinos +phist')
    depends_on('phist@develop ~fortran ~scamac ~host', when='@develop +phist')
    depends_on('phist@1.9.3 ~fortran ~scamac ~openmp ~host ~int64', when='@0.6.0 +phist')

    depends_on('ginkgo@develop ~openmp', when='@develop +ginkgo')
    depends_on('ginkgo@develop ~openmp+cuda', when='@develop +ginkgo +cuda')
    depends_on('ginkgo@1.3.0 ~openmp', when='@0.6.0 +ginkgo')
    depends_on('ginkgo@1.3.0 ~openmp+cuda', when='@0.6.0 +cuda +ginkgo')

    depends_on('py-libensemble@develop+petsc4py', type='run', when='@develop +libensemble')
    depends_on('py-libensemble@0.7.1+petsc4py', type='run', when='@0.6.0 +libensemble')

    depends_on('precice ~petsc', when='platform=cray +precice')
    depends_on('precice@develop', when='@develop +precice')
    depends_on('precice@2.1.1', when='@0.6.0 +precice')

    depends_on('butterflypack@master', when='@develop +butterflypack')
    depends_on('butterflypack@1.2.1', when='@0.6.0 +butterflypack')

    depends_on('heffte +fftw+cuda+magma', when='+cuda +heffte')
    depends_on('openmpi +cuda', when='+cuda +heffte')
    depends_on('heffte@develop+fftw', when='@develop +heffte')
    depends_on('heffte@2.0.0+fftw', when='@0.6.0 +heffte')

    depends_on('slate@2020.10.00 ~cuda', when='~cuda +slate %gcc@6.0:')
    depends_on('slate@2020.10.00 +cuda', when='+cuda +slate %gcc@6.0:')

    def cmake_args(self):
        spec = self.spec
        args = [
            '-DCMAKE_C_COMPILER=%s' % spec['mpi'].mpicc,
            '-DMPI_DIR=%s' % spec['mpi'].prefix,
            '-DSUNDIALS_DIR=%s'     % spec['sundials'].prefix,
            '-DPETSC_DIR=%s'         % spec['petsc'].prefix,
            '-DPETSC_INCLUDE_DIR=%s' % spec['petsc'].prefix.include,
            '-DPETSC_LIBRARY_DIR=%s' % spec['petsc'].prefix.lib,
            '-DSUPERLUDIST_INCLUDE_DIR=%s' %
            spec['superlu-dist'].prefix.include,
            '-DSUPERLUDIST_LIBRARY_DIR=%s' % spec['superlu-dist'].prefix.lib,
        ]
        if 'trilinos' in spec:
            args.extend([
                '-DTRILINOS_DIR:PATH=%s' % spec['trilinos'].prefix,
            ])
        return args

# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack import *
import os


class AwsParallelcluster(PythonPackage):
    """AWS ParallelCluster is an AWS supported Open Source cluster management
    tool to deploy and manage HPC clusters in the AWS cloud."""

    homepage = "https://github.com/aws/aws-parallelcluster"
    url      = "https://pypi.io/packages/source/a/aws-parallelcluster/aws-parallelcluster-2.10.0.tar.gz"

    maintainers = [
        'sean-smith', 'demartinofra', 'enrico-usai', 'lukeseawalker', 'rexcsn',
        'ddeidda', 'tilne'
    ]
    import_modules = [
        'pcluster', 'awsbatch', 'pcluster.dcv', 'pcluster.configure',
        'pcluster.config', 'pcluster.networking'
    ]

    version('2.10.0', sha256='a7a27871b4f54cb913b0c1233e675131e9b2099549af0840d32c36b7e91b104b')
    version('2.9.1', sha256='12dc22286cd447a16931f1f8619bdd47d4543fd0de7905d52b6c6f83ff9db8a3')
    version('2.9.0', sha256='e98a8426bc46aca0860d9a2be89bbc4a90aab3ed2f60ca6c385b595fbbe79a78')
    version('2.8.1', sha256='c183dc3f053bc2445db724e561cea7f633dd5e7d467a7b3f9b2f2f703f7d5d49')
    version('2.8.0', sha256='4e67539d49fe987884a3ed7198dc13bc8a3a1778f0b3656dfe0ae899138678f2')
    version('2.7.0', sha256='7c34995acfcc256a6996541d330575fc711e1fd5735bf3d734d4e96c1dc8df60')
    version('2.6.1', sha256='2ce9015d90b5d4dc88b46a44cb8a82e8fb0bb2b4cca30335fc5759202ec1b343')
    version('2.6.0', sha256='aaed6962cf5027206834ac24b3d312da91e0f96ae8607f555e12cb124b869f0c')
    version('2.5.1', sha256='4fd6e14583f8cf81f9e4aa1d6188e3708d3d14e6ae252de0a94caaf58be76303')
    version('2.5.0', sha256='3b0209342ea0d9d8cc95505456103ad87c2d4e35771aa838765918194efd0ad3')

    depends_on('python@2.7:', type=('build', 'run'))

    depends_on('py-future@0.16.0:0.18.2', type=('build', 'run'))

    depends_on('py-ipaddress@1.0.22:', type=('build', 'run'))

    depends_on('py-configparser@3.5.0:3.8.1', when='^python@:2', type=('build', 'run'))

    depends_on('py-tabulate@0.8.2:0.8.3', when='@:2.8', type=('build', 'run'))
    depends_on('py-tabulate@0.8.5', when='@2.9: ^python@3.0:3.4', type=('build', 'run'))
    depends_on('py-tabulate@0.8.2:0.8.7', when='@2.9: ^python@:2,3.5:', type=('build', 'run'))

    depends_on('py-pyyaml@5.2', when='@2.6:2.8 ^python@3.0:3.4', type=('build', 'run'))
    depends_on('py-pyyaml@5.3.1:', when='@2.9: ^python@:2,3.5:', type=('build', 'run'))

    depends_on('py-jinja2@2.10.1', when='@2.9: ^python@3.0:3.4', type=('build', 'run'))
    depends_on('py-jinja2@2.11.0:', when='@2.9: ^python@:2,3.5:', type=('build', 'run'))

    depends_on('py-boto3@1.16.14:', when='@2.10:', type=('build', 'run'))
    depends_on('py-boto3@1.14.3:', when='@2.8:2.9', type=('build', 'run'))
    depends_on('py-boto3@1.10.15:', when='@:2.7', type=('build', 'run'))

    depends_on('py-setuptools', when='@2.6:', type=('build', 'run'))

    depends_on('py-enum34@1.1.6:', when='@2.6: ^python@:3.3', type=('build', 'run'))
    depends_on('py-enum34@1.1.6:', when='@:2.5', type=('build', 'run'))

    depends_on('py-pyyaml@5.1.2', when='@2.6: ^python@:2,3.5:', type=('build', 'run'))
    depends_on('py-pyyaml@5.1.2:', when='@:2.5', type=('build', 'run'))

    # https://github.com/aws/aws-parallelcluster/pull/1633
    patch('enum34.patch', when='@:2.5.1')

    @run_after('install')
    @on_package_attributes(run_tests=True)
    def install_test(self):
        # Make sure executables work
        for exe in ['awsbhosts', 'awsbkill', 'awsbout', 'awsbqueues',
                    'awsbstat', 'awsbsub', 'pcluster']:
            exe = Executable(os.path.join(self.prefix.bin, exe))
            exe('--help')

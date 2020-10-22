# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack import *


class Njet(AutotoolsPackage):
    """NJet is a library for multi-parton one-loop matrix elements
       in massless QCD."""

    homepage = "https://bitbucket.org/njet/njet/wiki/Home"
    url      = "https://bitbucket.org/njet/njet/downloads/njet-2.1.1.tar.gz"

    version('2.1.1', sha256='3858ad37e84f3652711aa033819a6566352ecff04a1cb0189d6590af75b7bb56')

    depends_on('qd')

    def configure_args(self):
        args = ['--with-qd=' + self.spec['qd'].prefix,
                "FFLAGS=-ffixed-line-length-none -std=legacy"]
        return args

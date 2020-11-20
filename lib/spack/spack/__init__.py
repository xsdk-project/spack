# Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)


#: major, minor, patch version for Spack, in a tuple
spack_version_info = (0, 16, 0)

#: String containing Spack version joined with .'s
spack_version = '.'.join(str(v) for v in spack_version_info)

__all__ = ['spack_version_info', 'spack_version']

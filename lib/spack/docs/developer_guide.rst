.. Copyright 2013-2020 Lawrence Livermore National Security, LLC and other
   Spack Project Developers. See the top-level COPYRIGHT file for details.

   SPDX-License-Identifier: (Apache-2.0 OR MIT)

.. _developer_guide:

===============
Developer Guide
===============

This guide is intended for people who want to work on Spack itself.
If you just want to develop packages, see the :ref:`packaging-guide`.

It is assumed that you've read the :ref:`basic-usage` and
:ref:`packaging-guide` sections, and that you're familiar with the
concepts discussed there.  If you're not, we recommend reading those
first.

--------
Overview
--------

Spack is designed with three separate roles in mind:

#. **Users**, who need to install software *without* knowing all the
   details about how it is built.
#. **Packagers** who know how a particular software package is
   built and encode this information in package files.
#. **Developers** who work on Spack, add new features, and try to
   make the jobs of packagers and users easier.

Users could be end users installing software in their home directory,
or administrators installing software to a shared directory on a
shared machine.  Packagers could be administrators who want to
automate software builds, or application developers who want to make
their software more accessible to users.

As you might expect, there are many types of users with different
levels of sophistication, and Spack is designed to accommodate both
simple and complex use cases for packages.  A user who only knows that
he needs a certain package should be able to type something simple,
like ``spack install <package name>``, and get the package that he
wants.  If a user wants to ask for a specific version, use particular
compilers, or build several versions with different configurations,
then that should be possible with a minimal amount of additional
specification.

This gets us to the two key concepts in Spack's software design:

#. **Specs**: expressions for describing builds of software, and
#. **Packages**: Python modules that build software according to a
   spec.

A package is a template for building particular software, and a spec
as a descriptor for one or more instances of that template.  Users
express the configuration they want using a spec, and a package turns
the spec into a complete build.

The obvious difficulty with this design is that users under-specify
what they want.  To build a software package, the package object needs
a *complete* specification.  In Spack, if a spec describes only one
instance of a package, then we say it is **concrete**.  If a spec
could describes many instances, (i.e. it is under-specified in one way
or another), then we say it is **abstract**.

Spack's job is to take an *abstract* spec from the user, find a
*concrete* spec that satisfies the constraints, and hand the task of
building the software off to the package object.  The rest of this
document describes all the pieces that come together to make that
happen.

-------------------
Directory Structure
-------------------

So that you can familiarize yourself with the project, we'll start
with a high level view of Spack's directory structure:

.. code-block:: none

   spack/                  <- installation root
      bin/
         spack             <- main spack executable

      etc/
         spack/            <- Spack config files.
                              Can be overridden by files in ~/.spack.

      var/
         spack/            <- build & stage directories
             repos/            <- contains package repositories
                builtin/       <- pkg repository that comes with Spack
                   repo.yaml   <- descriptor for the builtin repository
                   packages/   <- directories under here contain packages
             cache/        <- saves resources downloaded during installs

      opt/
         spack/            <- packages are installed here

      lib/
         spack/
            docs/          <- source for this documentation
            env/           <- compiler wrappers for build environment

            external/      <- external libs included in Spack distro
            llnl/          <- some general-use libraries

            spack/         <- spack module; contains Python code
               cmd/        <- each file in here is a spack subcommand
               compilers/  <- compiler description files
               test/       <- unit test modules
               util/       <- common code

Spack is designed so that it could live within a `standard UNIX
directory hierarchy <http://linux.die.net/man/7/hier>`_, so ``lib``,
``var``, and ``opt`` all contain a ``spack`` subdirectory in case
Spack is installed alongside other software.  Most of the interesting
parts of Spack live in ``lib/spack``.

Spack has *one* directory layout and there is no install process.
Most Python programs don't look like this (they use distutils, ``setup.py``,
etc.) but we wanted to make Spack *very* easy to use.  The simple layout
spares users from the need to install Spack into a Python environment.
Many users don't have write access to a Python installation, and installing
an entire new instance of Python to bootstrap Spack would be very complicated.
Users should not have to install a big, complicated package to
use the thing that's supposed to spare them from the details of big,
complicated packages.  The end result is that Spack works out of the
box: clone it and add ``bin`` to your PATH and you're ready to go.

--------------
Code Structure
--------------

This section gives an overview of the various Python modules in Spack,
grouped by functionality.

^^^^^^^^^^^^^^^^^^^^^^^
Package-related modules
^^^^^^^^^^^^^^^^^^^^^^^

:mod:`spack.package`
  Contains the :class:`Package <spack.package.Package>` class, which
  is the superclass for all packages in Spack.  Methods on ``Package``
  implement all phases of the :ref:`package lifecycle
  <package-lifecycle>` and manage the build process.

:mod:`spack.packages`
  Contains all of the packages in Spack and methods for managing them.
  Functions like :func:`packages.get <spack.packages.get>` and
  :func:`class_name_for_package_name
  <packages.class_name_for_package_name>` handle mapping package module
  names to class names and dynamically instantiating packages by name
  from module files.

:mod:`spack.relations`
  *Relations* are relationships between packages, like
  :func:`depends_on <spack.relations.depends_on>` and :func:`provides
  <spack.relations.provides>`.  See :ref:`dependencies` and
  :ref:`virtual-dependencies`.

:mod:`spack.multimethod`
  Implementation of the :func:`@when <spack.multimethod.when>`
  decorator, which allows :ref:`multimethods <multimethods>` in
  packages.

^^^^^^^^^^^^^^^^^^^^
Spec-related modules
^^^^^^^^^^^^^^^^^^^^

:mod:`spack.spec`
  Contains :class:`Spec <spack.spec.Spec>` and :class:`SpecParser
  <spack.spec.SpecParser>`. Also implements most of the logic for
  normalization and concretization of specs.

:mod:`spack.parse`
  Contains some base classes for implementing simple recursive descent
  parsers: :class:`Parser <spack.parse.Parser>` and :class:`Lexer
  <spack.parse.Lexer>`.  Used by :class:`SpecParser
  <spack.spec.SpecParser>`.

:mod:`spack.concretize`
  Contains :class:`DefaultConcretizer
  <spack.concretize.DefaultConcretizer>` implementation, which allows
  site administrators to change Spack's :ref:`concretization-policies`.

:mod:`spack.version`
  Implements a simple :class:`Version <spack.version.Version>` class
  with simple comparison semantics.  Also implements
  :class:`VersionRange <spack.version.VersionRange>` and
  :class:`VersionList <spack.version.VersionList>`.  All three are
  comparable with each other and offer union and intersection
  operations.  Spack uses these classes to compare versions and to
  manage version constraints on specs.  Comparison semantics are
  similar to the ``LooseVersion`` class in ``distutils`` and to the
  way RPM compares version strings.

:mod:`spack.compilers`
  Submodules contains descriptors for all valid compilers in Spack.
  This is used by the build system to set up the build environment.

  .. warning::

     Not yet implemented.  Currently has two compiler descriptions,
     but compilers aren't fully integrated with the build process
     yet.

:mod:`spack.architecture`
  :func:`architecture.sys_type <spack.architecture.sys_type>` is used
  to determine the host architecture while building.

  .. warning::

     Not yet implemented.  Should eventually have architecture
     descriptions for cross-compiling.

^^^^^^^^^^^^^^^^^
Build environment
^^^^^^^^^^^^^^^^^

:mod:`spack.stage`
  Handles creating temporary directories for builds.

:mod:`spack.compilation`
  This contains utility functions used by the compiler wrapper script,
  ``cc``.

:mod:`spack.directory_layout`
  Classes that control the way an installation directory is laid out.
  Create more implementations of this to change the hierarchy and
  naming scheme in ``$spack_prefix/opt``

^^^^^^^^^^^^^^^^^
Spack Subcommands
^^^^^^^^^^^^^^^^^

:mod:`spack.cmd`
  Each module in this package implements a Spack subcommand.  See
  :ref:`writing commands <writing-commands>` for details.

^^^^^^^^^^
Unit tests
^^^^^^^^^^

:mod:`spack.test`
  Implements Spack's test suite.  Add a module and put its name in
  the test suite in ``__init__.py`` to add more unit tests.

:mod:`spack.test.mock_packages`
  This is a fake package hierarchy used to mock up packages for
  Spack's test suite.

^^^^^^^^^^^^^
Other Modules
^^^^^^^^^^^^^

:mod:`spack.url`
  URL parsing, for deducing names and versions of packages from
  tarball URLs.

:mod:`spack.error`
  :class:`SpackError <spack.error.SpackError>`, the base class for
  Spack's exception hierarchy.

:mod:`llnl.util.tty`
  Basic output functions for all of the messages Spack writes to the
  terminal.

:mod:`llnl.util.tty.color`
  Implements a color formatting syntax used by ``spack.tty``.

:mod:`llnl.util`
  In this package are a number of utility modules for the rest of
  Spack.

------------
Spec objects
------------

---------------
Package objects
---------------

Most spack commands look something like this:

#. Parse an abstract spec (or specs) from the command line,
#. *Normalize* the spec based on information in package files,
#. *Concretize* the spec according to some customizable policies,
#. Instantiate a package based on the spec, and
#. Call methods (e.g., ``install()``) on the package object.

The information in Package files is used at all stages in this
process.

Conceptually, packages are overloaded.  They contain:

-------------
Stage objects
-------------

.. _writing-commands:

----------------
Writing commands
----------------

Adding a new command to Spack is easy. Simply add a ``<name>.py`` file to
``lib/spack/spack/cmd/``, where ``<name>`` is the name of the subcommand.
At the bare minimum, two functions are required in this file:

^^^^^^^^^^^^^^^^^^
``setup_parser()``
^^^^^^^^^^^^^^^^^^

Unless your command doesn't accept any arguments, a ``setup_parser()``
function is required to define what arguments and flags your command takes.
See the `Argparse documentation <https://docs.python.org/2.7/library/argparse.html>`_
for more details on how to add arguments.

Some commands have a set of subcommands, like ``spack compiler find`` or
``spack module lmod refresh``. You can add subparsers to your parser to handle
this. Check out ``spack edit --command compiler`` for an example of this.

A lot of commands take the same arguments and flags. These arguments should
be defined in ``lib/spack/spack/cmd/common/arguments.py`` so that they don't
need to be redefined in multiple commands.

^^^^^^^^^^^^
``<name>()``
^^^^^^^^^^^^

In order to run your command, Spack searches for a function with the same
name as your command in ``<name>.py``. This is the main method for your
command, and can call other helper methods to handle common tasks.

Remember, before adding a new command, think to yourself whether or not this
new command is actually necessary. Sometimes, the functionality you desire
can be added to an existing command. Also remember to add unit tests for
your command. If it isn't used very frequently, changes to the rest of
Spack can cause your command to break without sufficient unit tests to
prevent this from happening.

Whenever you add/remove/rename a command or flags for an existing command,
make sure to update Spack's `Bash tab completion script
<https://github.com/adamjstewart/spack/blob/develop/share/spack/spack-completion.bash>`_.

----------
Unit tests
----------

------------
Unit testing
------------

------------------
Developer commands
------------------

.. _cmd-spack-doc:

^^^^^^^^^^^^^
``spack doc``
^^^^^^^^^^^^^

^^^^^^^^^^^^^^
``spack test``
^^^^^^^^^^^^^^

See the :ref:`contributor guide section <cmd-spack-test>` on ``spack test``.

.. _cmd-spack-python:

^^^^^^^^^^^^^^^^
``spack python``
^^^^^^^^^^^^^^^^

``spack python`` is a command that lets you import and debug things as if
you were in a Spack interactive shell. Without any arguments, it is similar
to a normal interactive Python shell, except you can import spack and any
other Spack modules:

.. code-block:: console

   $ spack python
   Spack version 0.10.0
   Python 2.7.13, Linux x86_64
   >>> from spack.version import Version
   >>> a = Version('1.2.3')
   >>> b = Version('1_2_3')
   >>> a == b
   True
   >>> c = Version('1.2.3b')
   >>> c > a
   True
   >>>

You can also run a single command:

.. code-block:: console

   $ spack python -c 'import distro; distro.linux_distribution()'
   ('Fedora', '25', 'Workstation Edition')

or a file:

.. code-block:: console

   $ spack python ~/test_fetching.py

just like you would with the normal ``python`` command.

.. _cmd-spack-url:

^^^^^^^^^^^^^
``spack url``
^^^^^^^^^^^^^

A package containing a single URL can be used to download several different
versions of the package. If you've ever wondered how this works, all of the
magic is in :mod:`spack.url`. This module contains methods for extracting
the name and version of a package from its URL. The name is used by
``spack create`` to guess the name of the package. By determining the version
from the URL, Spack can replace it with other versions to determine where to
download them from.

The regular expressions in ``parse_name_offset`` and ``parse_version_offset``
are used to extract the name and version, but they aren't perfect. In order
to debug Spack's URL parsing support, the ``spack url`` command can be used.

"""""""""""""""""""
``spack url parse``
"""""""""""""""""""

If you need to debug a single URL, you can use the following command:

.. command-output:: spack url parse http://cache.ruby-lang.org/pub/ruby/2.2/ruby-2.2.0.tar.gz

You'll notice that the name and version of this URL are correctly detected,
and you can even see which regular expressions it was matched to. However,
you'll notice that when it substitutes the version number in, it doesn't
replace the ``2.2`` with ``9.9`` where we would expect ``9.9.9b`` to live.
This particular package may require a ``list_url`` or ``url_for_version``
function.

This command also accepts a ``--spider`` flag. If provided, Spack searches
for other versions of the package and prints the matching URLs.

""""""""""""""""""
``spack url list``
""""""""""""""""""

This command lists every URL in every package in Spack. If given the
``--color`` and ``--extrapolation`` flags, it also colors the part of
the string that it detected to be the name and version. The
``--incorrect-name`` and ``--incorrect-version`` flags can be used to
print URLs that were not being parsed correctly.

"""""""""""""""""""""
``spack url summary``
"""""""""""""""""""""

This command attempts to parse every URL for every package in Spack
and prints a summary of how many of them are being correctly parsed.
It also prints a histogram showing which regular expressions are being
matched and how frequently:

.. command-output:: spack url summary

This command is essential for anyone adding or changing the regular
expressions that parse names and versions. By running this command
before and after the change, you can make sure that your regular
expression fixes more packages than it breaks.

---------
Profiling
---------

Spack has some limited built-in support for profiling, and can report
statistics using standard Python timing tools.  To use this feature,
supply ``--profile`` to Spack on the command line, before any subcommands.

.. _spack-p:

^^^^^^^^^^^^^^^^^^^
``spack --profile``
^^^^^^^^^^^^^^^^^^^

``spack --profile`` output looks like this:

.. command-output:: spack --profile graph hdf5
   :ellipsis: 25

The bottom of the output shows the top most time consuming functions,
slowest on top.  The profiling support is from Python's built-in tool,
`cProfile
<https://docs.python.org/2/library/profile.html#module-cProfile>`_.

.. _releases:

--------
Releases
--------

This section documents Spack's release process. It is intended for
project maintainers, as the tasks described here require maintainer
privileges on the Spack repository. For others, we hope this section at
least provides some insight into how the Spack project works.

.. _release-branches:

^^^^^^^^^^^^^^^^
Release branches
^^^^^^^^^^^^^^^^

There are currently two types of Spack releases: :ref:`major releases
<major-releases>` (``0.13.0``, ``0.14.0``, etc.) and :ref:`point releases
<point-releases>` (``0.13.1``, ``0.13.2``, ``0.13.3``, etc.). Here is a
diagram of how Spack release branches work::

    o    branch: develop  (latest version)
    |
    o    merge v0.14.1 into develop
    |\
    | o  branch: releases/v0.14, tag: v0.14.1
    o |  merge v0.14.0 into develop
    |\|
    | o  tag: v0.14.0
    |/
    o    merge v0.13.2 into develop
    |\
    | o  branch: releases/v0.13, tag: v0.13.2
    o |  merge v0.13.1 into develop
    |\|
    | o  tag: v0.13.1
    o |  merge v0.13.0 into develop
    |\|
    | o  tag: v0.13.0
    o |
    | o
    |/
    o

The ``develop`` branch has the latest contributions, and nearly all pull
requests target ``develop``.

Each Spack release series also has a corresponding branch, e.g.
``releases/v0.14`` has ``0.14.x`` versions of Spack, and
``releases/v0.13`` has ``0.13.x`` versions. A major release is the first
tagged version on a release branch. Minor releases are back-ported from
develop onto release branches. This is typically done by cherry-picking
bugfix commits off of ``develop``.

To avoid version churn for users of a release series, minor releases
should **not** make changes that would change the concretization of
packages. They should generally only contain fixes to the Spack core.

Both major and minor releases are tagged. After each release, we merge
the release branch back into ``develop`` so that the version bump and any
other release-specific changes are visible in the mainline. As a
convenience, we also tag the latest release as ``releases/latest``,
so that users can easily check it out to get the latest
stable version. See :ref:`merging-releases` for more details.


^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Scheduling work for releases
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We schedule work for releases by creating `GitHub projects
<https://github.com/spack/spack/projects>`_. At any time, there may be
several open release projects. For example, here are two releases (from
some past version of the page linked above):

.. image:: images/projects.png

Here, there's one release in progress for ``0.15.1`` and another for
``0.16.0``. Each of these releases has a project board containing issues
and pull requests. GitHub shows a status bar with completed work in
green, work in progress in purple, and work not started yet in gray, so
it's fairly easy to see progress.

Spack's project boards are not firm commitments, and we move work between
releases frequently. If we need to make a release and some tasks are not
yet done, we will simply move them to next minor or major release, rather
than delaying the release to complete them.

For more on using GitHub project boards, see `GitHub's documentation
<https://docs.github.com/en/github/managing-your-work-on-github/about-project-boards>`_.

.. _major-releases:

^^^^^^^^^^^^^^^^^^^^^
Making Major Releases
^^^^^^^^^^^^^^^^^^^^^

Assuming you've already created a project board and completed the work
for a major release, the steps to make the release are as follows:

#. Create two new project boards:

   * One for the next major release
   * One for the next point release

#. Move any tasks that aren't done yet to one of the new project boards.
   Small bugfixes should go to the next point release. Major features,
   refactors, and changes that could affect concretization should go in
   the next major release.

#. Create a branch for the release, based on ``develop``:

   .. code-block:: console

      $ git checkout -b releases/v0.15 develop

   For a version ``vX.Y.Z``, the branch's name should be
   ``releases/vX.Y``. That is, you should create a ``releases/vX.Y``
   branch if you are preparing the ``X.Y.0`` release.

#. Bump the version in ``lib/spack/spack/__init__.py``. See `this example from 0.13.0
   <https://github.com/spack/spack/commit/8eeb64096c98b8a43d1c587f13ece743c864fba9>`_

#. Update ``CHANGELOG.md`` with major highlights in bullet form. Use
   proper markdown formatting, like `this example from 0.15.0
   <https://github.com/spack/spack/commit/d4bf70d9882fcfe88507e9cb444331d7dd7ba71c>`_.

#. Push the release branch to GitHub.

#. Make sure CI passes on the release branch, including:

   * Regular unit tests
   * Build tests
   * The E4S pipeline at `gitlab.spack.io <https://gitlab.spack.io>`_

   If CI is not passing, submit pull requests to ``develop`` as normal
   and keep rebasing the release branch on ``develop`` until CI passes.

#. Follow the steps in :ref:`publishing-releases`.

#. Follow the steps in :ref:`merging-releases`.

#. Follow the steps in :ref:`announcing-releases`.


.. _point-releases:

^^^^^^^^^^^^^^^^^^^^^
Making Point Releases
^^^^^^^^^^^^^^^^^^^^^

This assumes you've already created a project board for a point release
and completed the work to be done for the release. To make a point
release:

#. Create one new project board for the next point release.

#. Move any cards that aren't done yet to the next project board.

#. Check out the release branch (it should already exist). For the
   ``X.Y.Z`` release, the release branch is called ``releases/vX.Y``. For
   ``v0.15.1``, you would check out ``releases/v0.15``:

   .. code-block:: console

      $ git checkout releases/v0.15

#. Cherry-pick each pull request in the ``Done`` column of the release
   project onto the release branch.

   This is **usually** fairly simple since we squash the commits from the
   vast majority of pull requests, which means there is only one commit
   per pull request to cherry-pick. For example, `this pull request
   <https://github.com/spack/spack/pull/15777>`_ has three commits, but
   the were squashed into a single commit on merge. You can see the
   commit that was created here:

   .. image:: images/pr-commit.png

   You can easily cherry pick it like this (assuming you already have the
   release branch checked out):

   .. code-block:: console

      $ git cherry-pick 7e46da7

   For pull requests that were rebased, you'll need to cherry-pick each
   rebased commit individually. There have not been any rebased PRs like
   this in recent point releases.

   .. warning::

      It is important to cherry-pick commits in the order they happened,
      otherwise you can get conflicts while cherry-picking. When
      cherry-picking onto a point release, look at the merge date,
      **not** the number of the pull request or the date it was opened.

      Sometimes you may **still** get merge conflicts even if you have
      cherry-picked all the commits in order. This generally means there
      is some other intervening pull request that the one you're trying
      to pick depends on. In these cases, you'll need to make a judgment
      call:

      1. If the dependency is small, you might just cherry-pick it, too.
         If you do this, add it to the release board.

      2. If it is large, then you may decide that this fix is not worth
         including in a point release, in which case you should remove it
         from the release project.

      3. You can always decide to manually back-port the fix to the release
         branch if neither of the above options makes sense, but this can
         require a lot of work. It's seldom the right choice.

#. Bump the version in ``lib/spack/spack/__init__.py``. See `this example from 0.14.1
   <https://github.com/spack/spack/commit/ff0abb9838121522321df2a054d18e54b566b44a>`_.

#. Update ``CHANGELOG.md`` with a list of bugfixes. This is typically just a
   summary of the commits you cherry-picked onto the release branch. See
   `the changelog from 0.14.1
   <https://github.com/spack/spack/commit/ff0abb9838121522321df2a054d18e54b566b44a>`_.

#. Push the release branch to GitHub.

#. Make sure CI passes on the release branch, including:
   * Regular unit tests
   * Build tests
   * The E4S pipeline at `gitlab.spack.io <https://gitlab.spack.io>`_

   If CI does not pass, you'll need to figure out why, and make changes
   to the release branch until it does. You can make more commits, modify
   or remove cherry-picked commits, or cherry-pick **more** from
   ``develop`` to make this happen.

#. Follow the steps in :ref:`publishing-releases`.

#. Follow the steps in :ref:`merging-releases`.

#. Follow the steps in :ref:`announcing-releases`.


.. _publishing-releases:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Publishing a release on GitHub
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

#. Go to `github.com/spack/spack/releases
   <https://github.com/spack/spack/releases>`_ and click ``Draft a new
   release``.  Set the following:

   * ``Tag version`` should start with ``v`` and contain *all three*
     parts of the version, .g. ``v0.15.1``. This is the name of the tag
     that will be created.

   * ``Target`` should be the ``releases/vX.Y`` branch (e.g., ``releases/v0.15``).

   * ``Release title`` should be ``vX.Y.Z`` (To match the tag, e.g., ``v0.15.1``).

   * For the text, paste the latest release markdown from your ``CHANGELOG.md``.

   You can save the draft and keep coming back to this as you prepare the release.

#. When you are done, click ``Publish release``.

#. Immediately after publishing, go back to
   `github.com/spack/spack/releases
   <https://github.com/spack/spack/releases>`_ and download the
   auto-generated ``.tar.gz`` file for the release. It's the ``Source
   code (tar.gz)`` link.

#. Click ``Edit`` on the release you just did and attach the downloaded
   release tarball as a binary. This does two things:

   #. Makes sure that the hash of our releases doesn't change over time.
      GitHub sometimes annoyingly changes they way they generate
      tarballs, and then hashes can change if you rely on the
      auto-generated tarball links.

   #. Gets us download counts on releases visible through the GitHub
      API. GitHub tracks downloads of artifacts, but *not* the source
      links. See the `releases
      page <https://api.github.com/repos/spack/spack/releases>`_ and search
      for ``download_count`` to see this.

#. Go to `readthedocs.org <https://readthedocs.org/projects/spack>`_ and activate
   the release tag. This builds the documentation and makes the released version
   selectable in the versions menu.


.. _merging-releases:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Updating `releases/latest` and `develop`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the new release is the **highest** Spack release yet, you should
also tag it as ``releases/latest``. For example, suppose the highest
release is currently ``0.15.3``:

     * If you are releasing ``0.15.4`` or ``0.16.0``, then you should tag
       it with ``releases/latest``, as these are higher than ``0.15.3``.

     * If you are making a new release of an **older** major version of
       Spack, e.g. ``0.14.4``, then you should not tag it as
       ``releases/latest`` (as there are newer major versions).

   To tag ``releases/latest``, do this:

   .. code-block:: console

      $ git checkout releases/vX.Y     # vX.Y is the new release's branch
      $ git tag --force releases/latest
      $ git push --tags

   The ``--force`` argument makes ``git`` overwrite the existing
   ``releases/latest`` tag with the new one.

We also merge each release that we tag as ``releases/latest`` into ``develop``.
Make sure to do this with a merge commit:

.. code-block:: console

   $ git checkout develop
   $ git merge --no-ff vX.Y.Z  # vX.Y.Z is the new release's tag
   $ git push

We merge back to ``develop`` because it:

  * updates the version and ``CHANGELOG.md`` on ``develop``.
  * ensures that your release tag is reachable from the head of
    ``develop``

We *must* use a real merge commit (via the ``--no-ff`` option) because it
ensures that the release tag is reachable from the tip of ``develop``.
This is necessary for ``spack -V`` to work properly -- it uses ``git
describe --tags`` to find the last reachable tag in the repository and
reports how far we are from it. For example:

.. code-block:: console

   $ spack -V
   0.14.2-1486-b80d5e74e5

This says that we are at commit ``b80d5e74e5``, which is 1,486 commits
ahead of the ``0.14.2`` release.

We put this step last in the process because it's best to do it only once
the release is complete and tagged. If you do it before you've tagged the
release and later decide you want to tag some later commit, you'll need
to merge again.

.. _announcing-releases:

^^^^^^^^^^^^^^^^^^^^
Announcing a release
^^^^^^^^^^^^^^^^^^^^

We announce releases in all of the major Spack communication channels.
Publishing the release takes care of GitHub. The remaining channels are
Twitter, Slack, and the mailing list. Here are the steps:

#. Make a tweet to announce the release. It should link to the release's
   page on GitHub. You can base it on `this example tweet
   <https://twitter.com/spackpm/status/1231761858182307840>`_.

#. Ping ``@channel`` in ``#general`` on Slack (`spackpm.slack.com
   <https://spackpm.slack.com>`_) with a link to the tweet. The tweet
   will be shown inline so that you do not have to retype your release
   announcement.

#. Email the Spack mailing list to let them know about the release. As
   with the tweet, you likely want to link to the release's page on
   GitHub. It's also helpful to include some information directly in the
   email. You can base yours on this `example email
   <https://groups.google.com/forum/#!topic/spack/WT4CT9i_X4s>`_.

Once you've announced the release, congratulations, you're done! You've
finished making the release!

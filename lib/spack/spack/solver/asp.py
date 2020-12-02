# Copyright 2013-2019 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
from __future__ import print_function

import collections
import copy
import itertools
import os
import pkgutil
import pprint
import re
import sys
import tempfile
import time
import types
from six import string_types

import archspec.cpu

try:
    import clingo
except ImportError:
    clingo = None

import llnl.util.lang
import llnl.util.tty as tty
import llnl.util.tty.color as color

import spack
import spack.architecture
import spack.cmd
import spack.config
import spack.dependency
import spack.error
import spack.spec
import spack.package
import spack.package_prefs
import spack.repo
import spack.variant
from spack.util.executable import which
from spack.version import ver


#: max line length for ASP programs in characters
_max_line = 80


class Timer(object):
    """Simple timer for timing phases of a solve"""
    def __init__(self):
        self.start = time.time()
        self.last = self.start
        self.phases = {}

    def phase(self, name):
        last = self.last
        now = time.time()
        self.phases[name] = now - last
        self.last = now

    def write(self, out=sys.stdout):
        now = time.time()
        out.write("Time:\n")
        for phase, t in self.phases.items():
            out.write("    %-15s%.4f\n" % (phase + ":", t))
        out.write("Total: %.4f\n" % (now - self.start))


def issequence(obj):
    if isinstance(obj, string_types):
        return False
    return isinstance(obj, (collections.Sequence, types.GeneratorType))


def listify(args):
    if len(args) == 1 and issequence(args[0]):
        return list(args[0])
    return list(args)


def packagize(pkg):
    if isinstance(pkg, string_types):
        return spack.repo.path.get_pkg_class(pkg)
    else:
        return pkg


def specify(spec):
    if isinstance(spec, spack.spec.Spec):
        return spec
    return spack.spec.Spec(spec)


class AspObject(object):
    """Object representing a piece of ASP code."""


def _id(thing):
    """Quote string if needed for it to be a valid identifier."""
    if isinstance(thing, AspObject):
        return thing
    elif isinstance(thing, bool):
        return '"%s"' % str(thing)
    elif isinstance(thing, int):
        return str(thing)
    else:
        return '"%s"' % str(thing)


class AspFunction(AspObject):
    def __init__(self, name, args=None):
        self.name = name
        self.args = [] if args is None else args

    def __call__(self, *args):
        return AspFunction(self.name, args)

    def symbol(self, positive=True):
        def argify(arg):
            if isinstance(arg, bool):
                return str(arg)
            elif isinstance(arg, int):
                return arg
            else:
                return str(arg)
        return clingo.Function(
            self.name, [argify(arg) for arg in self.args], positive=positive)

    def __getitem___(self, *args):
        self.args[:] = args
        return self

    def __str__(self):
        return "%s(%s)" % (
            self.name, ', '.join(str(_id(arg)) for arg in self.args))

    def __repr__(self):
        return str(self)


class AspAnd(AspObject):
    def __init__(self, *args):
        args = listify(args)
        self.args = args

    def __str__(self):
        s = ", ".join(str(arg) for arg in self.args)
        return s


class AspOneOf(AspObject):
    def __init__(self, *args):
        args = listify(args)
        self.args = args

    def __str__(self):
        body = "; ".join(str(arg) for arg in self.args)
        return "1 { %s } 1" % body


class AspFunctionBuilder(object):
    def __getattr__(self, name):
        return AspFunction(name)


fn = AspFunctionBuilder()


def all_compilers_in_config():
    return spack.compilers.all_compilers()


def extend_flag_list(flag_list, new_flags):
    """Extend a list of flags, preserving order and precedence.

    Add new_flags at the end of flag_list.  If any flags in new_flags are
    already in flag_list, they are moved to the end so that they take
    higher precedence on the compile line.

    """
    for flag in new_flags:
        if flag in flag_list:
            flag_list.remove(flag)
        flag_list.append(flag)


def check_same_flags(flag_dict_1, flag_dict_2):
    """Return True if flag dicts contain the same flags regardless of order."""
    types = set(flag_dict_1.keys()).union(set(flag_dict_2.keys()))
    for t in types:
        values1 = set(flag_dict_1.get(t, []))
        values2 = set(flag_dict_2.get(t, []))
        assert values1 == values2


def check_packages_exist(specs):
    """Ensure all packages mentioned in specs exist."""
    repo = spack.repo.path
    for spec in specs:
        for s in spec.traverse():
            try:
                check_passed = repo.exists(s.name) or repo.is_virtual(s.name)
            except Exception as e:
                msg = 'Cannot find package: {0}'.format(str(e))
                check_passed = False
                tty.debug(msg)

            if not check_passed:
                raise spack.repo.UnknownPackageError(str(s.fullname))


class Result(object):
    """Result of an ASP solve."""
    def __init__(self, asp=None):
        self.asp = asp
        self.satisfiable = None
        self.optimal = None
        self.warnings = None
        self.nmodels = 0

        # specs ordered by optimization level
        self.answers = []
        self.cores = []

    def print_cores(self):
        for core in self.cores:
            tty.msg(
                "The following constraints are unsatisfiable:",
                *sorted(str(symbol) for symbol in core))


class ClingoDriver(object):
    def __init__(self):
        self.clingo = which("clingo", required=True)
        self.out = None

    def title(self, name, char):
        self.out.write('\n')
        self.out.write("%" + (char * 76))
        self.out.write('\n')
        self.out.write("%% %s\n" % name)
        self.out.write("%" + (char * 76))
        self.out.write('\n')

    def h1(self, name):
        self.title(name, "=")

    def h2(self, name):
        self.title(name, "-")

    def newline(self):
        self.out.write('\n')

    def one_of(self, *args):
        return AspOneOf(*args)

    def _and(self, *args):
        return AspAnd(*args)

    def fact(self, head):
        """ASP fact (a rule without a body)."""
        self.out.write("%s.\n" % head)

    def rule(self, head, body):
        """ASP rule (an implication)."""
        rule_line = "%s :- %s.\n" % (head, body)
        if len(rule_line) > _max_line:
            rule_line = re.sub(r' \| ', "\n| ", rule_line)
        self.out.write(rule_line)

    def before_setup(self):
        """Must be called before program is generated."""
        # read the main ASP program from concrtize.lp

    def after_setup(self):
        """Must be called after program is generated."""

    def parse_model_functions(self, function_strings):
        function_re = re.compile(r'(\w+)\(([^)]*)\)')

        # parse functions out of ASP output
        functions = []
        for string in function_strings:
            m = function_re.match(string)
            name, arg_string = m.groups()
            args = re.split(r'\s*,\s*', arg_string)
            args = [s.strip('"') if s.startswith('"') else int(s)
                    for s in args]
            functions.append((name, args))
        return functions

    def parse_competition_format(self, output, builder, result):
        """Parse Clingo's competition output format, which gives one answer."""
        best_model_number = 0
        for line in output:
            match = re.match(r"% Answer: (\d+)", line)
            if match:
                best_model_number = int(match.group(1))

            if re.match("INCONSISTENT", line):
                result.satisfiable = False
                return

            if re.match("ANSWER", line):
                result.satisfiable = True

                answer = next(output)
                functions = [
                    f.rstrip(".") for f in re.split(r"\s+", answer.strip())
                ]
                function_tuples = self.parse_model_functions(functions)
                specs = builder.build_specs(function_tuples)

                costs = re.split(r"\s+", next(output).strip())
                opt = [int(x) for x in costs[1:]]

                result.answers.append((opt, best_model_number, specs))

    def solve(self, solver_setup, specs, dump=None, models=0,
              timers=False, stats=False):
        def colorize(string):
            color.cprint(highlight(color.cescape(string)))

        timer = Timer()
        with tempfile.TemporaryFile("w+") as program:
            self.out = program

            concretize_lp = pkgutil.get_data('spack.solver', 'concretize.lp')
            program.write(concretize_lp.decode("utf-8"))

            solver_setup.setup(self, specs)

            program.write('\n')
            display_lp = pkgutil.get_data('spack.solver', 'display.lp')
            program.write(display_lp.decode("utf-8"))

            timer.phase("generate")

            result = Result(program.read())
            program.seek(0)

            if dump and 'asp' in dump:
                if sys.stdout.isatty():
                    tty.msg('ASP program:')

                if dump == ['asp']:
                    print(result.asp)
                    return
                else:
                    colorize(result.asp)
                timer.phase("dump")

            with tempfile.TemporaryFile("w+") as output:
                with tempfile.TemporaryFile() as warnings:
                    self.clingo(
                        '--models=%d' % models,
                        # 1 is "competition" format with just optimal answer
                        # 2 is JSON format with all explored answers
                        '--outf=1',
                        # Use a highest priority criteria-first optimization
                        # strategy, which means we'll explore recent
                        # versions, preferred packages first.  This works
                        # well because Spack solutions are pretty easy to
                        # find -- there are just a lot of them.  Without
                        # this, it can take a VERY long time to find good
                        # solutions, and a lot of models are explored.
                        '--opt-strategy=bb,hier',
                        input=program,
                        output=output,
                        error=warnings,
                        fail_on_error=False)
                    timer.phase("solve")

                    warnings.seek(0)
                    result.warnings = warnings.read().decode("utf-8")

                    # dump any warnings generated by the solver
                    if result.warnings:
                        if sys.stdout.isatty():
                            tty.msg('Clingo gave the following warnings:')
                        colorize(result.warnings)

                    output.seek(0)
                    result.output = output.read()
                    timer.phase("read")

                    # dump the raw output of the solver
                    if dump and 'output' in dump:
                        if sys.stdout.isatty():
                            tty.msg('Clingo output:')
                        print(result.output)

                        if 'solutions' not in dump:
                            return

                    output.seek(0)
                    builder = SpecBuilder(specs)
                    self.parse_competition_format(output, builder, result)
                    timer.phase("parse")

            if timers:
                timer.write()
                print()

        return result


def _normalize(body):
    """Accept an AspAnd object or a single Symbol and return a list of
    symbols.
    """
    if isinstance(body, AspAnd):
        args = [getattr(f, 'symbol', lambda: f)() for f in body.args]
    elif isinstance(body, clingo.Symbol):
        args = [body]
    elif hasattr(body, 'symbol'):
        args = [body.symbol()]
    else:
        raise TypeError("Invalid typee: ", type(body))
    return args


def _normalize_packages_yaml(packages_yaml):
    normalized_yaml = copy.copy(packages_yaml)
    for pkg_name in packages_yaml:
        is_virtual = spack.repo.path.is_virtual(pkg_name)
        if pkg_name == 'all' or not is_virtual:
            continue

        # Remove the virtual entry from the normalized configuration
        data = normalized_yaml.pop(pkg_name)
        is_buildable = data.get('buildable', True)
        if not is_buildable:
            for provider in spack.repo.path.providers_for(pkg_name):
                entry = normalized_yaml.setdefault(provider.name, {})
                entry['buildable'] = False

        externals = data.get('externals', [])
        keyfn = lambda x: spack.spec.Spec(x['spec']).name
        for provider, specs in itertools.groupby(externals, key=keyfn):
            entry = normalized_yaml.setdefault(provider, {})
            entry.setdefault('externals', []).extend(specs)

    return normalized_yaml


class PyclingoDriver(object):
    def __init__(self, cores=True, asp=None):
        """Driver for the Python clingo interface.

        Arguments:
            cores (bool): whether to generate unsatisfiable cores for better
                error reporting.
            asp (file-like): optional stream to write a text-based ASP program
                for debugging or verification.
        """
        assert clingo, "PyclingoDriver requires clingo with Python support"
        self.out = asp or llnl.util.lang.Devnull()
        self.cores = cores

    def title(self, name, char):
        self.out.write('\n')
        self.out.write("%" + (char * 76))
        self.out.write('\n')
        self.out.write("%% %s\n" % name)
        self.out.write("%" + (char * 76))
        self.out.write('\n')

    def h1(self, name):
        self.title(name, "=")

    def h2(self, name):
        self.title(name, "-")

    def newline(self):
        self.out.write('\n')

    def one_of(self, *args):
        return AspOneOf(*args)

    def _and(self, *args):
        return AspAnd(*args)

    def _register_rule_for_cores(self, rule_str):
        # rule atoms need to be choices before we can assume them
        if self.cores:
            rule_sym = clingo.Function("rule", [rule_str])
            rule_atom = self.backend.add_atom(rule_sym)
            self.backend.add_rule([rule_atom], [], choice=True)
            self.assumptions.append(rule_atom)
            rule_atoms = [rule_atom]
        else:
            rule_atoms = []
        return rule_atoms

    def fact(self, head):
        """ASP fact (a rule without a body)."""
        symbols = _normalize(head)
        self.out.write("%s.\n" % ','.join(str(a) for a in symbols))

        atoms = {}
        for s in symbols:
            atoms[s] = self.backend.add_atom(s)

        self.backend.add_rule(
            [atoms[s] for s in symbols], [], choice=self.cores
        )
        if self.cores:
            for s in symbols:
                self.assumptions.append(atoms[s])

    def rule(self, head, body):
        """ASP rule (an implication)."""
        head_symbols = _normalize(head)
        body_symbols = _normalize(body)

        symbols = head_symbols + body_symbols
        atoms = {}
        for s in symbols:
            atoms[s] = self.backend.add_atom(s)

        # Special assumption atom to allow rules to be in unsat cores
        head_str = ",".join(str(a) for a in head_symbols)
        body_str = ",".join(str(a) for a in body_symbols)
        rule_str = "%s :- %s." % (head_str, body_str)

        rule_atoms = self._register_rule_for_cores(rule_str)

        # print rule before adding
        self.out.write("%s\n" % rule_str)
        self.backend.add_rule(
            [atoms[s] for s in head_symbols],
            [atoms[s] for s in body_symbols] + rule_atoms
        )

    def integrity_constraint(self, clauses, default_negated=None):
        """Add an integrity constraint to the solver.

        Args:
            clauses: clauses to be added to the integrity constraint
            default_negated: clauses to be added to the integrity
                constraint after with a default negation
        """
        symbols, negated_symbols, atoms = _normalize(clauses), [], {}
        if default_negated:
            negated_symbols = _normalize(default_negated)

        for s in symbols + negated_symbols:
            atoms[s] = self.backend.add_atom(s)

        symbols_str = ",".join(str(a) for a in symbols)
        if negated_symbols:
            negated_symbols_str = ",".join(
                "not " + str(a) for a in negated_symbols
            )
            symbols_str += ",{0}".format(negated_symbols_str)
        rule_str = ":- {0}.".format(symbols_str)
        rule_atoms = self._register_rule_for_cores(rule_str)

        # print rule before adding
        self.out.write("{0}\n".format(rule_str))
        self.backend.add_rule(
            [],
            [atoms[s] for s in symbols] +
            [-atoms[s] for s in negated_symbols]
            + rule_atoms
        )

    def iff(self, expr1, expr2):
        self.rule(head=expr1, body=expr2)
        self.rule(head=expr2, body=expr1)

    def one_of_iff(self, head, versions):
        # if there are no versions, skip this one_of_iff
        if not versions:
            return

        self.out.write("%s :- %s.\n" % (head, AspOneOf(*versions)))
        self.out.write("%s :- %s.\n" % (AspOneOf(*versions), head))

        at_least_1_sym = fn.at_least_1(*head.args).symbol()
        at_least_1 = self.backend.add_atom(at_least_1_sym)

        more_than_1_sym = fn.more_than_1(*head.args).symbol()
        more_than_1 = self.backend.add_atom(more_than_1_sym)

        version_atoms = [self.backend.add_atom(f.symbol()) for f in versions]
        self.backend.add_weight_rule(
            [at_least_1], 1, [(v, 1) for v in version_atoms])
        self.backend.add_weight_rule(
            [more_than_1], 2, [(v, 1) for v in version_atoms])

        head_atom = self.backend.add_atom(head.symbol())
        self.backend.add_rule([head_atom], [at_least_1, -more_than_1])

        self.backend.add_rule([], [head_atom, more_than_1])
        self.backend.add_rule([], [head_atom, -at_least_1])

    def solve(
            self, solver_setup, specs, dump=None, nmodels=0,
            timers=False, stats=False, tests=False
    ):
        timer = Timer()

        # Initialize the control object for the solver
        self.control = clingo.Control()
        self.control.configuration.solve.models = nmodels
        self.control.configuration.asp.trans_ext = 'all'
        self.control.configuration.asp.eq = '5'
        self.control.configuration.configuration = 'tweety'
        self.control.configuration.solve.parallel_mode = '2'
        self.control.configuration.solver.opt_strategy = "usc,one"

        # set up the problem -- this generates facts and rules
        self.assumptions = []
        with self.control.backend() as backend:
            self.backend = backend
            solver_setup.setup(self, specs, tests=tests)
        timer.phase("setup")

        # read in the main ASP program and display logic -- these are
        # handwritten, not generated, so we load them as resources
        parent_dir = os.path.dirname(__file__)
        self.control.load(os.path.join(parent_dir, 'concretize.lp'))
        self.control.load(os.path.join(parent_dir, "display.lp"))
        timer.phase("load")

        # Grounding is the first step in the solve -- it turns our facts
        # and first-order logic rules into propositional logic.
        self.control.ground([("base", [])])
        timer.phase("ground")

        # With a grounded program, we can run the solve.
        result = Result()
        models = []  # stable models if things go well
        cores = []   # unsatisfiable cores if they do not

        def on_model(model):
            models.append((model.cost, model.symbols(shown=True, terms=True)))

        solve_result = self.control.solve(
            assumptions=self.assumptions,
            on_model=on_model,
            on_core=cores.append
        )
        timer.phase("solve")

        # once done, construct the solve result
        result.satisfiable = solve_result.satisfiable

        def stringify(x):
            return x.string or str(x)

        if result.satisfiable:
            builder = SpecBuilder(specs)
            min_cost, best_model = min(models)
            tuples = [
                (sym.name, [stringify(a) for a in sym.arguments])
                for sym in best_model
            ]
            answers = builder.build_specs(tuples)
            result.answers.append((list(min_cost), 0, answers))

        elif cores:
            symbols = dict(
                (a.literal, a.symbol)
                for a in self.control.symbolic_atoms
            )
            for core in cores:
                core_symbols = []
                for atom in core:
                    sym = symbols[atom]
                    if sym.name == "rule":
                        sym = sym.arguments[0].string
                    core_symbols.append(sym)
                result.cores.append(core_symbols)

        if timers:
            timer.write()
            print()
        if stats:
            print("Statistics:")
            pprint.pprint(self.control.statistics)

        return result


class SpackSolverSetup(object):
    """Class to set up and run a Spack concretization solve."""

    def __init__(self):
        self.gen = None  # set by setup()
        self.possible_versions = {}
        self.possible_virtuals = None
        self.possible_compilers = []
        self.version_constraints = set()
        self.target_constraints = set()
        self.providers_by_vspec_name = collections.defaultdict(list)
        self.virtual_constraints = set()
        self.compiler_version_constraints = set()
        self.post_facts = []

        # id for dummy variables
        self.card = 0

    def pkg_version_rules(self, pkg):
        """Output declared versions of a package.

        This uses self.possible_versions so that we include any versions
        that arise from a spec.
        """
        pkg = packagize(pkg)

        config = spack.config.get("packages")
        version_prefs = config.get(pkg.name, {}).get("version", {})
        priority = dict((v, i) for i, v in enumerate(version_prefs))

        # The keys below show the order of precedence of factors used
        # to select a version when concretizing.  The item with
        # the "largest" key will be selected.
        #
        # NOTE: When COMPARING VERSIONS, the '@develop' version is always
        #       larger than other versions.  BUT when CONCRETIZING,
        #       the largest NON-develop version is selected by default.
        keyfn = lambda v: (
            # ------- Special direction from the user
            # Respect order listed in packages.yaml
            -priority.get(v, 0),

            # The preferred=True flag (packages or packages.yaml or both?)
            pkg.versions.get(v, {}).get('preferred', False),

            # ------- Regular case: use latest non-develop version by default.
            # Avoid @develop version, which would otherwise be the "largest"
            # in straight version comparisons
            not v.isdevelop(),

            # Compare the version itself
            # This includes the logic:
            #    a) develop > everything (disabled by "not v.isdevelop() above)
            #    b) numeric > non-numeric
            #    c) Numeric or string comparison
            v)

        most_to_least_preferred = sorted(
            self.possible_versions[pkg.name], key=keyfn, reverse=True
        )

        for i, v in enumerate(most_to_least_preferred):
            self.gen.fact(fn.version_declared(pkg.name, v, i))

    def spec_versions(self, spec):
        """Return list of clauses expressing spec's version constraints."""
        spec = specify(spec)
        assert spec.name

        if spec.concrete:
            return [fn.version(spec.name, spec.version)]

        if spec.versions == ver(":"):
            return []

        # record all version constraints for later
        self.version_constraints.add((spec.name, spec.versions))
        return [fn.version_satisfies(spec.name, spec.versions)]

    def target_ranges(self, spec, single_target_fn):
        target = spec.architecture.target

        # Check if the target is a concrete target
        if str(target) in archspec.cpu.TARGETS:
            return [single_target_fn(spec.name, target)]

        self.target_constraints.add((spec.name, target))
        return [fn.node_target_satisfies(spec.name, target)]

    def conflict_rules(self, pkg):
        for trigger, constraints in pkg.conflicts.items():
            for constraint, _ in constraints:
                constraint_body = spack.spec.Spec(pkg.name)
                constraint_body.constrain(constraint)
                constraint_body.constrain(trigger)

                clauses = []
                for s in constraint_body.traverse():
                    clauses += self.spec_clauses(s, body=True)

                # TODO: find a better way to generate clauses for integrity
                # TODO: constraints, instead of generating them for the body
                # TODO: of a rule and filter unwanted functions.
                to_be_filtered = ['node_compiler_hard']
                clauses = [x for x in clauses if x.name not in to_be_filtered]
                external = fn.external(pkg.name)

                self.gen.integrity_constraint(
                    AspAnd(*clauses), AspAnd(external)
                )

    def available_compilers(self):
        """Facts about available compilers."""

        self.gen.h2("Available compilers")
        compilers = self.possible_compilers

        compiler_versions = collections.defaultdict(lambda: set())
        for compiler in compilers:
            compiler_versions[compiler.name].add(compiler.version)

        for compiler in sorted(compiler_versions):
            self.gen.fact(fn.compiler(compiler))
            for v in sorted(compiler_versions[compiler]):
                self.gen.fact(fn.compiler_version(compiler, v))

            self.gen.newline()

    def compiler_defaults(self):
        """Set compiler defaults, given a list of possible compilers."""
        self.gen.h2("Default compiler preferences")

        compiler_list = self.possible_compilers.copy()
        compiler_list = sorted(
            compiler_list, key=lambda x: (x.name, x.version), reverse=True)
        ppk = spack.package_prefs.PackagePrefs("all", 'compiler', all=False)
        matches = sorted(compiler_list, key=ppk)

        for i, cspec in enumerate(matches):
            f = fn.default_compiler_preference(cspec.name, cspec.version, i)
            self.gen.fact(f)

    def compiler_supports_os(self):
        compilers_yaml = spack.compilers.all_compilers_config()
        for entry in compilers_yaml:
            c = spack.spec.CompilerSpec(entry['compiler']['spec'])
            operating_system = entry['compiler']['operating_system']
            self.gen.fact(fn.compiler_supports_os(
                c.name, c.version, operating_system
            ))

    def package_compiler_defaults(self, pkg):
        """Facts about packages' compiler prefs."""

        packages = spack.config.get("packages")
        pkg_prefs = packages.get(pkg.name)
        if not pkg_prefs or "compiler" not in pkg_prefs:
            return

        compiler_list = self.possible_compilers.copy()
        compiler_list = sorted(
            compiler_list, key=lambda x: (x.name, x.version), reverse=True)
        ppk = spack.package_prefs.PackagePrefs(pkg.name, 'compiler', all=False)
        matches = sorted(compiler_list, key=ppk)

        for i, cspec in enumerate(reversed(matches)):
            self.gen.fact(fn.node_compiler_preference(
                pkg.name, cspec.name, cspec.version, -i * 100
            ))

    def pkg_rules(self, pkg, tests):
        pkg = packagize(pkg)

        # versions
        self.pkg_version_rules(pkg)
        self.gen.newline()

        # variants
        for name, variant in sorted(pkg.variants.items()):
            self.gen.fact(fn.variant(pkg.name, name))

            single_value = not variant.multi
            if single_value:
                self.gen.fact(fn.variant_single_value(pkg.name, name))
                self.gen.fact(
                    fn.variant_default_value_from_package_py(
                        pkg.name, name, variant.default)
                )
            else:
                spec_variant = variant.make_default()
                defaults = spec_variant.value
                for val in sorted(defaults):
                    self.gen.fact(
                        fn.variant_default_value_from_package_py(
                            pkg.name, name, val)
                    )

            values = variant.values
            if values is None:
                values = []
            elif isinstance(values, spack.variant.DisjointSetsOfValues):
                union = set()
                for s in values.sets:
                    union.update(s)
                values = union

            # make sure that every variant has at least one posisble value
            if not values:
                values = [variant.default]

            for value in sorted(values):
                self.gen.fact(fn.variant_possible_value(pkg.name, name, value))

            self.gen.newline()

        # conflicts
        self.conflict_rules(pkg)

        # default compilers for this package
        self.package_compiler_defaults(pkg)

        # dependencies
        self.package_dependencies_rules(pkg, tests)

        # virtual preferences
        self.virtual_preferences(
            pkg.name,
            lambda v, p, i: self.gen.fact(
                fn.pkg_provider_preference(pkg.name, v, p, i)
            )
        )

    def package_dependencies_rules(self, pkg, tests):
        """Translate 'depends_on' directives into ASP logic."""
        for name, conditions in sorted(pkg.dependencies.items()):
            for cond, dep in sorted(conditions.items()):
                named_cond = cond.copy()
                named_cond.name = named_cond.name or pkg.name

                for t in sorted(dep.type):
                    # Skip test dependencies if they're not requested at all
                    if t == 'test' and not tests:
                        continue

                    # ... or if they are requested only for certain packages
                    if t == 'test' and (not isinstance(tests, bool)
                                        and pkg.name not in tests):
                        continue

                    if cond == spack.spec.Spec():
                        self.gen.fact(
                            fn.declared_dependency(
                                dep.pkg.name, dep.spec.name, t
                            )
                        )
                    else:
                        clauses = self.spec_traverse_clauses(named_cond)

                        self.gen.rule(
                            fn.declared_dependency(
                                dep.pkg.name, dep.spec.name, t
                            ), self.gen._and(*clauses)
                        )

                # add constraints on the dependency from dep spec.
                if spack.repo.path.is_virtual(dep.spec.name):
                    self.virtual_constraints.add(str(dep.spec))
                    conditions = ([fn.real_node(pkg.name)] +
                                  self.spec_clauses(named_cond, body=True))
                    self.gen.rule(
                        head=fn.single_provider_for(
                            str(dep.spec.name), str(dep.spec.versions)
                        ),
                        body=self.gen._and(*conditions)
                    )
                else:
                    clauses = self.spec_clauses(dep.spec)
                    for clause in clauses:
                        self.gen.rule(
                            clause,
                            self.gen._and(
                                fn.depends_on(dep.pkg.name, dep.spec.name),
                                *self.spec_traverse_clauses(named_cond)
                            )
                        )
            self.gen.newline()

    def spec_traverse_clauses(self, named_cond):
        clauses = []
        for d in named_cond.traverse():
            clauses.extend(self.spec_clauses(d, body=True))
        return clauses

    def virtual_preferences(self, pkg_name, func):
        """Call func(vspec, provider, i) for each of pkg's provider prefs."""
        config = spack.config.get("packages")
        pkg_prefs = config.get(pkg_name, {}).get("providers", {})
        for vspec, providers in pkg_prefs.items():
            if vspec not in self.possible_virtuals:
                continue

            for i, provider in enumerate(providers):
                func(vspec, provider, i + 10)

    def provider_defaults(self):
        self.gen.h2("Default virtual providers")
        assert self.possible_virtuals is not None
        self.virtual_preferences(
            "all",
            lambda v, p, i: self.gen.fact(
                fn.default_provider_preference(v, p, i))
        )

    def external_packages(self):
        """Facts on external packages, as read from packages.yaml"""
        # Read packages.yaml and normalize it, so that it
        # will not contain entries referring to virtual
        # packages.
        packages_yaml = spack.config.get("packages")
        packages_yaml = _normalize_packages_yaml(packages_yaml)

        self.gen.h1('External packages')
        for pkg_name, data in packages_yaml.items():
            if pkg_name == 'all':
                continue

            if 'externals' not in data:
                self.gen.fact(fn.external(pkg_name).symbol(positive=False))

            self.gen.h2('External package: {0}'.format(pkg_name))
            # Check if the external package is buildable. If it is
            # not then "external(<pkg>)" is a fact.
            external_buildable = data.get('buildable', True)
            if not external_buildable:
                self.gen.fact(fn.external_only(pkg_name))

            # Read a list of all the specs for this package
            externals = data.get('externals', [])
            external_specs = [spack.spec.Spec(x['spec']) for x in externals]

            # Compute versions with appropriate weights
            external_versions = [
                (x.version, idx) for idx, x in enumerate(external_specs)
            ]
            external_versions = [
                (v, -(w + 1), idx)
                for w, (v, idx) in enumerate(sorted(external_versions))
            ]
            for version, weight, id in external_versions:
                self.gen.fact(fn.external_version_declared(
                    pkg_name, str(version), weight, id
                ))

            # Establish an equivalence between "external_spec(pkg, id)"
            # and the clauses of that spec, so that we have a uniform
            # way to identify it
            spec_id_list = []
            for id, spec in enumerate(external_specs):
                self.gen.newline()
                spec_id = fn.external_spec(pkg_name, id)
                clauses = self.spec_clauses(spec, body=True)
                # This is an iff below, wish it could be written in a
                # more compact form
                self.gen.rule(head=spec_id.symbol(), body=AspAnd(*clauses))
                for clause in clauses:
                    self.gen.rule(clause, spec_id.symbol())
                spec_id_list.append(spec_id)

            # If one of the external specs is selected then the package
            # is external and viceversa
            # TODO: make it possible to declare the rule like below
            # self.gen.iff(expr1=fn.external(pkg_name),
            #              expr2=one_of_the_externals)
            self.gen.newline()
            # FIXME: self.gen.one_of_iff(fn.external(pkg_name), spec_id_list)
            one_of_the_externals = self.gen.one_of(*spec_id_list)
            external_str = fn.external(pkg_name)
            external_rule = "{0} :- {1}.\n{1} :- {0}.\n".format(
                external_str, str(one_of_the_externals)
            )
            self.gen.out.write(external_rule)
            self.gen.control.add("base", [], external_rule)

    def preferred_variants(self, pkg_name):
        """Facts on concretization preferences, as read from packages.yaml"""
        preferences = spack.package_prefs.PackagePrefs
        preferred_variants = preferences.preferred_variants(pkg_name)
        if not preferred_variants:
            return

        for variant_name in sorted(preferred_variants):
            variant = preferred_variants[variant_name]
            values = variant.value

            if not isinstance(values, tuple):
                values = (values,)

            for value in values:
                self.gen.fact(fn.variant_default_value_from_packages_yaml(
                    pkg_name, variant.name, value
                ))

    def preferred_targets(self, pkg_name):
        key_fn = spack.package_prefs.PackagePrefs(pkg_name, 'target')
        target_specs = [
            spack.spec.Spec('target={0}'.format(target_name))
            for target_name in archspec.cpu.TARGETS
        ]
        preferred_targets = [x for x in target_specs if key_fn(x) < 0]
        if not preferred_targets:
            return

        preferred = preferred_targets[0]
        self.gen.fact(fn.package_target_weight(
            str(preferred.architecture.target), pkg_name, -30
        ))

    def preferred_versions(self, pkg_name):
        packages_yaml = spack.config.get('packages')
        versions = packages_yaml.get(pkg_name, {}).get('version', [])
        if not versions:
            return

        for idx, version in enumerate(reversed(versions)):
            self.gen.fact(
                fn.preferred_version_declared(pkg_name, version, -(idx + 1))
            )

    def flag_defaults(self):
        self.gen.h2("Compiler flag defaults")

        # types of flags that can be on specs
        for flag in spack.spec.FlagMap.valid_compiler_flags():
            self.gen.fact(fn.flag_type(flag))
        self.gen.newline()

        # flags from compilers.yaml
        compilers = all_compilers_in_config()
        for compiler in compilers:
            for name, flags in compiler.flags.items():
                for flag in flags:
                    self.gen.fact(fn.compiler_version_flag(
                        compiler.name, compiler.version, name, flag))

    def spec_clauses(self, spec, body=False):
        """Return a list of clauses for a spec mandates are true.

        Arguments:
            spec (Spec): the spec to analyze
            body (bool): if True, generate clauses to be used in rule bodies
                (final values) instead of rule heads (setters).
        """
        clauses = []

        # TODO: do this with consistent suffixes.
        class Head(object):
            node = fn.node
            node_platform = fn.node_platform_set
            node_os = fn.node_os_set
            node_target = fn.node_target_set
            variant = fn.variant_set
            node_compiler = fn.node_compiler_hard
            node_compiler_version = fn.node_compiler_version_hard
            node_flag = fn.node_flag_set

        class Body(object):
            node = fn.node
            node_platform = fn.node_platform
            node_os = fn.node_os
            node_target = fn.node_target
            variant = fn.variant_value
            node_compiler = fn.node_compiler
            node_compiler_version = fn.node_compiler_version
            node_flag = fn.node_flag

        f = Body if body else Head

        if spec.name:
            clauses.append(f.node(spec.name))

        clauses.extend(self.spec_versions(spec))

        # seed architecture at the root (we'll propagate later)
        # TODO: use better semantics.
        arch = spec.architecture
        if arch:
            if arch.platform:
                clauses.append(f.node_platform(spec.name, arch.platform))
            if arch.os:
                clauses.append(f.node_os(spec.name, arch.os))
            if arch.target:
                clauses.extend(self.target_ranges(spec, f.node_target))

        # variants
        for vname, variant in sorted(spec.variants.items()):
            value = variant.value
            if isinstance(value, tuple):
                for v in value:
                    if v == '*':
                        continue
                    clauses.append(f.variant(spec.name, vname, v))
            elif value != '*':
                clauses.append(f.variant(spec.name, vname, variant.value))

        # compiler and compiler version
        if spec.compiler:
            clauses.append(f.node_compiler(spec.name, spec.compiler.name))

            if spec.compiler.concrete:
                clauses.append(f.node_compiler_version(
                    spec.name, spec.compiler.name, spec.compiler.version))

            elif spec.compiler.versions:
                clauses.append(
                    fn.node_compiler_version_satisfies(
                        spec.name, spec.compiler.name, spec.compiler.versions))
                self.compiler_version_constraints.add(
                    (spec.name, spec.compiler))

        # compiler flags
        for flag_type, flags in spec.compiler_flags.items():
            for flag in flags:
                clauses.append(f.node_flag(spec.name, flag_type, flag))

        # TODO
        # namespace

        return clauses

    def build_version_dict(self, possible_pkgs, specs):
        """Declare any versions in specs not declared in packages."""
        self.possible_versions = collections.defaultdict(lambda: set())

        for pkg_name in possible_pkgs:
            pkg = spack.repo.get(pkg_name)
            for v in pkg.versions:
                self.possible_versions[pkg_name].add(v)

        for spec in specs:
            for dep in spec.traverse():
                if dep.versions.concrete:
                    self.possible_versions[dep.name].add(dep.version)

    def _supported_targets(self, compiler, targets):
        """Get a list of which targets are supported by the compiler.

        Results are ordered most to least recent.
        """
        supported = []

        for target in targets:
            try:
                target.optimization_flags(compiler.name, compiler.version)
                supported.append(target)
            except archspec.cpu.UnsupportedMicroarchitecture:
                continue
            except ValueError:
                continue

        return sorted(supported, reverse=True)

    def platform_defaults(self):
        self.gen.h2('Default platform')
        platform = spack.architecture.platform()
        self.gen.fact(fn.node_platform_default(platform))

    def os_defaults(self, specs):
        self.gen.h2('Possible operating systems')
        platform = spack.architecture.platform()

        # create set of OS's to consider
        possible = set([
            platform.front_os, platform.back_os, platform.default_os])
        for spec in specs:
            if spec.architecture and spec.architecture.os:
                possible.add(spec.architecture.os)

        # make directives for possible OS's
        for possible_os in sorted(possible):
            self.gen.fact(fn.os(possible_os))

        # mark this one as default
        self.gen.fact(fn.node_os_default(platform.default_os))

    def target_defaults(self, specs):
        """Add facts about targets and target compatibility."""
        self.gen.h2('Default target')

        platform = spack.architecture.platform()
        uarch = archspec.cpu.TARGETS.get(platform.default)

        self.gen.h2('Target compatibility')

        compatible_targets = [uarch] + uarch.ancestors
        compilers = self.possible_compilers

        # this loop can be used to limit the number of targets
        # considered. Right now we consider them all, but it seems that
        # many targets can make things slow.
        # TODO: investigate this.
        best_targets = set([uarch.family.name])
        for compiler in sorted(compilers):
            supported = self._supported_targets(compiler, compatible_targets)

            if not supported:
                continue

            for target in supported:
                best_targets.add(target.name)
                self.gen.fact(fn.compiler_supports_target(
                    compiler.name, compiler.version, target.name))
                self.gen.fact(fn.compiler_supports_target(
                    compiler.name, compiler.version, uarch.family.name))

        # add any targets explicitly mentioned in specs
        for spec in specs:
            if not spec.architecture or not spec.architecture.target:
                continue

            target = archspec.cpu.TARGETS.get(spec.target.name)
            if not target:
                raise ValueError("Invalid target: ", spec.target.name)
            if target not in compatible_targets:
                compatible_targets.append(target)

        i = 0
        for target in compatible_targets:
            self.gen.fact(fn.target(target.name))
            self.gen.fact(fn.target_family(target.name, target.family.name))
            for parent in sorted(target.parents):
                self.gen.fact(fn.target_parent(target.name, parent.name))

            # prefer best possible targets; weight others poorly so
            # they're not used unless set explicitly
            if target.name in best_targets:
                self.gen.fact(fn.default_target_weight(target.name, i))
                i += 1
            else:
                self.gen.fact(fn.default_target_weight(target.name, 100))

            self.gen.newline()

    def virtual_providers(self):
        self.gen.h2("Virtual providers")
        assert self.possible_virtuals is not None

        # what provides what
        for vspec in sorted(self.possible_virtuals):
            self.gen.fact(fn.virtual(vspec))
            all_providers = sorted(spack.repo.path.providers_for(vspec))
            for idx, provider in enumerate(all_providers):
                provides_atom = fn.provides_virtual(provider.name, vspec)
                possible_provider_fn = fn.possible_provider(
                    vspec, provider.name, idx
                )
                item = (idx, provider, possible_provider_fn)
                self.providers_by_vspec_name[vspec].append(item)
                clauses = self.spec_clauses(provider, body=True)
                clauses_but_node = [c for c in clauses if c.name != 'node']
                if clauses_but_node:
                    self.gen.rule(provides_atom, AspAnd(*clauses_but_node))
                else:
                    self.gen.fact(provides_atom)
                for clause in clauses:
                    self.gen.rule(clause, possible_provider_fn)
                self.gen.newline()
            self.gen.newline()

    def generate_possible_compilers(self, specs):
        compilers = all_compilers_in_config()
        cspecs = set([c.spec for c in compilers])

        # add compiler specs from the input line to possibilities if we
        # don't require compilers to exist.
        strict = spack.concretize.Concretizer().check_for_compiler_existence
        for spec in specs:
            for s in spec.traverse():
                if not s.compiler or not s.compiler.concrete:
                    continue

                if strict and s.compiler not in cspecs:
                    raise spack.concretize.UnavailableCompilerVersionError(
                        s.compiler
                    )
                else:
                    cspecs.add(s.compiler)
                    self.gen.fact(fn.allow_compiler(
                        s.compiler.name, s.compiler.version
                    ))

        return cspecs

    def define_version_constraints(self):
        """Define what version_satisfies(...) means in ASP logic."""
        for pkg_name, versions in sorted(self.version_constraints):
            # version must be *one* of the ones the spec allows.
            allowed_versions = [
                v for v in sorted(self.possible_versions[pkg_name])
                if v.satisfies(versions)
            ]

            # This is needed to account for a variable number of
            # numbers e.g. if both 1.0 and 1.0.2 are possible versions
            exact_match = [v for v in allowed_versions if v == versions]
            if exact_match:
                allowed_versions = exact_match

            # don't bother restricting anything if all versions are allowed
            if len(allowed_versions) == len(self.possible_versions[pkg_name]):
                continue

            predicates = [fn.version(pkg_name, v) for v in allowed_versions]

            # version_satisfies(pkg, constraint) is true if and only if a
            # satisfying version is set for the package
            self.gen.one_of_iff(
                fn.version_satisfies(pkg_name, versions),
                predicates,
            )
            self.gen.newline()

    def define_virtual_constraints(self):
        for vspec_str in sorted(self.virtual_constraints):
            vspec = spack.spec.Spec(vspec_str)
            self.gen.h2("Virtual spec: {0}".format(vspec_str))
            providers = spack.repo.path.providers_for(vspec_str)
            candidates = self.providers_by_vspec_name[vspec.name]
            possible_providers = [
                func for idx, spec, func in candidates if spec in providers
            ]

            self.gen.newline()
            single_provider_for = fn.single_provider_for(
                vspec.name, vspec.versions
            )
            one_of_the_possibles = self.gen.one_of(*possible_providers)
            single_provider_rule = "{0} :- {1}.\n{1} :- {0}.\n".format(
                single_provider_for, str(one_of_the_possibles)
            )
            self.gen.out.write(single_provider_rule)
            self.gen.control.add("base", [], single_provider_rule)

    def define_compiler_version_constraints(self):
        compiler_list = spack.compilers.all_compiler_specs()
        compiler_list = list(sorted(set(compiler_list)))

        for pkg_name, cspec in self.compiler_version_constraints:
            possible_compiler_versions = [
                fn.node_compiler_version(
                    pkg_name, compiler.name, compiler.version)
                for compiler in compiler_list
                if compiler.satisfies(cspec)
            ]

            self.gen.one_of_iff(
                fn.node_compiler_version_satisfies(
                    pkg_name, cspec.name, cspec.versions),
                possible_compiler_versions,
            )
            self.gen.newline()

    def define_target_constraints(self):

        def _all_targets_satisfiying(single_constraint):
            allowed_targets = []
            t_min, _, t_max = single_constraint.partition(':')
            for test_target in archspec.cpu.TARGETS.values():
                # Check lower bound
                if t_min and not t_min <= test_target:
                    continue

                # Check upper bound
                if t_max and not t_max >= test_target:
                    continue

                allowed_targets.append(test_target)
            return allowed_targets

        cache = {}
        for spec_name, target_constraint in sorted(self.target_constraints):

            # Construct the list of allowed targets for this constraint
            allowed_targets = []
            for single_constraint in str(target_constraint).split(','):
                if single_constraint not in cache:
                    cache[single_constraint] = _all_targets_satisfiying(
                        single_constraint
                    )
                allowed_targets.extend(cache[single_constraint])

            allowed_targets = [
                fn.node_target(spec_name, t) for t in allowed_targets
            ]

            self.gen.one_of_iff(
                fn.node_target_satisfies(spec_name, target_constraint),
                allowed_targets,
            )
            self.gen.newline()

    def setup(self, driver, specs, tests=False):
        """Generate an ASP program with relevant constraints for specs.

        This calls methods on the solve driver to set up the problem with
        facts and rules from all possible dependencies of the input
        specs, as well as constraints from the specs themselves.

        Arguments:
            specs (list): list of Specs to solve

        """
        # preliminary checks
        check_packages_exist(specs)

        # get list of all possible dependencies
        self.possible_virtuals = set(
            x.name for x in specs if x.virtual
        )
        possible = spack.package.possible_dependencies(
            *specs,
            virtuals=self.possible_virtuals,
            deptype=spack.dependency.all_deptypes
        )
        pkgs = set(possible)

        # driver is used by all the functions below to add facts and
        # rules to generate an ASP program.
        self.gen = driver

        # get possible compilers
        self.possible_compilers = self.generate_possible_compilers(specs)

        # traverse all specs and packages to build dict of possible versions
        self.build_version_dict(possible, specs)

        self.gen.h1('General Constraints')
        self.available_compilers()
        self.compiler_defaults()
        self.compiler_supports_os()

        # architecture defaults
        self.platform_defaults()
        self.os_defaults(specs)
        self.target_defaults(specs)

        self.virtual_providers()
        self.provider_defaults()
        self.external_packages()
        self.flag_defaults()

        self.gen.h1('Package Constraints')
        for pkg in sorted(pkgs):
            self.gen.h2('Package rules: %s' % pkg)
            self.pkg_rules(pkg, tests=tests)
            self.gen.h2('Package preferences: %s' % pkg)
            self.preferred_variants(pkg)
            self.preferred_targets(pkg)
            self.preferred_versions(pkg)

        self.gen.h1('Spec Constraints')
        for spec in sorted(specs):
            if not spec.virtual:
                self.gen.fact(fn.root(spec.name))
            else:
                self.gen.fact(fn.virtual_root(spec.name))

            for dep in spec.traverse():
                self.gen.h2('Spec: %s' % str(dep))
                # Inject dev_path from environment
                _develop_specs_from_env(dep)
                if dep.virtual:
                    for clause in self.virtual_spec_clauses(dep):
                        self.gen.fact(clause)
                else:
                    for clause in self.spec_clauses(dep):
                        self.gen.fact(clause)
                        # TODO: This might need to be moved somewhere else.
                        # TODO: It's needed to account for open-ended variants
                        # TODO: validated through a function. The rationale is
                        # TODO: that if a value is set from cli and validated
                        # TODO: then it's also a possible value.
                        if clause.name == 'variant_set':
                            variant_name = clause.args[1]
                            # 'dev_path' and 'patches are treated in a
                            # special way, as they are injected from cli
                            # or files
                            if variant_name == 'dev_path':
                                pkg_name = clause.args[0]
                                self.gen.fact(fn.variant(
                                    pkg_name, variant_name
                                ))
                                self.gen.fact(fn.variant_single_value(
                                    pkg_name, variant_name
                                ))
                            elif variant_name == 'patches':
                                pkg_name = clause.args[0]
                                self.gen.fact(fn.variant(
                                    pkg_name, variant_name
                                ))
                            else:
                                variant_def = dep.package.variants[
                                    variant_name
                                ]
                                variant_def.validate_or_raise(
                                    dep.variants[variant_name],
                                    dep.package
                                )
                            # State that this variant is a possible value
                            # to account for variant values that are not
                            # enumerated explicitly
                            self.gen.fact(
                                fn.variant_possible_value(*clause.args)
                            )

        self.gen.h1("Virtual Constraints")
        self.define_virtual_constraints()

        self.gen.h1("Version Constraints")
        self.define_version_constraints()

        self.gen.h1("Compiler Version Constraints")
        self.define_compiler_version_constraints()

        self.gen.h1("Target Constraints")
        self.define_target_constraints()

    def virtual_spec_clauses(self, dep):
        assert dep.virtual
        self.virtual_constraints.add(str(dep))
        clauses = [
            fn.virtual_node(dep.name),
            fn.single_provider_for(str(dep.name), str(dep.versions))
        ]
        return clauses


class SpecBuilder(object):
    """Class with actions to rebuild a spec from ASP results."""
    def __init__(self, specs):
        self._result = None
        self._command_line_specs = specs
        self._flag_sources = collections.defaultdict(lambda: set())
        self._flag_compiler_defaults = set()

    def node(self, pkg):
        if pkg not in self._specs:
            self._specs[pkg] = spack.spec.Spec(pkg)

    def _arch(self, pkg):
        arch = self._specs[pkg].architecture
        if not arch:
            arch = spack.spec.ArchSpec()
            self._specs[pkg].architecture = arch
        return arch

    def node_platform(self, pkg, platform):
        self._arch(pkg).platform = platform

    def node_os(self, pkg, os):
        self._arch(pkg).os = os

    def node_target(self, pkg, target):
        self._arch(pkg).target = target

    def variant_value(self, pkg, name, value):
        # FIXME: is there a way not to special case 'dev_path' everywhere?
        if name == 'dev_path':
            self._specs[pkg].variants.setdefault(
                name,
                spack.variant.SingleValuedVariant(name, value)
            )
            return

        if name == 'patches':
            self._specs[pkg].variants.setdefault(
                name,
                spack.variant.MultiValuedVariant(name, value)
            )
            return

        pkg_class = spack.repo.path.get_pkg_class(pkg)

        variant = self._specs[pkg].variants.get(name)
        if variant:
            # it's multi-valued
            variant.append(value)
        else:
            variant = pkg_class.variants[name].make_variant(value)
            self._specs[pkg].variants[name] = variant

    def version(self, pkg, version):
        self._specs[pkg].versions = ver([version])

    def node_compiler(self, pkg, compiler):
        self._specs[pkg].compiler = spack.spec.CompilerSpec(compiler)

    def node_compiler_version(self, pkg, compiler, version):
        self._specs[pkg].compiler.versions = spack.version.VersionList(
            [version])

    def node_flag_compiler_default(self, pkg):
        self._flag_compiler_defaults.add(pkg)

    def node_flag(self, pkg, flag_type, flag):
        self._specs[pkg].compiler_flags.setdefault(flag_type, []).append(flag)

    def node_flag_source(self, pkg, source):
        self._flag_sources[pkg].add(source)

    def no_flags(self, pkg, flag_type):
        self._specs[pkg].compiler_flags[flag_type] = []

    def external_spec(self, pkg, idx):
        """This means that the external spec and index idx
        has been selected for this package.
        """
        packages_yaml = spack.config.get('packages')
        packages_yaml = _normalize_packages_yaml(packages_yaml)
        spec_info = packages_yaml[pkg]['externals'][int(idx)]
        self._specs[pkg].external_path = spec_info.get('prefix', None)
        self._specs[pkg].external_modules = (
            spack.spec.Spec._format_module_list(spec_info.get('modules', None))
        )
        self._specs[pkg].extra_attributes = spec_info.get(
            'extra_attributes', {}
        )

    def depends_on(self, pkg, dep, type):
        dependency = self._specs[pkg]._dependencies.get(dep)
        if not dependency:
            self._specs[pkg]._add_dependency(
                self._specs[dep], (type,))
        else:
            dependency.add_type(type)

    def reorder_flags(self):
        """Order compiler flags on specs in predefined order.

        We order flags so that any node's flags will take priority over
        those of its dependents.  That is, the deepest node in the DAG's
        flags will appear last on the compile line, in the order they
        were specified.

        The solver determines wihch flags are on nodes; this routine
        imposes order afterwards.
        """
        # nodes with no flags get flag order from compiler
        compilers = dict((c.spec, c) for c in all_compilers_in_config())
        for pkg in self._flag_compiler_defaults:
            spec = self._specs[pkg]
            compiler_flags = compilers[spec.compiler].flags
            check_same_flags(spec.compiler_flags, compiler_flags)
            spec.compiler_flags.update(compiler_flags)

        # index of all specs (and deps) from the command line by name
        cmd_specs = dict(
            (s.name, s)
            for spec in self._command_line_specs
            for s in spec.traverse())

        # iterate through specs with specified flags
        for pkg, sources in self._flag_sources.items():
            spec = self._specs[pkg]

            # order is determined by the DAG.  A spec's flags come after
            # any from its ancestors on the compile line.
            order = [
                s.name
                for s in spec.traverse(order='post', direction='parents')]

            # sort the sources in our DAG order
            sorted_sources = sorted(
                sources, key=lambda s: order.index(s))

            # add flags from each source, lowest to highest precedence
            flags = collections.defaultdict(lambda: [])
            for source_name in sorted_sources:
                source = cmd_specs[source_name]
                for name, flag_list in source.compiler_flags.items():
                    extend_flag_list(flags[name], flag_list)

            check_same_flags(spec.compiler_flags, flags)
            spec.compiler_flags.update(flags)

    def build_specs(self, function_tuples):
        # Functions don't seem to be in particular order in output.  Sort
        # them here so that directives that build objects (like node and
        # node_compiler) are called in the right order.
        function_tuples.sort(key=lambda f: {
            "node": -2,
            "node_compiler": -1,
        }.get(f[0], 0))

        self._specs = {}
        for name, args in function_tuples:
            action = getattr(self, name, None)

            # print out unknown actions so we can display them for debugging
            if not action:
                msg = "%s(%s)" % (name, ", ".join(str(a) for a in args))
                tty.debug(msg)
                continue

            assert action and callable(action)
            action(*args)

        # namespace assignment is done after the fact, as it is not
        # currently part of the solve
        for spec in self._specs.values():
            repo = spack.repo.path.repo_for_pkg(spec)
            spec.namespace = repo.namespace

        # fix flags after all specs are constructed
        self.reorder_flags()

        for s in self._specs.values():
            spack.spec.Spec.inject_patches_variant(s)

        # Add external paths to specs with just external modules
        for s in self._specs.values():
            spack.spec.Spec.ensure_external_path_if_external(s)

        for s in self._specs.values():
            _develop_specs_from_env(s)

        for s in self._specs.values():
            s._mark_concrete()

        for s in self._specs.values():
            spack.spec.Spec.ensure_no_deprecated(s)

        return self._specs


def highlight(string):
    """Syntax highlighting for ASP programs"""
    # variables
    string = re.sub(r'\b([A-Z])\b', r'@y{\1}', string)

    # implications
    string = re.sub(r':-', r'@*G{:-}', string)

    # final periods
    pattern = re.compile(r'^([^%].*)\.$', flags=re.MULTILINE)
    string = re.sub(pattern, r'\1@*G{.}', string)

    # directives
    string = re.sub(
        r'(#\w*)( (?:\w*)?)((?:/\d+)?)', r'@*B{\1}@c{\2}\3', string)

    # functions
    string = re.sub(r'(\w[\w-]+)\(([^)]*)\)', r'@C{\1}@w{(}\2@w{)}', string)

    # comments
    pattern = re.compile(r'(%.*)$', flags=re.MULTILINE)
    string = re.sub(pattern, r'@w\1@.', string)

    # strings
    string = re.sub(r'("[^"]*")', r'@m{\1}', string)

    # result
    string = re.sub(r'\bUNSATISFIABLE', "@R{UNSATISFIABLE}", string)
    string = re.sub(r'\bINCONSISTENT', "@R{INCONSISTENT}", string)
    string = re.sub(r'\bSATISFIABLE', "@G{SATISFIABLE}", string)
    string = re.sub(r'\bOPTIMUM FOUND', "@G{OPTIMUM FOUND}", string)

    return string


def _develop_specs_from_env(spec):
    env = spack.environment.get_env(None, None)
    dev_info = env.dev_specs.get(spec.name, {}) if env else {}
    if not dev_info:
        return

    path = dev_info['path']
    path = path if os.path.isabs(path) else os.path.join(env.path, path)

    if 'dev_path' in spec.variants:
        assert spec.variants['dev_path'].value == path
    else:
        spec.variants.setdefault(
            'dev_path', spack.variant.SingleValuedVariant('dev_path', path)
        )
    spec.constrain(dev_info['spec'])


#
# These are handwritten parts for the Spack ASP model.
#
def solve(specs, dump=(), models=0, timers=False, stats=False, tests=False):
    """Solve for a stable model of specs.

    Arguments:
        specs (list): list of Specs to solve.
        dump (tuple): what to dump
        models (int): number of models to search (default: 0)
    """
    driver = PyclingoDriver()
    if "asp" in dump:
        driver.out = sys.stdout

    # Check upfront that the variants are admissible
    for root in specs:
        for s in root.traverse():
            if s.virtual:
                continue
            spack.spec.Spec.ensure_valid_variants(s)

    setup = SpackSolverSetup()
    return driver.solve(setup, specs, dump, models, timers, stats, tests)

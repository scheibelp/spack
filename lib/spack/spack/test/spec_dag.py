##############################################################################
# Copyright (c) 2013, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory.
#
# This file is part of Spack.
# Written by Todd Gamblin, tgamblin@llnl.gov, All rights reserved.
# LLNL-CODE-647188
#
# For details, see https://github.com/llnl/spack
# Please also see the LICENSE file for our notice and the LGPL.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License (as published by
# the Free Software Foundation) version 2.1 dated February 1999.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the IMPLIED WARRANTY OF
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the terms and
# conditions of the GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
##############################################################################
"""
These tests check Spec DAG operations using dummy packages.
You can find the dummy packages here::

    spack/lib/spack/spack/test/mock_packages
"""
import spack
import spack.package

from spack.spec import Spec
from spack.test.mock_packages_test import *


class SpecDagTest(MockPackagesTest):

    def test_conflicting_package_constraints(self):
        self.set_pkg_dep('mpileaks', 'mpich@1.0')
        self.set_pkg_dep('callpath', 'mpich@2.0')

        spec = Spec('mpileaks ^mpich ^callpath ^dyninst ^libelf ^libdwarf')

        # TODO: try to do something to showt that the issue was with
        # TODO: the user's input or with package inconsistencies.
        self.assertRaises(spack.spec.UnsatisfiableVersionSpecError,
                          spec.normalize)


    def test_preorder_node_traversal(self):
        dag = Spec('mpileaks ^zmpi')
        dag.normalize()

        names = ['mpileaks', 'callpath', 'dyninst', 'libdwarf', 'libelf',
                 'zmpi', 'fake']
        pairs = zip([0,1,2,3,4,2,3], names)

        traversal = dag.traverse()
        self.assertEqual([x.name for x in traversal], names)

        traversal = dag.traverse(depth=True)
        self.assertEqual([(x, y.name) for x,y in traversal], pairs)


    def test_preorder_edge_traversal(self):
        dag = Spec('mpileaks ^zmpi')
        dag.normalize()

        names = ['mpileaks', 'callpath', 'dyninst', 'libdwarf', 'libelf',
                 'libelf', 'zmpi', 'fake', 'zmpi']
        pairs = zip([0,1,2,3,4,3,2,3,1], names)

        traversal = dag.traverse(cover='edges')
        self.assertEqual([x.name for x in traversal], names)

        traversal = dag.traverse(cover='edges', depth=True)
        self.assertEqual([(x, y.name) for x,y in traversal], pairs)


    def test_preorder_path_traversal(self):
        dag = Spec('mpileaks ^zmpi')
        dag.normalize()

        names = ['mpileaks', 'callpath', 'dyninst', 'libdwarf', 'libelf',
                 'libelf', 'zmpi', 'fake', 'zmpi', 'fake']
        pairs = zip([0,1,2,3,4,3,2,3,1,2], names)

        traversal = dag.traverse(cover='paths')
        self.assertEqual([x.name for x in traversal], names)

        traversal = dag.traverse(cover='paths', depth=True)
        self.assertEqual([(x, y.name) for x,y in traversal], pairs)


    def test_postorder_node_traversal(self):
        dag = Spec('mpileaks ^zmpi')
        dag.normalize()

        names = ['libelf', 'libdwarf', 'dyninst', 'fake', 'zmpi',
                 'callpath', 'mpileaks']
        pairs = zip([4,3,2,3,2,1,0], names)

        traversal = dag.traverse(order='post')
        self.assertEqual([x.name for x in traversal], names)

        traversal = dag.traverse(depth=True, order='post')
        self.assertEqual([(x, y.name) for x,y in traversal], pairs)


    def test_postorder_edge_traversal(self):
        dag = Spec('mpileaks ^zmpi')
        dag.normalize()

        names = ['libelf', 'libdwarf', 'libelf', 'dyninst', 'fake', 'zmpi',
                 'callpath', 'zmpi', 'mpileaks']
        pairs = zip([4,3,3,2,3,2,1,1,0], names)

        traversal = dag.traverse(cover='edges', order='post')
        self.assertEqual([x.name for x in traversal], names)

        traversal = dag.traverse(cover='edges', depth=True, order='post')
        self.assertEqual([(x, y.name) for x,y in traversal], pairs)


    def test_postorder_path_traversal(self):
        dag = Spec('mpileaks ^zmpi')
        dag.normalize()

        names = ['libelf', 'libdwarf', 'libelf', 'dyninst', 'fake', 'zmpi',
                 'callpath', 'fake', 'zmpi', 'mpileaks']
        pairs = zip([4,3,3,2,3,2,1,2,1,0], names)

        traversal = dag.traverse(cover='paths', order='post')
        self.assertEqual([x.name for x in traversal], names)

        traversal = dag.traverse(cover='paths', depth=True, order='post')
        self.assertEqual([(x, y.name) for x,y in traversal], pairs)


    def test_conflicting_spec_constraints(self):
        mpileaks = Spec('mpileaks ^mpich ^callpath ^dyninst ^libelf ^libdwarf')

        # Normalize then add conflicting constraints to the DAG (this is an
        # extremely unlikely scenario, but we test for it anyway)
        mpileaks.normalize()
        mpileaks.dependencies['mpich'] = Spec('mpich@1.0')
        mpileaks.dependencies['callpath'].dependencies['mpich'] = Spec('mpich@2.0')

        self.assertRaises(spack.spec.InconsistentSpecError, mpileaks.flatten)


    def test_normalize_twice(self):
        """Make sure normalize can be run twice on the same spec,
           and that it is idempotent."""
        spec = Spec('mpileaks')
        spec.normalize()
        n1 = spec.copy()

        spec.normalize()
        self.assertEqual(n1, spec)


    def test_normalize_a_lot(self):
        spec = Spec('mpileaks')
        spec.normalize()
        spec.normalize()
        spec.normalize()
        spec.normalize()


    def test_normalize_with_virtual_spec(self):
        dag = Spec('mpileaks',
                   Spec('callpath',
                        Spec('dyninst',
                             Spec('libdwarf',
                                  Spec('libelf')),
                             Spec('libelf')),
                        Spec('mpi')),
                   Spec('mpi'))
        dag.normalize()

        # make sure nothing with the same name occurs twice
        counts = {}
        for spec in dag.traverse(key=id):
            if not spec.name in counts:
                counts[spec.name] = 0
            counts[spec.name] += 1

        for name in counts:
            self.assertEqual(counts[name], 1, "Count for %s was not 1!" % name)


    def check_links(self, spec_to_check):
        for spec in spec_to_check.traverse():
            for dependent in spec.dependents.values():
                self.assertTrue(
                    spec.name in dependent.dependencies,
                    "%s not in dependencies of %s" % (spec.name, dependent.name))

            for dependency in spec.dependencies.values():
                self.assertTrue(
                    spec.name in dependency.dependents,
                    "%s not in dependents of %s" % (spec.name, dependency.name))


    def test_dependents_and_dependencies_are_correct(self):
        spec = Spec('mpileaks',
                   Spec('callpath',
                        Spec('dyninst',
                             Spec('libdwarf',
                                  Spec('libelf')),
                             Spec('libelf')),
                        Spec('mpi')),
                   Spec('mpi'))

        self.check_links(spec)
        spec.normalize()
        self.check_links(spec)


    def test_unsatisfiable_version(self):
        self.set_pkg_dep('mpileaks', 'mpich@1.0')
        spec = Spec('mpileaks ^mpich@2.0 ^callpath ^dyninst ^libelf ^libdwarf')
        self.assertRaises(spack.spec.UnsatisfiableVersionSpecError, spec.normalize)


    def test_unsatisfiable_compiler(self):
        self.set_pkg_dep('mpileaks', 'mpich%gcc')
        spec = Spec('mpileaks ^mpich%intel ^callpath ^dyninst ^libelf ^libdwarf')
        self.assertRaises(spack.spec.UnsatisfiableCompilerSpecError, spec.normalize)


    def test_unsatisfiable_compiler_version(self):
        self.set_pkg_dep('mpileaks', 'mpich%gcc@4.6')
        spec = Spec('mpileaks ^mpich%gcc@4.5 ^callpath ^dyninst ^libelf ^libdwarf')
        self.assertRaises(spack.spec.UnsatisfiableCompilerSpecError, spec.normalize)


    def test_unsatisfiable_architecture(self):
        self.set_pkg_dep('mpileaks', 'mpich=bgqos_0')
        spec = Spec('mpileaks ^mpich=sles_10_ppc64 ^callpath ^dyninst ^libelf ^libdwarf')
        self.assertRaises(spack.spec.UnsatisfiableArchitectureSpecError, spec.normalize)


    def test_invalid_dep(self):
        spec = Spec('libelf ^mpich')
        self.assertRaises(spack.spec.InvalidDependencyException, spec.normalize)

        spec = Spec('libelf ^libdwarf')
        self.assertRaises(spack.spec.InvalidDependencyException, spec.normalize)

        spec = Spec('mpich ^dyninst ^libelf')
        self.assertRaises(spack.spec.InvalidDependencyException, spec.normalize)


    def test_equal(self):
        # Different spec structures to test for equality
        flat = Spec('mpileaks ^callpath ^libelf ^libdwarf')

        flat_init = Spec(
            'mpileaks', Spec('callpath'), Spec('libdwarf'), Spec('libelf'))

        flip_flat = Spec(
            'mpileaks', Spec('libelf'), Spec('libdwarf'), Spec('callpath'))

        dag = Spec('mpileaks', Spec('callpath',
                                    Spec('libdwarf',
                                         Spec('libelf'))))

        flip_dag = Spec('mpileaks', Spec('callpath',
                                         Spec('libelf',
                                              Spec('libdwarf'))))

        # All these are equal to each other with regular ==
        specs = (flat, flat_init, flip_flat, dag, flip_dag)
        for lhs, rhs in zip(specs, specs):
            self.assertEqual(lhs, rhs)
            self.assertEqual(str(lhs), str(rhs))

        # Same DAGs constructed different ways are equal
        self.assertTrue(flat.eq_dag(flat_init))

        # order at same level does not matter -- (dep on same parent)
        self.assertTrue(flat.eq_dag(flip_flat))

        # DAGs should be unequal if nesting is different
        self.assertFalse(flat.eq_dag(dag))
        self.assertFalse(flat.eq_dag(flip_dag))
        self.assertFalse(flip_flat.eq_dag(dag))
        self.assertFalse(flip_flat.eq_dag(flip_dag))
        self.assertFalse(dag.eq_dag(flip_dag))


    def test_normalize_mpileaks(self):
        # Spec parsed in from a string
        spec = Spec('mpileaks ^mpich ^callpath ^dyninst ^libelf@1.8.11 ^libdwarf')

        # What that spec should look like after parsing
        expected_flat = Spec(
            'mpileaks', Spec('mpich'), Spec('callpath'), Spec('dyninst'),
            Spec('libelf@1.8.11'), Spec('libdwarf'))

        # What it should look like after normalization
        mpich = Spec('mpich')
        libelf = Spec('libelf@1.8.11')
        expected_normalized = Spec(
            'mpileaks',
            Spec('callpath',
                 Spec('dyninst',
                      Spec('libdwarf',
                           libelf),
                      libelf),
                 mpich),
            mpich)

        # Similar to normalized spec, but now with copies of the same
        # libelf node.  Normalization should result in a single unique
        # node for each package, so this is the wrong DAG.
        non_unique_nodes = Spec(
            'mpileaks',
            Spec('callpath',
                 Spec('dyninst',
                      Spec('libdwarf',
                           Spec('libelf@1.8.11')),
                      Spec('libelf@1.8.11')),
                 mpich),
            Spec('mpich'))

        # All specs here should be equal under regular equality
        specs = (spec, expected_flat, expected_normalized, non_unique_nodes)
        for lhs, rhs in zip(specs, specs):
            self.assertEqual(lhs, rhs)
            self.assertEqual(str(lhs), str(rhs))

        # Test that equal and equal_dag are doing the right thing
        self.assertEqual(spec, expected_flat)
        self.assertTrue(spec.eq_dag(expected_flat))

        # Normalized has different DAG structure, so NOT equal.
        self.assertNotEqual(spec, expected_normalized)
        self.assertFalse(spec.eq_dag(expected_normalized))

        # Again, different DAG structure so not equal.
        self.assertNotEqual(spec, non_unique_nodes)
        self.assertFalse(spec.eq_dag(non_unique_nodes))

        spec.normalize()

        # After normalizing, spec_dag_equal should match the normalized spec.
        self.assertNotEqual(spec, expected_flat)
        self.assertFalse(spec.eq_dag(expected_flat))

        self.assertEqual(spec, expected_normalized)
        self.assertTrue(spec.eq_dag(expected_normalized))

        self.assertEqual(spec, non_unique_nodes)
        self.assertFalse(spec.eq_dag(non_unique_nodes))


    def test_normalize_with_virtual_package(self):
        spec = Spec('mpileaks ^mpi ^libelf@1.8.11 ^libdwarf')
        spec.normalize()

        expected_normalized = Spec(
            'mpileaks',
            Spec('callpath',
                 Spec('dyninst',
                      Spec('libdwarf',
                           Spec('libelf@1.8.11')),
                      Spec('libelf@1.8.11')),
                 Spec('mpi')), Spec('mpi'))

        self.assertEqual(str(spec), str(expected_normalized))


    def test_contains(self):
        spec = Spec('mpileaks ^mpi ^libelf@1.8.11 ^libdwarf')
        self.assertTrue(Spec('mpi') in spec)
        self.assertTrue(Spec('libelf') in spec)
        self.assertTrue(Spec('libelf@1.8.11') in spec)
        self.assertFalse(Spec('libelf@1.8.12') in spec)
        self.assertTrue(Spec('libdwarf') in spec)
        self.assertFalse(Spec('libgoblin') in spec)
        self.assertTrue(Spec('mpileaks') in spec)


    def test_copy_simple(self):
        orig = Spec('mpileaks')
        copy = orig.copy()

        self.check_links(copy)

        self.assertEqual(orig, copy)
        self.assertTrue(orig.eq_dag(copy))
        self.assertEqual(orig._normal, copy._normal)
        self.assertEqual(orig._concrete, copy._concrete)

        # ensure no shared nodes bt/w orig and copy.
        orig_ids = set(id(s) for s in orig.traverse())
        copy_ids = set(id(s) for s in copy.traverse())
        self.assertFalse(orig_ids.intersection(copy_ids))


    def test_copy_normalized(self):
        orig = Spec('mpileaks')
        orig.normalize()
        copy = orig.copy()

        self.check_links(copy)

        self.assertEqual(orig, copy)
        self.assertTrue(orig.eq_dag(copy))
        self.assertEqual(orig._normal, copy._normal)
        self.assertEqual(orig._concrete, copy._concrete)

        # ensure no shared nodes bt/w orig and copy.
        orig_ids = set(id(s) for s in orig.traverse())
        copy_ids = set(id(s) for s in copy.traverse())
        self.assertFalse(orig_ids.intersection(copy_ids))


    def test_copy_concretized(self):
        orig = Spec('mpileaks')
        orig.concretize()
        copy = orig.copy()

        self.check_links(copy)

        self.assertEqual(orig, copy)
        self.assertTrue(orig.eq_dag(copy))
        self.assertEqual(orig._normal, copy._normal)
        self.assertEqual(orig._concrete, copy._concrete)

        # ensure no shared nodes bt/w orig and copy.
        orig_ids = set(id(s) for s in orig.traverse())
        copy_ids = set(id(s) for s in copy.traverse())
        self.assertFalse(orig_ids.intersection(copy_ids))

import functools
import os
import random
import unittest
import attrdict
import numpy as np
from sqsgenerator.compat import have_mpi_support
from sqsgenerator.core import default_shell_distances
from sqsgenerator.adapters import to_ase_atoms, to_pymatgen_structure
from sqsgenerator.io import read_settings_file
from sqsgenerator.settings.readers import read_atol, \
    read_rtol, \
    read_mode, \
    read_structure, \
    read_iterations, \
    read_composition, \
    read_pair_weights, \
    read_shell_weights, \
    read_shell_distances, \
    read_target_objective, \
    read_threads_per_rank, \
    read_max_output_configurations, \
    BadSettings, ATOL, RTOL, IterationMode, Structure


def settings(recursive=True, **kwargs):
    return attrdict.AttrDict({**kwargs}, recursive=recursive)


def test_function(test_f):

    def test_f_wrapper(**kwargs):
        return test_f(settings(**kwargs))

    def _decorator(f):

        def _inner(self):
            return f(self, test_f_wrapper)

        return _inner

    return _decorator


class TestSettingReaders(unittest.TestCase):

    def setUp(self) -> None:
        self.raw_dict = read_settings_file('examples/cs-cl.sqs.yaml')
        self.raw_dict_from_file = read_settings_file('examples/cs-cl.poscar.sqs.yaml')
        self.file_name = self.raw_dict_from_file.structure.file
        self.structure = read_structure(self.raw_dict)
        self.distances = default_shell_distances(self.structure, ATOL, RTOL)

    def assertStructureEquals(self, s1: Structure, s2: Structure, prec=3):
        self.assertEqual(s1.num_unique_species, s2.num_unique_species)
        self.assertTrue(np.allclose(s1.numbers, s2.numbers))
        coords_close = np.allclose(np.round(s1.frac_coords, prec), np.round(s2.frac_coords, prec))
        self.assertTrue(coords_close)

    @test_function(read_atol)
    def test_read_atol(self, f):
        self.assertAlmostEqual(f(), ATOL)
        self.assertAlmostEqual(f(atol=1.5), 1.5)
        with self.assertRaises(BadSettings):
            f(atol=-1)
        with self.assertRaises(BadSettings):
            f(atol="adsfasdf")

    @test_function(read_rtol)
    def test_read_rtol(self, f):
        self.assertAlmostEqual(f(), RTOL)
        self.assertAlmostEqual(f(rtol=1.5), 1.5)
        with self.assertRaises(BadSettings):
            f(rtol=-1)

    @test_function(read_mode)
    def test_read_mode(self, f):
        for mode, obj in IterationMode.names.items():
            self.assertEqual(f(mode=mode), obj)
            self.assertEqual(f(mode=obj), obj)

        with self.assertRaises(BadSettings):
            f(mode='atol')

        self.assertEqual(f(), IterationMode.random)

    @test_function(read_iterations)
    def test_read_iterations(self, f):

        self.assertEqual(f(mode=IterationMode.random), 1e5)
        self.assertEqual(f(mode=IterationMode.systematic), -1)

        num_iterations = random.randint(1000, 10000)
        self.assertEqual(f(mode=IterationMode.systematic, iterations=num_iterations), num_iterations)
        self.assertEqual(f(mode=IterationMode.random, iterations=num_iterations), num_iterations)

        with self.assertRaises(BadSettings):
            # raise a TypeError in convert
            f(iterations=())

        with self.assertRaises(BadSettings):
            # raise a ValueError in convert
            f(iterations="adsfasdf")

        with self.assertRaises(BadSettings):
            # raise a TypeError in convert
            f(iterations=-23)

    @test_function(read_max_output_configurations)
    def test_read_max_output_configurations(self, f):

        self.assertEqual(f(), 10)
        self.assertEqual(f(max_output_configurations=1000), 1000)
        self.assertEqual(f(max_output_configurations=1e3), 1000)

        with self.assertRaises(BadSettings):
            # raise a TypeError in convert
            f(max_output_configurations=())

        with self.assertRaises(BadSettings):
            # raise a ValueError in convert
            f(max_output_configurations="adsfasdf")

        with self.assertRaises(BadSettings):
            # raise a TypeError in convert
            f(max_output_configurations=-23)

    @test_function(read_structure)
    def test_read_structure(self, f):
        self.assertStructureEquals(f(structure=self.structure), self.structure)
        self.assertStructureEquals(f(structure=self.structure), self.structure)
        self.assertStructureEquals(f(**self.raw_dict_from_file), self.structure)
        self.assertStructureEquals(f(structure=to_ase_atoms(self.structure)), self.structure)
        self.assertStructureEquals(f(structure=to_pymatgen_structure(self.structure)), self.structure)
        with self.assertRaises(BadSettings):
            f()
        with self.assertRaises(BadSettings):
            f(structure={'A': 1})

    @test_function(read_composition)
    def test_read_composition(self, f):

        with self.assertRaises(BadSettings):
            # raise a TypeError in convert
            f(structure=self.structure, composition={})

        with self.assertRaises(BadSettings):
            # raise a wrong number of total atoms
            f(structure=self.structure, composition=dict(Fr=18, Lu=18))

        with self.assertRaises(BadSettings):
            # correct number but less than one
            f(structure=self.structure, composition=dict(Fr=54, Lu=0))

        with self.assertRaises(BadSettings):
            # correct number but negative number
            f(structure=self.structure, composition=dict(Fr=55, Lu=-1))

        with self.assertRaises(BadSettings):
            # wrong species
            f(structure=self.structure, composition=dict(Fr=27, Kf=27))

        with self.assertRaises(BadSettings):
            # type error in atom number
            f(structure=self.structure, composition=dict(Fr=27, Na='asdf'))

        with self.assertRaises(BadSettings):
            # wrong number of atoms on sublattice
            f(structure=self.structure, composition=dict(Fr=27, Kf=27, which='Cs'))

        with self.assertRaises(BadSettings):
            # non existing sublattice
            f(structure=self.structure, composition=dict(Fr=14, K=13, which='Na'))

        with self.assertRaises(BadSettings):
            # wrong type in sublattice specification
            f(structure=self.structure, composition=dict(Fr=27, Na=27, which=345345))

        with self.assertRaises(BadSettings):
            # index out of bounds in sublattice specification
            f(structure=self.structure, composition=dict(Fr=2, Na=2, which=(0,1,2,4, self.structure.num_atoms+4)))

        with self.assertRaises(BadSettings):
            # index out of bounds in sublattice specification
            f(structure=self.structure, composition=dict(Fr=2, Na=2, which=(0, 1, 2, 4, 'g')))

        with self.assertRaises(BadSettings):
            # too few atoms on sublattice
            f(structure=self.structure, composition=dict(Fr=0, Na=1, which=(0,)))

        with self.assertRaises(BadSettings):
            # wrong number of atoms on sublattice
            f(structure=self.structure, composition=dict(Fr=27, Kf=27, which='all'))

        s = settings(structure=self.structure, composition=dict(Cs=27, Cl=27, which='all'))
        read_composition(s)
        self.assertTrue('is_sublattice' in s)
        self.assertFalse(s.is_sublattice)

        sublattice = 'Cs'
        s = settings(structure=self.structure, composition=dict(H=13, He=14, which=sublattice))
        read_composition(s)
        self.assertTrue('is_sublattice' in s)
        self.assertTrue(s.is_sublattice)

        sublattice = [0,2,4,5,6,7,8,9]
        s = settings(structure=self.structure, composition=dict(H=4, He=4, which=sublattice))
        read_composition(s)
        self.assertTrue('is_sublattice' in s)
        self.assertTrue(s.is_sublattice)

    @test_function(read_shell_distances)
    def test_read_shell_distances(self, f):
        atol = read_atol(settings())
        rtol = read_rtol(settings())
        distances = f(structure=self.structure, atol=atol, rtol=rtol)
        np.testing.assert_array_almost_equal(distances, default_shell_distances(self.structure, atol, rtol))

        with self.assertRaises(BadSettings):
            f(shell_distances=[0, -1, 2, 3, 4])

        with self.assertRaises(BadSettings):
            f(shell_distances="Wrong type")

        with self.assertRaises(BadSettings):
            f(shell_distances=[0, 1, 2, 3, complex(1, 2)])

        with self.assertRaises(BadSettings):
            f(shell_distances=[])

        with self.assertRaises(BadSettings):
            f(shell_distances=[0.0]*2)

        custom_distances = [0, 1, 2, 4, 5]
        np.testing.assert_array_almost_equal(custom_distances, f(shell_distances=custom_distances))

        custom_distances = [1, 2, 4, 5]
        np.testing.assert_array_almost_equal([0.0]+custom_distances, f(shell_distances=custom_distances))

    @test_function(read_shell_weights)
    def test_read_shell_weights(self, f):
        atol = read_atol(settings())
        rtol = read_rtol(settings())
        distances = read_shell_distances(settings(structure=self.structure, atol=atol, rtol=rtol))
        ff = functools.partial(f, shell_distances=distances)
        weights = f(shell_distances=distances)
        for i, w in weights.items():
            self.assertAlmostEqual(w, 1.0/i)
        self.assertEqual(len(weights)+1, len(distances))

        with self.assertRaises(BadSettings):
            ff(shell_weights={len(distances)+1: 1.0})

        with self.assertRaises(BadSettings):
            ff(shell_weights={-1: 1.0})

        with self.assertRaises(BadSettings):
            ff(shell_weights={})

        with self.assertRaises(BadSettings):
            ff(shell_weights=[1.0])

        shells = {1: 1.0}
        validated = ff(shell_weights=shells)
        self.assertEqual(shells, validated)

    @test_function(read_pair_weights)
    def test_read_pair_weights(self, f):
        ff = functools.partial(f, structure=self.structure)
        ns = self.structure.num_unique_species

        default_value = (~np.eye(self.structure.num_unique_species, dtype=bool)).astype(int)
        np.testing.assert_array_almost_equal(f(structure=self.structure), default_value)

        np.testing.assert_array_almost_equal(np.eye(ns), ff(pair_weights=np.eye(ns)))

        with self.assertRaises(BadSettings):
            ff(pair_weights=np.eye(ns + 1))

        with self.assertRaises(BadSettings):
            ff(pair_weights="string")

        with self.assertRaises(BadSettings):
            ff(pair_weights=np.arange(ns*ns).reshape((ns, ns)))

    @test_function(read_target_objective)
    def test_read_test_target_objective(self, f):
        ff = functools.partial(f, structure=self.structure, shell_distances=self.distances)
        default_sw = read_shell_weights(settings(structure=self.structure, atol=ATOL, rtol=RTOL, shell_distances=self.distances))
        ns = self.structure.num_unique_species

        def shape(sw : dict = default_sw): return (len(sw), ns, ns)

        max_num_shells = len(default_sw)
        for nshells in range(1, max_num_shells+1):
            sw = {i: 1.0/i for i in range(1, nshells+1)}
            self.assertEqual(ff(shell_weights=sw).shape, shape(sw))

            targets = ff(shell_weights=sw, target_objective=nshells)
            self.assertEqual(targets.shape, shape(sw))
            for shell, w in sw.items():
                actual = targets[shell-1, :, :]
                should_be = np.ones_like(actual) * w * nshells
                np.testing.assert_array_almost_equal(actual, should_be)

        fff = functools.partial(ff, shell_weights=default_sw)
        with self.assertRaises(BadSettings):
            fff(target_objective="sadf")

        with self.assertRaises(BadSettings):
            fff(target_objective=np.arange(10))

        with self.assertRaises(BadSettings):
            fff(target_objective=np.ones((2,2,2,2)))

        # test 3D array
        all_ones = np.ones(shape())
        np.testing.assert_array_almost_equal(all_ones, fff(target_objective=all_ones))

        with self.assertRaises(BadSettings):
            # test non symmetric sub-arrays
            fff(target_objective=np.arange(np.prod(shape())).reshape(shape()))

        with self.assertRaises(BadSettings):
            fff(target_objective=np.zeros((2, ns+1, ns)))

        # test 2D arrays
        all_ones = np.ones((ns, ns))
        target_objective = fff(target_objective=all_ones)
        for shell in sorted(default_sw):
            np.testing.assert_array_almost_equal(target_objective[shell-1], np.ones_like(all_ones)*default_sw[shell])

        with self.assertRaises(BadSettings):
            # non-symmetric input
            fff(target_objective=np.arange(ns * ns).reshape((ns, ns)))

        with self.assertRaises(BadSettings):
            fff(target_objective=np.ones((ns+1, ns)))

    @test_function(read_threads_per_rank)
    def test_read_threads_per_rank(self, f):
        default = [-1]
        self.assertEqual(f(), default)

        if not have_mpi_support():
            with self.assertRaises(BadSettings):
                f(threads_per_rank=(1,2,4))

        import multiprocessing
        for i in range(1, multiprocessing.cpu_count()+1):
            self.assertEqual(f(threads_per_rank=i), [i])
            self.assertEqual(f(threads_per_rank=float(i)), [i])
            self.assertEqual(f(threads_per_rank=(i)), [i])
            self.assertEqual(f(threads_per_rank=(float(i))), [i])



if __name__ == '__main__':
    unittest.main()
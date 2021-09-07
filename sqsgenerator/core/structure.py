import numbers
import itertools
import numpy as np
import typing as T
from operator import attrgetter as attr
from sqsgenerator.core.core import Structure as Structure_, Atom


class Structure(Structure_):
    """
    Structure class used to store structural information. This class is used by the core extension and is a wrapper
    around the extension internal ``sqsgenerator.core.core.Structure`` class. The class is desinged to be array like,
    therefore it does not provide any setter functions.
    """

    def __init__(self, lattice: np.ndarray, frac_coords: np.ndarray, symbols: T.List[str], pbc: T.Tuple[bool, bool, bool]=(True, True, True)):
        super(Structure, self).__init__(lattice, frac_coords, symbols, pbc)
        self._symbols = np.array(list(map(attr('symbol'), self.species)))
        self._numbers = np.fromiter(map(attr('Z'), self.species), dtype=int, count=self.num_atoms)
        self._unique_species = set(np.unique(self._symbols))

    @property
    def symbols(self) -> np.ndarray:
        """
        A ``numpy.ndarray`` storing the symbols of the atomic species. E.g "*Fe*", "*Cr*", "*Ni*"

        :return: the array of symbols
        :rtype: numpy.ndarray
        """
        return self._symbols

    @property
    def numbers(self) -> np.ndarray:
        """
        The ordinal numbers of the atoms sitting on the lattice positions

        :return: array of ordinal numbers
        :rtype: numpy.ndarray
        """
        return self._numbers

    @property
    def num_unique_species(self) -> int:
        """
        The number of unique elements in the structure object

        :return: the number of elements
        :rtype: int
        """
        return len(self._unique_species)

    @property
    def unique_species(self) -> T.Set[str]:
        """
        A set of symbols of the occurring species

        :return: a set containing the symbol of the occurring species
        :rtype: set or str
        """
        return self._unique_species

    def __len__(self):
        return self.num_atoms

    def __repr__(self):
        def group_symbols():
            for species, same in itertools.groupby(self._symbols):
                num_same = len(list(same))
                yield species if num_same == 1 else f'{species}{num_same}'

        formula = ''.join(group_symbols())
        return f'Structure({formula}, len={self.num_atoms})'

    def sorted(self):
        """
        Creates a new structure, where the lattice positions are ordered by the ordinal numbers of the occupying species

        :return: the sorted Structure
        :rtype: Structure
        """
        return self[np.argsort(self._numbers)]

    def __getitem__(self, item):
        if isinstance(item, numbers.Integral):
            if item < -self.num_atoms or item >= self.num_atoms:
                raise IndexError('Index out of range.')
            return self.species[item]

        if isinstance(item, (list, tuple, np.ndarray)):
            indices = np.array(item)
            if indices.dtype == bool:
                indices = np.argwhere(indices).flatten()
            elif indices.dtype != int:
                raise TypeError('Only integer numbers cann be used for slicing')
             # boolean mask slice
        elif isinstance(item, slice):
            indices = np.arange(self.num_atoms)[item]
        else:
            raise TypeError(f'Structure indices must not be of type {type(item)}')
        return Structure(self.lattice, self.frac_coords[indices], self.symbols[indices])

    def to_dict(self) -> dict:
        """
        Serializes the object into JSON/YAML serializable dictionary

        :return: the JSON/YAML serializable dictionary
        :rtype: dict
        """
        return structure_to_dict(self)

    def slice_with_species(self, species: T.Iterable[str], which: T.Optional[T.Iterable[int]]=None):
        """
        Creates a new structure containing the lattice positions specified by {which}. The new structure
        is occupied by the atomic elements specified in {species}. In case {which} is ``None`` all lattice positions
        are assumed to be occupied with a new {species}. The new structure will only contain lattice positions specified
        in {which}.

        :param species: the atomic species specified by their symbols
        :type species: iterable of str
        :param which: the indices of the lattice positions to choose (default is ``None``)
        :type which: iterable of int or ``None``
        :return: the (subset) Structure with new species
        :rtype: structure
        :raises ValueError: if length of which is < 1 or length of {which} and {species} does not match
        """
        which = which or tuple(range)
        return self.with_species(species, which=which)[which]

    def with_species(self, species, which=None):
        """
        Creates a new structure containing the lattice positions specified by {which}. The new structure
        is occupied by the atomic elements specified in {species}. In case {which} is ``None`` all lattice positions
        are assumed to be occupied with a new {species}. The new structure will only all lattice positions of the
        current structure, while on the positions specified by {which} are occipied with {species}.

        :param species: the atomic species specified by their symbols
        :type species: iterable of str
        :param which: the indices of the lattice positions to choose (default is ``None``)
        :type which: iterable of int or ``None``
        :return: the (subset) Structure with new species
        :rtype: structure
        :raises ValueError: if length of which is < 1 or length of {which} and {species} does not match
        """
        which = which or tuple(range)
        species = list(species)
        if len(species) < 1:
            raise ValueError('Cannot create an empty structure')
        if len(which) != len(species):
            raise ValueError('Number of species does not match the number of specified atoms')
        new_symbols = self.symbols.copy()
        new_symbols[np.array(which)] = species
        return Structure(self.lattice, self.frac_coords, new_symbols.tolist())


def structure_to_dict(structure: Structure):
    return dict(
        lattice=structure.lattice.tolist(),
        coords=structure.frac_coords.tolist(),
        species=structure.symbols.tolist()
    )


def make_supercell(structure: Structure, sa: int = 1, sb: int = 1, sc : int = 1) -> Structure:
    """
    Creates a supercell of structure, which is repeated {sa}, {sb} and {sc} times

    :param structure: the structure to replicate
    :type structure: Structure
    :param sa: number of repetitions in directions of the first lattice vector (default is ``1``)
    :type sa: int
    :param sb: number of repetitions in directions of the second lattice vector (default is ``1``)
    :type sb: int
    :param sc: number of repetitions in directions of the third lattice vector (default is ``1``)
    :type sc: int
    :return: the supercell structure
    :rtype: Structure
    """
    sizes = (sa, sb, sc)
    num_cells = np.prod(sizes)
    num_atoms_supercell = structure.num_atoms * num_cells
    scale = np.diag(sizes).astype(float)
    iscale = np.linalg.inv(scale)
    supercell_lattice = scale @ structure.lattice

    scaled_fc = structure.frac_coords @ iscale.T

    def make_translation_vector(a, b, c):
        return np.tile(np.array([a, b, c]) @ iscale, [structure.num_atoms, 1])

    supercell_coords = np.vstack([
        scaled_fc + make_translation_vector(*shift)
        for shift in itertools.product(*map(range, sizes))
    ])

    supercell_species = np.tile(structure.symbols, num_cells).tolist()

    assert supercell_coords.shape == (num_atoms_supercell, 3)
    assert len(supercell_species) == num_atoms_supercell
    structure_supercell = Structure(supercell_lattice, supercell_coords, supercell_species, (True, True, True))
    return structure_supercell
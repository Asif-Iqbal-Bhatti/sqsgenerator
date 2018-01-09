from .utils import write_message, full_name, ERROR, WARNING, parse_separated_string, isclose, parse_float, all_subclasses
from pymatgen.core.periodic_table import Element
from os.path import exists, isfile, basename


def parse_options(docopt_options):
    options = {}
    exceptions = [CompositionalArgument]
    parsers = {subcls(docopt_options).format_key(): subcls(docopt_options) for subcls in all_subclasses(ArgumentBase) if subcls not in exceptions}
    for key in docopt_options.keys():
        if key.startswith('--') or (key.startswith('<') and key.endswith('>')):
            if docopt_options[key] is None:
                continue
            if key not in parsers:
                write_message('No suitable parser found for argument {0}'.format(key), exit=True)
            options[parsers[key].key] = parsers[key]()
        else:
            options[key] = docopt_options[key]
    return options


class Singleton(object):
    # the one, true Singleton
  __single = None

  def __new__(classtype, *args, **kwargs):
    # Check to see if a __single exists already for this class
    # Compare class types instead of just looking for None so
    # that subclasses will create their own __single objects
    if classtype != type(classtype.__single):
        classtype.__single = object.__new__(classtype)
        classtype.__single.__init__(*args, **kwargs)
    return classtype.__single

class InvalidOption(Exception):

    """
    Arguments vor options are invalid
    """


class ArgumentBase(Singleton):

    def __init__(self, options, key, option=False):
        self._options = options
        self._key = key
        self._parsed = False
        self._result = None
        self._option = option

    @property
    def key(self):
        return self._key

    def format_key(self):
        return ('--{key}' if self._option else '<{key}>').format(key=self._key)

    @property
    def raw_value(self):
        return self._options[self.format_key()]

    def parse(self, options, *args, **kwargs):
        return options[self.format_key()]

    def __call__(self, *args, **kwargs):
        if not self._parsed:
            try:
                self._result = self.parse(self._options, args, kwargs)
            except InvalidOption:
                write_message('{name}: Failed to parse "{arg}" for '+'argument' if not self._option else 'option' +' "{option}"'.format(name=full_name(self), option=self.key, arg=self.raw_value, exit=True))
            else:
                self._parsed = True
        return self._result

    def write_message(self, message, level=ERROR, exit=False):
        write_message('{name}: {message}'.format(name=full_name(self), message=message), level=level, exit=exit)


class CompositionalArgument(ArgumentBase):

    def __init__(self, options, key, option=False):
        super(CompositionalArgument, self).__init__(options, key, option=option)

    def parse_composition(self, composition, species, atoms):
        try:
            composition = parse_separated_string(composition)
            mole_fractions = {}
            dummy_z = 1
            dummy_species = []
            for species_comp in composition:
                try:
                    _species, mole_fraction = species_comp.split(':')
                except ValueError:
                    if ':' not in species_comp:
                        if species_comp == '0':
                            _species = species_comp
                        elif not Element.is_valid_symbol(species_comp):
                            _species = Element.from_Z(dummy_z).symbol
                            dummy_species.append(_species)
                            dummy_z += 1
                            mole_fraction = species_comp
                        else:
                            continue

                try:
                    mole_fraction = int(mole_fraction)
                    mole_fraction = float(mole_fraction) / atoms
                except ValueError:
                    try:
                        mole_fraction = float(mole_fraction)
                    except ValueError:
                        self.write_message(
                            'Could not parse {0} in composition string. Resuming with 0.0'.format(mole_fraction))
                        raise InvalidOption

                if _species == '0' and '0' not in species:
                    species.append('0')

                # if _species not in species and _species != '0':
                #    write_message('Species "{0}" is not defined in POSCAR file'.format(_species))

                if mole_fraction:
                    mole_fractions[_species] = mole_fraction
            missing_species = [specie for specie in species if specie not in mole_fractions.keys()]
            if sum(mole_fractions.values()) > 1.0:
                self.write_message('The mole fractions specified exceed 1. {0}'.format(mole_fractions))
                raise InvalidOption
            if len(missing_species) > 1:
                self.write_message('You did not specify enough species. I\'m missing {0}!'.format(missing_species))
                raise InvalidOption
            elif len(missing_species) == 1:
                missing_species = missing_species[0]
                mole_fractions[missing_species] = (1.0 - sum(mole_fractions.values()))
            elif len(missing_species) == 0:
                if not isclose(sum(mole_fractions.values()), 1.0):
                    if '0' not in mole_fractions:
                        self.write_message(
                            "The mole fractions you specified do not. Resuming by filling the missing percentage with vacancies in composition definition {0}".format(
                                composition), level=WARNING)
                        mole_fractions['0'] = (1 - sum(mole_fractions.values()))
                    else:
                        self.write_message('Your composition does not sum up to 1')
                        raise InvalidOption
            else:
                self.write_message(
                    'The amount of specified mole fractions does not match the species specified. Expected list of length {0} or {1}'.format(
                        len(species), len(species) - 1))
                raise InvalidOption
            if len(dummy_species) > 0:
                self.write_message('Missing elements resuming with {0} for undefined elements'.format(dummy_species),
                              level=WARNING)
            return mole_fractions
        except:
            write_message('Could not parse composition')


    def parse(self, options, *args, **kwargs):
        raise NotImplementedError


class LatticeOption(CompositionalArgument):

    def __init__(self, options):
        super(LatticeOption, self).__init__(options, 'lattice', option=True)

    def parse(self, options, *args, **kwargs):
        structure = StructureFileArgument(options)()
        species = list(set([element.symbol for element in structure.species]))
        sublattice_composition = {}
        sublattice_mapping = self.raw_value
        for mapping in sublattice_mapping:
            try:
                sublattice, composition = mapping.split('=')
            except:
                self.write_message('Could not parse sublattice definition "{0}"'.format(mapping))
                raise InvalidOption
            sublattice_species = []
            dummy_z = 1
            for sublattice_composition_string in parse_separated_string(composition):

                try:
                    _species, mole_fraction = sublattice_composition_string.split(':')
                except ValueError:
                    if Element.is_valid_symbol(
                            sublattice_composition_string) or sublattice_composition_string.startswith(
                            '0'):
                        _species = sublattice_composition_string
                    else:
                        _species = Element.from_Z(dummy_z).symbol
                        dummy_z += 1
                sublattice_species.append(_species)

            for _species in sublattice_species:
                if not Element.is_valid_symbol(_species) and not _species == '0':
                    self.write_message(
                        'Element "{0}" is not a valid symbol in the periodic table. To get a list of all symbols you may have a look at pymatgen.core.periodic_table'.format(
                            _species))
                    raise InvalidOption

            if sublattice == '0':
                self.write_message('Vacancies cannot be specified as sublattice'.format(sublattice))
                raise InvalidOption
            elif sublattice not in species:
                self.write_message('"{0}" is not a specified species'.format(sublattice))
                raise InvalidOption
            if len(sublattice_species) == 0:
                self.write_message(
                    'You must specify which species should be placed on the {0} sublattice'.format(sublattice))
                raise InvalidOption
            sublattice_composition[sublattice] = \
                self.parse_composition(composition, sublattice_species,
                                  atoms=self.get_atom_number_on_sublattice(sublattice, structure))

        return sublattice_composition

    def get_atom_number_on_sublattice(self, species, structure):
        return len(list(filter(lambda site: site.specie.symbol == species, structure.sites)))


class WeightsOption(ArgumentBase):

    def __init__(self, options):
        super(WeightsOption, self).__init__(options, key='weights', option=True)

    def parse(self, options, *args, **kwargs):
        try:
            weight_values = list(map(lambda str_: parse_float(str_, except_val=0, raise_exc=True),
                                     parse_separated_string(options[self.format_key()])))

            weights = dict(zip(range(1, len(weight_values) + 1), weight_values))
        except ValueError:
            self.write_message('An error occurred while parsing weights. Exiting!\n')
            raise InvalidOption
        else:
            return weights


class ObjectiveOption(ArgumentBase):

    def __init__(self, options):
        super(ObjectiveOption, self).__init__(options, key='objective', option=True)

    def parse(self, options, *args, **kwargs):
        if self.raw_value.lower().startswith('i'):
            objective_value = float('inf')
        elif self.raw_value.lower().startswith('-i'):
            objective_value = float('-inf')
        else:
            try:
                objective_value = float(options[self.format_key()].lower())
            except ValueError:
                self.write_message('Cannot parse objective function value: "{0}" . Exiting!\n'.format(options[self.format_key()]))
                raise InvalidOption
        return objective_value


class AnisotropyOption(ArgumentBase):

    def __init__(self, options):
        super(AnisotropyOption, self).__init__(options, key='anisotropy', option=True)

    def parse(self, options, *args, **kwargs):
        try:
            anisotropy_values = list(map(lambda str_: parse_float(str_, except_val=0, raise_exc=True),
                                         parse_separated_string(self.raw_value)))
            if len(anisotropy_values) not in (1, 2, 4):
                self.write_message("Only 1, 2 or 4 values can be specified for the directional weighting. "
                              "Use the -h switch for help")
                raise InvalidOption

            main_sum_weight = anisotropy_values[0]
            if len(anisotropy_values) == 1:
                anisotropy_weights = [1.0] * 3 if main_sum_weight >= 1.0 else [(1 - main_sum_weight) / 3] * 3
            else:
                anisotropy_weights = anisotropy_values[1:]
        except ValueError:
            self.write_message('An error occurred while parsing anisotropy weights. Exiting!\n')
            raise InvalidOption
        else:
            return main_sum_weight, anisotropy_weights


class ParallelOption(ArgumentBase):

    def __init__(self, options):
        super(ParallelOption, self).__init__(options, key='parallel', option=True)


class DivergentOption(ArgumentBase):

    def __init__(self, options):
        super(DivergentOption, self).__init__(options, key='divergent', option=True)


class VerbosityOption(ArgumentBase):

    def __init__(self, options):
        super(VerbosityOption, self).__init__(options, key='verbosity', option=True)

    def parse(self, options, *args, **kwargs):
        try:
            verbosity = int(parse_float(self.raw_value, raise_exc=True))
        except ValueError:
            self.write_message('Could not parse verbosity level')
            raise InvalidOption
        else:
            return verbosity


class VacancyOption(ArgumentBase):

    def __init__(self, options):
        super(VacancyOption, self).__init__(options, key='vacancy', option=True)

    def parse(self, options, *args, **kwargs):
        # The vacancy switch
        try:
            mole_fraction_vacancy = abs(parse_float(self.raw_value, raise_exc=True))
        except:
            self.write_message('Could not parse vacancy definition')
            raise InvalidOption
        else:
            return mole_fraction_vacancy


class IterationsOption(ArgumentBase):

    def __init__(self, options):
        super(IterationsOption, self).__init__(options, key='iterations', option=True)

    def parse(self, options, *args, **kwargs):
        try:
            iterations = int(parse_float(self.raw_value, raise_exc=True))
        except ValueError:
            if self.raw_value.lower() == 'all':
                return self.raw_value
            else:
                self.write_message('Could not parse iteration number')
                raise InvalidOption
        else:
            return iterations


class OutputOption(ArgumentBase):

    def __init__(self, options):
        super(OutputOption, self).__init__(options, key='output', option=True)

    def parse(self, options, *args, **kwargs):
        try:
            output = int(parse_float(self.raw_value, raise_exc=True))
        except ValueError:
            if self.raw_value.lower() == 'all':
                return self.raw_value
            else:
                self.write_message('Could not output structure number')
                raise InvalidOption
        else:
            return output


class HelpOption(ArgumentBase):

    def __init__(self, options):
        super(HelpOption, self).__init__(options, key='help', option=True)

    def parse(self, options, *args, **kwargs):
        import sqsgenerator.cli
        return sqsgenerator.cli.__doc__


class VersionOption(ArgumentBase):

    def __init__(self, options):
        super(VersionOption, self).__init__(options, key='version', option=True)

    def parse(self, options, *args, **kwargs):
        from sqsgenerator.cli import __VERSION__
        return __VERSION__


class StructureFileArgument(ArgumentBase):

    def __init__(self, options):
        super(StructureFileArgument, self).__init__(options, key='structure')

    def parse(self, options, *args, **kwargs):
        path = self.raw_value
        if exists(path):
            if isfile(path):
                filename = basename(path)
                if filename.lower().endswith('.cif'):
                    from pymatgen.io.cif import CifParser
                    try:
                        result = CifParser(path).get_structures()[0]
                    except:
                        self.write_message('Could not parse CIF file: "{0}"'.format(path))
                        raise InvalidOption
                elif filename.lower().endswith('.cssr'):
                    from pymatgen.io.cssr import Cssr
                    try:
                        result = Cssr.from_file(path).structure
                    except:
                        self.write_message('Could not parse CSSR file: "{0}"'.format(path))
                        raise InvalidOption
                elif filename.lower().endswith('.xml'):
                    from pymatgen.io.exciting import ExcitingInput
                    try:
                        result = ExcitingInput.from_file(path).structure
                    except:
                        self.write_message('Could not parse Exciting input file: "{0}"'.format(path))
                        raise InvalidOption
                else:
                    from pymatgen.io.vasp import Poscar
                    try:
                        result = Poscar.from_file(path).structure
                    except:
                        self.write_message('Could not parse POSCAR file "{0}"'.format(path))
                        raise InvalidOption
                if not 'result' in locals():
                    write_message('File format not supported')
                    raise InvalidOption
                else:
                    return result
            else:
                self.write_message('"{0}" is a directory!'.format(path))
                raise InvalidOption
        else:
            self.write_message('Cannot locate file "{0}"'.format(path))
            raise InvalidOption


class CompositionArgument(CompositionalArgument):

    def __init__(self, options):
        super(CompositionArgument, self).__init__(options, key='composition')

    def parse(self, options, *args, **kwargs):
        structure = StructureFileArgument(options)()
        species = list(set([element.symbol for element in structure.species]))
        # Parse the given composition
        mole_fractions = self.parse_composition(self.raw_value, species, len(structure.sites))
        vacancy_parser = VacancyOption(options)
        if vacancy_parser.format_key() in options and options[vacancy_parser.format_key()]:
            mole_fraction_vacancy = vacancy_parser()
            # Check if given value is sensible
            if isclose(mole_fraction_vacancy, 1.0) or 0.0 >= mole_fraction_vacancy > 1.0:
                self.write_message('Vacancy mole fraction cannot be 1 or greater or less or equal to 0')
                raise InvalidOption
            # Vacancy species already specified by -S --species switch
            if '0' in mole_fractions:
                mole_fractions['0'] = 0.0
                # Correction factor for the other mole fractions
                correction_factor = 1 / sum(mole_fractions.values())
                # Correct other mole fractions
                for _species, mole_fraction in mole_fractions.items():
                    mole_fractions[_species] = mole_fraction * correction_factor

            correction_factor = (1.0 - mole_fraction_vacancy) / sum(mole_fractions.values())
            for _species, mole_fraction in mole_fractions.items():
                mole_fractions[_species] = mole_fraction * correction_factor
            mole_fractions['0'] = mole_fraction_vacancy
        return mole_fractions


class SupercellXArgument(ArgumentBase):

    def __init__(self, options):
        super(SupercellXArgument, self).__init__(options, key='supercellx')

    def parse(self, options, *args, **kwargs):
        try:
            supercell_x = int(parse_float(self.raw_value, raise_exc=True))
        except ValueError:
            self.write_message('Could not parse supercell scale factor')
            raise InvalidOption
        else:
            return supercell_x


class SupercellYArgument(ArgumentBase):

    def __init__(self, options):
        super(SupercellYArgument, self).__init__(options, key='supercelly')

    def parse(self, options, *args, **kwargs):
        try:
            supercell_y = int(parse_float(self.raw_value, raise_exc=True))
        except ValueError:
            self.write_message('Could not parse supercell scale factor')
            raise InvalidOption
        else:
            return supercell_y


class SupercellZArgument(ArgumentBase):

    def __init__(self, options):
        super(SupercellZArgument, self).__init__(options, key='supercellz')

    def parse(self, options, *args, **kwargs):
        try:
            supercell_z = int(parse_float(self.raw_value, raise_exc=True))
        except ValueError:
            self.write_message('Could not parse supercell scale factor')
            raise InvalidOption
        else:
            return supercell_z
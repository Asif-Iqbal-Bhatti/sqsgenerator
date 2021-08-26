import itertools
import os
import click
import tabulate
import attrdict
import functools
import numpy as np
import typing as T
from sqsgenerator.compat import Feature as F
from sqsgenerator.settings import construct_settings
from sqsgenerator.settings.readers import read_structure, process_settings
from sqsgenerator.io import supported_formats, to_dict, dumps, compression_to_file_extension, export_structures
from sqsgenerator.commands.common import click_settings_file, error, pretty_print
from sqsgenerator.core import pair_sqs_iteration, set_core_log_level, log_levels, symbols_from_z, SQSResult, Structure, pair_analysis, available_species
from operator import attrgetter as attr, itemgetter as item

TimingDictionary = T.Dict[int, T.List[float]]
Settings = attrdict.AttrDict

species_to_ordinal = dict(map(attr('symbol', 'Z'), available_species()))


def nditer(A: np.ndarray):
    return itertools.product(map(range, A.shape))


def transpose(l: list): return list(zip(*l))


def add_col(l: list, col: list):
    cols = transpose(l)
    cols.insert(0, col)
    return transpose(cols)


def add_row(l: list, row: list):
    l.insert(0, row)
    return l


def format_parameters(settings: Settings, result: SQSResult, tablefmt='fancy_grid'):
    structure = settings.structure
    parameters = result.parameters(settings.target_objective.shape)
    species = sorted(structure.unique_species, key=species_to_ordinal.get)
    return [tabulate.tabulate(sros, headers=species, tablefmt=tablefmt, showindex=species) for sros in parameters]


def make_result_document(sqs_results: T.Iterable[SQSResult], settings: Settings, timings : T.Optional[TimingDictionary]=None, fields: T.Tuple[str]=('configuration',)) -> Settings:
    allowed_fields = {
        'configuration': lambda result: symbols_from_z(result.configuration),
        'objective': attr('objective'),
        'parameters': lambda result: result.parameters(settings.target_objective.shape)
    }

    def make_sqs_result_document(result):
        if len(fields) == 1:
            key = next(iter(fields))
            return allowed_fields[key](result)
        else:
            return {f: allowed_fields[f](result) for f in fields}

    have_sublattice = 'sublattice' in settings
    result_document = {
        'structure': settings.sublattice.structure if have_sublattice else settings.structure,
        'configurations': {r.rank: make_sqs_result_document(r) for r in sqs_results}
    }
    if have_sublattice:
        result_document['which'] = settings.sublattice.which
    if timings is not None: result_document['timings'] = timings
    return Settings(result_document)


def expand_results(dense: Settings):
    have_sublattice = 'which' in dense
    s = dense.structure
    new_structure = functools.partial(Structure, s.lattice, s.frac_coords)

    def new_species(conf):
        if have_sublattice:
            species = s.symbols
            mask = np.array(dense.which, dtype=int)
            species[mask] = conf
            return species.tolist()
        else: return conf

    return {
        rank:
        new_structure(new_species(conf if not isinstance(conf, dict) else conf['configuration']))
        for rank, conf in dense.configurations.items()
    }


@click.command('iteration')
@click.option('--export', '-e', 'do_export', is_flag=True)
@click.option('--dump/--no-dump', default=True)
@click.option('--format', '-f', type=click.STRING, default='cif')
@click.option('--dump-inplace', '--inplace', 'dump_inplace', is_flag=True)
@click.option('--writer', '-w', type=click.Choice(['ase', 'pymatgen']), default='ase')
@click.option('--log-level', type=click.Choice(list(log_levels.keys())), default='warning')
@click.option('--output', '-o', 'output_file', type=click.Path(dir_okay=False, allow_dash=True))
@click.option('--dump-format', '-df', 'dump_format', type=click.Choice(['yaml', 'json', 'pickle']), default='yaml')
@click.option('--dump-include', '-di', 'dump_include', type=click.Choice(['parameters', 'timings', 'objective']), multiple=True)
@click.option('--compress', '-c', type=click.Choice(list(compression_to_file_extension)))
@click_settings_file('all')
def iteration(settings, log_level, do_export, output_file, dump, dump_format, dump_include, dump_inplace, format, writer, compress):
    iteration_settings = construct_settings(settings, False)
    set_core_log_level(log_levels.get(log_level))
    sqs_results, timings = pair_sqs_iteration(iteration_settings)

    output_prefix = output_file \
        if output_file is not None \
        else (os.path.splitext(settings.file_name)[0] if 'file_name' in settings else 'sqs')

    dump_include = list(dump_include)
    if 'configuration' not in dump_include: dump_include += ['configuration']
    result_document = make_result_document(sqs_results, settings, fields=dump_include)
    if dump_inplace:
        settings.update(result_document)
        keys_to_remove = {'file_name', 'input_format', 'composition', 'iterations', 'max_output_configurations',
                          'mode', 'threads_per_rank', 'is_sublattice'}
        final_document = {k: v for k, v in settings.items() if k  not in keys_to_remove}
        if 'sublattice' in final_document:
            final_document.update(final_document['sublattice'])
            del final_document['sublattice']
    else:
        final_document = result_document

    if dump:
        output_file_name = f'{output_prefix}.result.{dump_format}'
        with open(output_file_name, 'wb') as handle:
            handle.write(
                dumps(
                    to_dict(final_document), output_format=dump_format
                ))

    if do_export:
        writer = F(writer)
        if format not in supported_formats(writer):
            error(f'{writer.value} does not support the format "{format}". '
                  f'Supported formats are {supported_formats(writer)}')
        structures = expand_results(result_document)
        export_structures(structures, format=format, output_file=output_prefix, writer=writer, compress=compress)

    return final_document


@click.command('export')
@click.option('--format', '-f', type=click.STRING, default='cif')
@click.option('--writer', '-w', type=click.Choice(['ase', 'pymatgen']), default='ase')
@click.option('--compress', '-c', type=click.Choice(list(compression_to_file_extension)))
@click.option('--output', '-o', 'output_file', type=click.Path(dir_okay=False, allow_dash=True))
@click_settings_file(process=None, default_name='sqs.result.yaml')
def export(settings, format='cif', writer='ase', compress=None, output_file='sqs.result'):
    result_document = attrdict.AttrDict(settings)
    needed_keys = {'structure', 'configurations'}
    if not all(map(lambda k: k in result_document, needed_keys)):
        raise KeyError(f'Result document must at least contain the following keys: {needed_keys}')
    # read the structure from from the settings document
    result_document['structure'] = read_structure(result_document)
    output_prefix = output_file \
        if output_file is not None \
        else (os.path.splitext(settings.file_name)[0] if 'file_name' in settings else 'sqs')
    writer = F(writer)

    if format not in supported_formats(writer):
        error(f'{writer.value} does not support the format "{format}". '
              f'Supported formats are {supported_formats(writer)}', prefix='FeatureError')

    structures = expand_results(result_document)
    export_structures(structures, format=format, output_file=output_prefix, writer=writer, compress=compress)


@click.command('analysis')
@click.option('--output', '-o', 'output_file', type=click.Path(dir_okay=False, allow_dash=True))
@click_settings_file('all', ignore=('composition',))
def analysis(settings, output_file):

    output_prefix = output_file \
        if output_file is not None \
        else (os.path.splitext(settings.file_name)[0] if 'file_name' in settings else 'sqs')

    iteration_settings = construct_settings(settings, False)
    result = pair_analysis(iteration_settings)
    format_parameters(settings, result)


@click.group('run')
def run():
    pass


run.add_command(iteration, 'iteration')
run.add_command(analysis, 'analysis')
run.add_command(export, 'export')

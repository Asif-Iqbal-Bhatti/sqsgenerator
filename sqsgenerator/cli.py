
import click
from sqsgenerator.commands.run import run
from sqsgenerator.commands.params import params
from sqsgenerator.commands.compute import compute


def make_version_string():
    from sqsgenerator.core import __version__
    major, minor, *_ = __version__
    return f'{major}.{minor}'


def make_version_message():
    from sqsgenerator.core import __version__, __features__
    _, _, hash_, branch = __version__
    message = f'%(prog)s, version %(version)s, commit {hash_}@{branch}, features {set(__features__)}'
    return message


@click.group(help='sqsgenerator')
@click.version_option(prog_name='sqsgenerator', version=make_version_string(), message=make_version_message())
def cli():
    pass


cli.add_command(params, 'params')
cli.add_command(compute, 'compute')
cli.add_command(run, 'run')

if __name__ == '__main__':
    cli()
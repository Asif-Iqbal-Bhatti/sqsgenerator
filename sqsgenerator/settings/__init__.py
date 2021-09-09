
import typing as T
from attrdict import AttrDict
from sqsgenerator.core import IterationSettings
from sqsgenerator.settings.defaults import defaults
from sqsgenerator.settings.exceptions import BadSettings
from sqsgenerator.settings.readers import process_settings, parameter_list


def construct_settings(settings: AttrDict, process: T.Optional[bool] = True, **overloads) -> IterationSettings:
    """
    Constructs a ``sqsgenerator.core.IterationSettings`` object. This object is needed to pass the {settings} to the
    C++ extension. This function does not modify the passed {settings} but creates a copy of it. This function is meant
    for **internal use**

    :param settings: the dict-like settings object. The parameter is passed on to the ``AttrDict`` constructor
    :type settings: AttrDict
    :param process: process the the settings (default is ``True``)
    :type process: bool
    :param overloads: keyword args are used to **overload** key in the {settings} dictionary
    :return: the ``sqsgenerator.core.IterationSettings`` object, ready to pass on to ``pair_analysis``
    :rtype: IterationsSettings
    :raises KeyError: if a key was passed in {overloads} which is not present in {settings}
    """

    settings = AttrDict(settings.copy())
    for overload, value in overloads.items():
        if overload not in settings:
            raise KeyError(overload)
        settings[overload] = value
    settings = process_settings(settings) if process else settings

    return IterationSettings(
        settings.structure,
        settings.target_objective,
        settings.pair_weights,
        dict(settings.shell_weights),
        settings.iterations,
        settings.max_output_configurations,
        list(settings.shell_distances),
        list(settings.threads_per_rank),
        settings.atol,
        settings.rtol,
        settings.mode
    )


__all__ = [
    'BadSettings',
    'parameter_list',
    'process_settings',
    'construct_settings',
    'defaults'
]

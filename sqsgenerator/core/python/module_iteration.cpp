//
// Created by dominik on 14.07.21.
//
#include "types.hpp"
#include "iteration.hpp"
#include <boost/python/suite/indexing/map_indexing_suite.hpp>

using namespace sqsgenerator;
using namespace sqsgenerator::python;

char const* greet()
{
    return "hello, world";
}



BOOST_PYTHON_MODULE(iteration) {
        Py_Initialize();
        np::initialize();

        py::enum_<iteration_mode>("IterationMode")
                .value("random", sqsgenerator::random)
                .value("systematic", systematic);

        py::class_<pair_shell_weights_t>("ShellWeights")
                .def(py::map_indexing_suite<pair_shell_weights_t>());
        //StructurePythonWrapper wrapper, double target_objective, np::ndarray parameter_weights, pair_shell_weights_t shell_weights, int iterations, int output_configurations, int iteration_mode, uint8_t prec
        py::class_<IterationSettingsPythonWrapper>("IterationSettings", py::init<StructurePythonWrapper, double, np::ndarray, py::dict, int, int, iteration_mode, uint8_t>())
                .def_readonly("num_atoms", &IterationSettingsPythonWrapper::num_atoms)
                .def_readonly("num_shells", &IterationSettingsPythonWrapper::num_shells)
                .def_readonly("num_iterations", &IterationSettingsPythonWrapper::num_iterations)
                .def_readonly("num_species", &IterationSettingsPythonWrapper::num_species)
                .def_readonly("num_output_configurations", &IterationSettingsPythonWrapper::num_output_configurations)
                .def_readonly("mode", &IterationSettingsPythonWrapper::mode)
                .def_readonly("structure", &IterationSettingsPythonWrapper::structure)
                .def_readonly("target_objective", &IterationSettingsPythonWrapper::target_objective)
                .def_readonly("shell_weights", &IterationSettingsPythonWrapper::shell_weights)
                .def_readonly("parameter_weights", &IterationSettingsPythonWrapper::parameter_weights);

}
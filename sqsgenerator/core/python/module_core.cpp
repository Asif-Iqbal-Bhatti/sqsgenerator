//
// Created by dominik on 02.09.21.
//

//
// Created by dominik on 14.07.21.
//
#include "version.hpp"
#include "types.hpp"
#include "sqs.hpp"
#include "data.hpp"
#include "helpers.hpp"
#include "iteration.hpp"
#include "container_wrappers.hpp"
#include "structure_utils.hpp"
#include <boost/log/core.hpp>
#include <boost/log/trivial.hpp>
#include <boost/log/utility/setup.hpp>
#include <boost/python/suite/indexing/map_indexing_suite.hpp>


namespace logging = boost::log;
using namespace sqsgenerator;
using namespace sqsgenerator::python;
namespace py = boost::python;
namespace np = boost::python::numpy;
namespace helpers = sqsgenerator::python::helpers;
namespace atomistics = sqsgenerator::utils::atomistics;

static bool log_initialized = false;

void init_logging() {
    if (! log_initialized) {
        static const std::string COMMON_FMT("[%TimeStamp%][%Severity%]:%Message%");
        boost::log::register_simple_formatter_factory<boost::log::trivial::severity_level, char>("Severity");
        boost::log::add_console_log(
                std::cout,
                boost::log::keywords::format = COMMON_FMT,
                boost::log::keywords::auto_flush = true
        );

        logging::core::get()->set_filter(logging::trivial::severity >= logging::trivial::trace);
        log_initialized = true;
    }
}

py::tuple pair_sqs_iteration(IterationSettingsPythonWrapper settings) {
    auto [sqs_results, thread_timings] = sqsgenerator::do_pair_iterations(*settings.handle());
    SQSResultCollection wrapped_results;
    for (auto &r : sqs_results) wrapped_results.push_back(SQSResultPythonWrapper(std::move(r)));
    py::dict thread_timings_converted;
    for (const auto &timing: thread_timings) {
        thread_timings_converted[timing.first] = sqsgenerator::python::helpers::vector_to_list(timing.second);
    }
    return py::make_tuple(wrapped_results, thread_timings_converted);
}

SQSResultPythonWrapper pair_analysis(IterationSettingsPythonWrapper settings) {
    return SQSResultPythonWrapper(std::move(sqsgenerator::do_pair_analysis(*settings.handle())));
}

void set_log_level(boost::log::trivial::severity_level log_level = boost::log::trivial::info) {
    logging::core::get()->set_filter(logging::trivial::severity >= log_level);
}

void initialize_converters()
{
    py::to_python_converter<cpp_int, helpers::Cpp_int_to_python_num>();
    helpers::Cpp_int_from_python_num();
}

rank_t rank_configuration_internal(const configuration_t &conf) {
    auto nspecies {sqsgenerator::utils::unique_species(conf).size()};
    auto [_, packed_configuration] = sqsgenerator::utils::pack_configuration(conf);
    return sqsgenerator::utils::rank_permutation(packed_configuration, nspecies);
}

rank_t rank_structure(StructurePythonWrapper &s) {
    return rank_configuration_internal(s.handle()->configuration());
}

rank_t rank_configuration(const py::object &iterable) {
    return rank_configuration_internal(helpers::list_to_vector<species_t>(iterable));
}

rank_t total_permutations_internal(const configuration_t &conf) {
    auto [_, packed_configuration] = sqsgenerator::utils::pack_configuration(conf);
    return sqsgenerator::utils::total_permutations(packed_configuration);
}

rank_t total_permutations_iterable(const py::object &iterable) {
    return total_permutations_internal(helpers::list_to_vector<species_t>(iterable));
}

rank_t total_permutations_structure(StructurePythonWrapper &s) {
    return total_permutations_internal(s.handle()->configuration());
}

configuration_t make_rank_internal(const configuration_t &conf, rank_t &rank) {
    auto total_perms = total_permutations_internal(conf);
    auto [packaging_indices, packed_configuration] = sqsgenerator::utils::pack_configuration(conf);
    auto hist = utils::configuration_histogram(packed_configuration);
    configuration_t result(conf);
    utils::unrank_permutation(result, hist, total_perms, rank);
    return utils::unpack_configuration(packaging_indices, result);
}


py::list make_rank_iterable(const py::object &iterable, rank_t rank) {
    return helpers::vector_to_list(sqsgenerator::utils::atomistics::Atoms::z_to_symbol(make_rank_internal(sqsgenerator::utils::atomistics::Atoms::symbol_to_z(helpers::list_to_vector<std::string>(iterable)), rank)));
}

StructurePythonWrapper make_rank_structure(StructurePythonWrapper &s, rank_t rank) {
    return {s.handle()->lattice(), s.handle()->frac_coords(), make_rank_internal(s.handle()->configuration(), rank), s.handle()->pbc()};
}


py::list atoms_from_numbers(const py::object &iterable) {
    auto numbers = helpers::list_to_vector<species_t>(iterable);
    std::vector<atomistics::Atom> atoms = atomistics::Atoms::from_z(numbers);
    return helpers::vector_to_list(atoms);
}

py::list atoms_from_symbols(const py::object &iterable) {
    auto symbols = helpers::list_to_vector<std::string>(iterable);
    std::vector<atomistics::Atom> atoms = atomistics::Atoms::from_symbol(symbols);
    return helpers::vector_to_list(atoms);
}

py::list symbols_from_z(const py::object &iterable) {
    auto numbers = helpers::list_to_vector<species_t>(iterable);
    std::vector<std::string> symbols = atomistics::Atoms::z_to_symbol(numbers);
    return helpers::vector_to_list(symbols);
}

py::list available_species() {
    return helpers::vector_to_list(atomistics::Atoms::all_elements());
}

py::list default_shell_distances_wrapped(StructurePythonWrapper &s, double atol=1e-5, double rtol=1e-8) {
    return helpers::vector_to_list(sqsgenerator::utils::default_shell_distances(s.handle()->distance_matrix(), atol, rtol));
}

BOOST_PYTHON_MODULE(iteration) {
        Py_Initialize();
        np::initialize();
        init_logging();
        initialize_converters();

        py::class_<SQSResultPythonWrapper>("SQSResult", py::no_init)
        .def_readonly("objective", &SQSResultPythonWrapper::objective)
        .def_readonly("rank", &SQSResultPythonWrapper::rank)
        .def_readonly("configuration", &SQSResultPythonWrapper::configuration)
        .def("parameters", &SQSResultPythonWrapper::parameters);


        py::class_<atomistics::Atom>("Atom", py::no_init)
            .def_readonly("Z", &atomistics::Atom::Z)
            .def_readonly("name", &atomistics::Atom::name)
            .def_readonly("symbol", &atomistics::Atom::symbol)
            .def_readonly("atomic_radius", &atomistics::Atom::atomic_radius)
            .def_readonly("mass", &atomistics::Atom::mass);

        py::class_<StructurePythonWrapper>("Structure", py::init<np::ndarray, np::ndarray, py::object, py::tuple>())
            .def_readonly("lattice", &StructurePythonWrapper::lattice)
            .def_readonly("num_atoms", &StructurePythonWrapper::num_atoms)
            .def_readonly("species", &StructurePythonWrapper::species)
            .def_readonly("frac_coords", &StructurePythonWrapper::frac_coords)
            .def_readonly("distance_vecs", &StructurePythonWrapper::distance_vecs)
            .def_readonly("distance_matrix", &StructurePythonWrapper::distance_matrix)
            //.def<np::ndarray(StructurePythonWrapper::*)(const py::list&, double, double)>("shell_matrix", &StructurePythonWrapper::shell_matrix)
            //.def<np::ndarray(StructurePythonWrapper::*)(double, double)>("shell_matrix", &StructurePythonWrapper::shell_matrix)
            .def_readonly("pbc", &StructurePythonWrapper::pbc);

        py::class_<SQSResultCollection>("SQSResultCollection")
        .def("__len__", &SQSResultCollection::size)
        .def("__getitem__", &helpers::std_item<SQSResultCollection>::get,
            py::return_value_policy<py::copy_non_const_reference>())
        .def("__iter__", py::iterator<SQSResultCollection>());

        py::enum_<iteration_mode>("IterationMode")
        .value("random", sqsgenerator::random)
        .value("systematic", sqsgenerator::systematic);

        py::enum_<boost::log::trivial::severity_level>("BoostLogLevel")
        .value("trace", boost::log::trivial::trace)
        .value("debug", boost::log::trivial::debug)
        .value("info", boost::log::trivial::info)
        .value("warning", boost::log::trivial::warning)
        .value("error", boost::log::trivial::error)
        .value("fatal", boost::log::trivial::fatal);

        py::class_<pair_shell_weights_t>("ShellWeights")
        .def(py::map_indexing_suite<pair_shell_weights_t>());
        //StructurePythonWrapper wrapper, double target_objective, np::ndarray parameter_weights, pair_shell_weights_t shell_weights, int iterations, int output_configurations, int iteration_mode, uint8_t prec
        py::class_<IterationSettingsPythonWrapper>("IterationSettings",py::init<StructurePythonWrapper, np::ndarray, np::ndarray, py::dict, int, int, py::list, iteration_mode>())
        .def(py::init<StructurePythonWrapper, np::ndarray, np::ndarray, py::dict, int, int, py::list, double, double, iteration_mode>())
        .def(py::init<StructurePythonWrapper, np::ndarray, np::ndarray, py::dict, int, int, py::list, py::list, double, double, iteration_mode>())
        .def_readonly("num_atoms", &IterationSettingsPythonWrapper::num_atoms)
        .def_readonly("num_shells", &IterationSettingsPythonWrapper::num_shells)
        .def_readonly("num_iterations", &IterationSettingsPythonWrapper::num_iterations)
        .def_readonly("num_species", &IterationSettingsPythonWrapper::num_species)
        .def_readonly("num_output_configurations", &IterationSettingsPythonWrapper::num_output_configurations)
        .def_readonly("mode", &IterationSettingsPythonWrapper::mode)
        .def_readonly("structure", &IterationSettingsPythonWrapper::structure)
        .def_readonly("target_objective", &IterationSettingsPythonWrapper::target_objective)
        .def_readonly("shell_weights", &IterationSettingsPythonWrapper::shell_weights)
        .def_readonly("parameter_weights", &IterationSettingsPythonWrapper::parameter_weights)
        .def_readonly("atol", &IterationSettingsPythonWrapper::atol)
        .def_readonly("rtol", &IterationSettingsPythonWrapper::rtol);

        py::def("set_log_level", &set_log_level);
        py::def("pair_sqs_iteration", &pair_sqs_iteration);
        py::def("pair_analysis", &pair_analysis);

        py::def("rank_structure", &rank_structure);
        py::def("rank_configuration", &rank_configuration);

        py::def("total_permutations", &total_permutations_iterable);
        py::def("total_permutations", &total_permutations_structure);

        py::def("make_rank", &make_rank_iterable);
        py::def("make_rank", &make_rank_structure);

        py::def("default_shell_distances", &default_shell_distances_wrapped);

        py::def("atoms_from_numbers", &atoms_from_numbers);
        py::def("atoms_from_symbols", &atoms_from_symbols);

        py::def("symbols_from_z", &symbols_from_z);

        py::def("available_species", &available_species);

        py::list features;
#ifdef _OPENMP
        features.append("openmp");
#endif
#if defined(USE_MPI)
        features.append("mpi");
#endif
        py::scope().attr("__features__")= features;
        py::scope().attr("__version__") = py::make_tuple(VERSION_MAJOR, VERSION_MINOR, GIT_COMMIT_HASH, GIT_BRANCH);
}
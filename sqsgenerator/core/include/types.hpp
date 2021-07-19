//
// Created by dominik on 21.05.21.
//

#ifndef SQSGENERATOR_TYPES_HPP
#define SQSGENERATOR_TYPES_HPP
#include <vector>
#include <map>
#include <array>
#include <cstdint>
#include <functional>
#include <boost/multi_array.hpp>
#include <boost/multiprecision/cpp_int.hpp>
#include <boost/numeric/ublas/matrix.hpp>
#include <boost/numeric/ublas/storage.hpp>

namespace sqsgenerator {
    typedef uint8_t species_t;
    typedef uint32_t shell_t;
    typedef boost::multiprecision::cpp_int rank_t;
    typedef boost::multi_array<shell_t, 2> pair_shell_matrix;
    typedef boost::const_multi_array_ref<shell_t, 2> const_pair_shell_matrix_ref_t;
    typedef boost::multi_array_ref<shell_t, 2> pair_shell_matrix_ref_t;
    typedef boost::multi_array<double, 2> array_2d_t;
    typedef boost::multi_array<double, 3> array_3d_t;
    typedef boost::multi_array_ref<double, 2> array_2d_ref_t;
    typedef boost::multi_array_ref<double, 3> array_3d_ref_t;
    typedef array_3d_t::index index_t;
    typedef boost::const_multi_array_ref<double, 2> const_array_2d_ref_t;
    typedef boost::const_multi_array_ref<double, 3> const_array_3d_ref_t;
    typedef boost::multi_array_ref<double, 3> array_3d_ref_t;
    typedef std::vector<species_t> configuration_t;
    typedef std::vector<double> parameter_storage_t;
    typedef std::map<shell_t, double> pair_shell_weights_t;
    using get_next_configuration_t = std::function<bool(configuration_t&)>;
    using get_next_configuration_ptr_t = std::function<bool(species_t*, size_t)>;
    template<size_t NDims>
    using Shape = std::array<size_t, NDims>;

    // The array consists of {size_t i, size_t j, size_t shell, size_t shell_index}
    typedef std::array<pair_shell_matrix::index, 4> AtomPair;

}
#endif //SQSGENERATOR_TYPES_HPP

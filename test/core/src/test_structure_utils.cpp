//
// Created by dominik on 29.06.21.
//
#include "utils.hpp"
#include "structure_utils.hpp"
#include <cassert>
#include <stdexcept>
#include <iostream>
#include <fstream>
#include <filesystem>
#include <boost/multi_array.hpp>
#include <boost/numeric/ublas/matrix.hpp>
#include <gtest/gtest.h>

using namespace boost;
using namespace sqsgenerator::utils;
using namespace boost::numeric::ublas;
namespace fs = std::filesystem;

namespace sqsgenerator::test {

    template <typename T> T convert_to (const std::string &str)
    {
        std::istringstream ss(str);
        T num;
        ss >> num;
        return num;
    }
/**
 * \brief   Return the filenames of all files that have the specified extension
 *          in the specified directory and all subdirectories.
 */
    std::vector<fs::path> get_all(std::string const &root, std::string const &ext) {
        std::vector<fs::path> paths;
        for (auto &p : fs::recursive_directory_iterator(root))
        {
            if (p.path().extension() == ext) paths.emplace_back(p.path());
        }
        return paths;
    }

    std::vector<std::string> split (std::string s, std::string delimiter) {
        // Taken from https://stackoverflow.com/questions/14265581/parse-split-a-string-in-c-using-string-delimiter-standard-c
        size_t pos_start = 0, pos_end, delim_len = delimiter.length();
        std::string token;
        std::vector<std::string> res;

        while ((pos_end = s.find (delimiter, pos_start)) != std::string::npos) {
            token = s.substr (pos_start, pos_end - pos_start);
            pos_start = pos_end + delim_len;
            res.push_back (token);
        }

        res.push_back (s.substr (pos_start));
        return res;
    }

    template<typename T, size_t NDims>
    multi_array<T, NDims> read_array(std::ifstream &fhandle, std::string const &name) {
        std::string line;
        std::string start_line = name + "::array::begin";
        while (std::getline(fhandle, line)) {
            if (line == start_line) { break; }
        }
        assert(line == start_line);
        // Read dimensions
        std::getline(fhandle, line);
        auto crumbs  = split(line, " ");
        assert(crumbs.size() == 2);
        assert(crumbs[0] == name + "::array::ndims");
        size_t ndims {std::stoul(crumbs[1])};
        assert(ndims == NDims);

        // Read shape
        std::getline(fhandle, line);
        crumbs  = split(line, " ");
        assert(crumbs.size() == ndims+1);
        assert(crumbs[0] == name + "::array::shape");
        std::vector<size_t> shape;
        for(auto it = crumbs.begin() + 1; it != crumbs.end(); ++it) shape.push_back(std::stoul(*it));
        assert(shape.size() == ndims);
        size_t num_elements = std::accumulate(shape.begin(), shape.end(), 1, std::multiplies<size_t>());

        std::getline(fhandle, line);
        crumbs  = split(line, " ");
        assert(crumbs.size() == num_elements+1);
        assert(crumbs[0] == name + "::array::data");
        std::vector<T> data;
        for(auto it = crumbs.begin() + 1; it != crumbs.end(); ++it) data.push_back(convert_to<T>(*it));
        assert(data.size() == num_elements);


        multi_array<T, NDims> result;
        auto& shape_array = reinterpret_cast<boost::array<size_t, NDims> const&>(*shape.data());
        result.resize(shape_array);
        result.assign(data.begin(), data.end());
        std::getline(fhandle, line);
        assert(line == name + "::array::end");
        return result;
    }

    struct TestCaseData {
    public:
        multi_array<double, 2> lattice;
        multi_array<double, 2> fcoords;
        multi_array<double, 2> distances;
        multi_array<double, 3> vecs;
        multi_array<int, 2> shells;
    };

    TestCaseData read_test_data(std::string const &path) {
        std::ifstream fhandle(path);
        std::string line;
        auto lattice = read_array<double, 2>(fhandle, "lattice");
        auto fcoords = read_array<double, 2>(fhandle, "fcoords");
        auto d2 = read_array<double, 2>(fhandle, "distances");
        auto shells = read_array<int, 2>(fhandle, "shells");
        auto vecs = read_array<double, 3>(fhandle, "vecs");

        fhandle.close();
        return TestCaseData {lattice, fcoords, d2, vecs, shells};
    }

    class StructureUtilsTestFixture : public ::testing::Test {
    protected:
        std::vector<TestCaseData> test_cases{};


    public:
        void SetUp() {
            // code here will execute just before the test ensues
            // std::cout << "StructureUtilsTestFixture::SetUp(): " << std::filesystem::current_path() << std::endl;
            get_all("resources", ".data");
            for (auto &p : get_all("resources", ".data")) {
                // std::cout << "StructureUtilsTestFixture::SetUp(): Found test case: " << p << std::endl;
                test_cases.emplace_back(read_test_data(p));
            }
        };

        void TearDown() {
            // code here will be called just after the test completes
            // ok to through exceptions from here if need be
        }


    };

    template<typename T, size_t NDims>
    void assert_multi_array_equal(const multi_array<T, NDims> &a, const multi_array<T, NDims> &b) {
        ASSERT_EQ(a.num_elements(), b.num_elements());
        for (size_t i = 0; i < a.num_elements(); ++i) {

            ASSERT_NEAR(std::abs(a.data()[i]), std::abs(b.data()[i]), 1.0e-5);
            //EXPECT_NEAR(a.data()[i], b.data()[i], 1.0e-5);
        }
    }

    TEST_F(StructureUtilsTestFixture, TestPbcVectors) {
        for (TestCaseData &test_case : test_cases) {
            matrix<double> lattice (matrix_from_multi_array<double>(test_case.lattice));
            matrix<double> fcoords (matrix_from_multi_array<double>(test_case.fcoords));
            auto pbc_vecs = sqsgenerator::utils::pbc_shortest_vectors(lattice, fcoords, true);
            for (size_t i = 0; i < 3; i++) ASSERT_EQ(pbc_vecs.shape()[i], test_case.vecs.shape()[i]);
            assert_multi_array_equal(pbc_vecs, test_case.vecs);
        }
    }

    TEST_F(StructureUtilsTestFixture, TestDistanceMatrix) {
        for (TestCaseData &test_case : test_cases) {
            matrix<double> lattice (matrix_from_multi_array<double>(test_case.lattice));
            matrix<double> fcoords (matrix_from_multi_array<double>(test_case.fcoords));
            auto d2 = sqsgenerator::utils::distance_matrix(lattice, fcoords, true);
            for (size_t i = 0; i < 2; i++)  ASSERT_EQ(d2.shape()[i], test_case.vecs.shape()[i]);
            assert_multi_array_equal(d2, test_case.distances);
            auto d2_external = sqsgenerator::utils::distance_matrix(test_case.vecs);
            assert_multi_array_equal(d2, d2_external);
        }
    }

    TEST_F(StructureUtilsTestFixture, TestShellMatrix) {
        for (TestCaseData &test_case : test_cases) {
            matrix<double> lattice (matrix_from_multi_array<double>(test_case.lattice));
            matrix<double> fcoords (matrix_from_multi_array<double>(test_case.fcoords));
            auto d2 = sqsgenerator::utils::distance_matrix(lattice, fcoords, true);
            auto shells = sqsgenerator::utils::shell_matrix(d2);
            for (size_t i = 0; i < 2; i++)  ASSERT_EQ(shells.shape()[i], test_case.shells.shape()[i]);
            assert_multi_array_equal(shells, test_case.shells);
            auto shells_external = sqsgenerator::utils::shell_matrix(test_case.distances);
            assert_multi_array_equal(shells, shells_external);
        }
    }
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
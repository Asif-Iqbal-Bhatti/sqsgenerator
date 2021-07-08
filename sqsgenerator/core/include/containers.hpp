//
// Created by dominik on 28.05.21.
//

#ifndef SQSGENERATOR_CONTAINERS_HPP
#define SQSGENERATOR_CONTAINERS_HPP

#include <iostream>
#include <atomic>
#include <vector>
#include <limits>
#include <thread>
#include <mutex>
#include <type_traits>
#include "types.hpp"
#include "rank.hpp"
#include "utils.hpp"
#include "moodycamel/concurrentqueue.h"
#include <boost/multiprecision/cpp_int.hpp>

using namespace sqsgenerator::utils;

namespace sqsgenerator {

    class SQSResult {
    private:
        double m_objective;
        cpp_int m_rank;
        configuration_t m_configuration;
        parameter_storage_t m_storage;

    public:

        SQSResult();
        SQSResult(double objective, cpp_int rank, configuration_t conf, parameter_storage_t params);
        SQSResult(double objective, configuration_t conf, parameter_storage_t parameters);
        //TODO: we could write: SQSResult(const SQSResult &other) = default; here
        SQSResult(const SQSResult &other);
        SQSResult(SQSResult &&other) noexcept;

        SQSResult& operator=(const SQSResult& other) = default;
        SQSResult& operator=(SQSResult&& other) noexcept;

        [[nodiscard]] double objective() const;
        [[nodiscard]] const configuration_t& configuration() const;
        [[nodiscard]] rank_t rank() const;
        [[nodiscard]] const parameter_storage_t& storage() const;
        template<size_t NDims>
        boost::const_multi_array_ref<double, NDims> parameters(const Shape<NDims> shape) const {
            return boost::const_multi_array_ref<double, NDims>(m_storage.data(), shape);
        }
    };


    class SQSResultCollection {
        /*
         * Intended use of SQSResultCollection
         *
         * ======== serial ========
         * SQSResultCollection results(size);
         * ======= parallel =======
         * results.addResult(); # thread-safe
         * double best = results.bestObjective(); # thread-safe
         * ======== serial ========
         * results.collect() # Gather the computed results from the MPMCQueue
         *                   # thread-safe (but should not be called in a "parallel section"
         */

    public:
        SQSResultCollection(int maxSize);
        //SQSResultCollection(const SQSResultCollection& other) = delete;
        SQSResultCollection(SQSResultCollection&& other) noexcept;

        double best_objective() const;
        bool add_result(const SQSResult &item);
        void collect();
        size_t size() const;
        size_t queue_size() const;
        size_t result_size() const;
        const std::vector<SQSResult>& results() const;

    private:
        moodycamel::ConcurrentQueue<SQSResult> m_q;
        std::atomic<size_t> m_size;
        std::atomic<double> m_best_objective;
        std::mutex m_mutex_clear;
        std::vector<SQSResult> m_r;
        int m_max_size;

        void clear_queue();
    };


}


#endif //SQSGENERATOR_CONTAINERS_HPP

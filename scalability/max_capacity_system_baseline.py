#!/usr/bin/env python3
import os

import experiment
import gflags
import misc
import run_system_baseline_experiment
from elasticsearch import ElasticSearch

FLAGS = gflags.FLAGS

# Flags for query mode
gflags.DEFINE_integer("query_initial_rps", 100, "Start rps and increment in query mode.")
gflags.DEFINE_integer("max_query_load", 40000, "Maximum query load in queries per second to issue.")
gflags.DEFINE_integer("target_query_load", 4000, "Target query load in queries per second to issue.")
gflags.DEFINE_integer("query_rps_increment", 50, "Increment of requests per second per round for queries.")

# Flags for update mode
gflags.DEFINE_integer("target_update_load", 600, "Target update load in queries per second to issue.")
gflags.DEFINE_integer("update_rps_increment", 20, "Increment of requests per second per round for update calls.")
gflags.DEFINE_integer("update_initial_rps", 100, "Start rps and increment in update mode.")
gflags.DEFINE_integer("max_update_load", 2000, "Maximum update load in queries per second to issue.")

# Maximum failure rate and median query duration limit to consider
# for rps to choose as rps_max. If failure rate or latency is higher,
# continue running the benchmark, but do not consider this RPS
# for max capacity
gflags.DEFINE_float(
    "allowable_failure_rate", 0.2, "Maximum failure rate at which to consider the iteration successful."
)
gflags.DEFINE_integer(
    "allowable_t_median", 5000, "Maximum query median latency at which to consider the iteration successful."
)
gflags.DEFINE_integer(
    "update_allowable_t_median", 5000, "Maximum update median latency at which to consider the iteration successful."
)

# Maximum failure rate and median query duration limit for when to
# stop the benchmark.
# Looks like the workload generator timeout is 30s, so we will never
# see anything higher than that on average.
gflags.DEFINE_float("stop_failure_rate", 0.95, "Maximum failure rate before aborting the benchmark.")
gflags.DEFINE_integer("stop_t_median", 120000, "Maximum median latency before aborting the benchmark.")

if __name__ == "__main__":
    experiment.parse_command_line_args()
    experiment_name = os.path.basename(__file__).replace(".py", "")

    datapoints = (
        misc.get_datapoints(
            FLAGS.target_update_load, FLAGS.update_initial_rps, FLAGS.max_update_load, FLAGS.update_rps_increment, 1
        )
        if FLAGS.use_updates
        else misc.get_datapoints(
            FLAGS.target_query_load, FLAGS.query_initial_rps, FLAGS.max_query_load, FLAGS.query_rps_increment, 1
        )
    )
    exp = run_system_baseline_experiment.Experiment1()
    (
        failure_rate,
        t_median,
        t_average,
        t_max,
        t_min,
        total_requests,
        num_success,
        num_failure,
        rps,
    ) = exp.run_iterations(datapoints)

    ElasticSearch.send_max_capacity(
        experiment_name,
        "Update" if FLAGS.use_updates else "Query",
        exp.git_hash,
        exp.git_hash,
        FLAGS.is_ci_job,
        rps,
        exp.out_dir,
        exp.t_experiment_start,
    )

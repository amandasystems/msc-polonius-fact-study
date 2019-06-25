#!/usr/bin/env python3

# benchmark a release version of Polonius on a number of directories containing
# nll-facts.
# benchmark-solving <my-crate> <my-other-crate>

import csv
import sys
import timeit
from pathlib import Path

from benchmark import inputs_or_workdir, run_command

POLONIUS_OPTIONS = ["--skip-timing", "--ignore-region-live-at"]
POLONIUS_PATH = "../polonius/target/release/polonius"
POLONIUS_COMMAND = [POLONIUS_PATH, *POLONIUS_OPTIONS]
NR_REPEATS = 3

ALGORITHMS = ["Naive", "Hybrid", "DatafrogOpt"]


def benchmark_crate_fn(p, algorithm):
    """
    Perform benchmarks on a function's input data, located in p
    """
    benchmark_timer = timeit.Timer(
        lambda: run_command([*POLONIUS_COMMAND, "-a", algorithm, "--", str(p)]))
    try:
        return min(benchmark_timer.repeat(NR_REPEATS, number=1))
    except RuntimeError:
        return None


def benchmark_crate_fns(facts_path):
    return ([p.stem, *[benchmark_crate_fn(p, a) for a in ALGORITHMS]]
            for p in facts_path.iterdir()
            if p.is_dir() and not p.stem[0] == ".")


def benchmark_crate_folder(p):
    assert isinstance(p, Path)
    assert p.is_dir(), f"{p} must be a directory!"

    facts_path = p / "nll-facts"
    if not facts_path.is_dir():
        facts_path = p
    program_name = p.stem

    for fn_name_and_runtimes in benchmark_crate_fns(facts_path):
        yield [program_name, *fn_name_and_runtimes]


def benchmark_crates_to_csv(dirs, out_fp):
    writer = csv.writer(out_fp)
    writer.writerow([
        "program", "function",
        *[f"min({NR_REPEATS}) {a} runtime" for a in ALGORITHMS]
    ])
    for c in crate_fact_list:
        writer.writerows(benchmark_crate_folder(c))


if __name__ == '__main__':
    crate_fact_list = inputs_or_workdir()
    benchmark_crates_to_csv(crate_fact_list, sys.stdout)

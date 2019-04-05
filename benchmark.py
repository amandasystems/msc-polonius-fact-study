#!/usr/bin/env python3
import copy
import csv
import os
import pathlib
import re
import shutil
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from contextlib import contextmanager

import scipy.stats

CLEAN_COMMAND = ["cargo", "+nightly", "clean"]
CHECK_COMMAND = ["cargo", "+nightly", "check", "--message-format", "short"]
ALGORITHMS = [
    "-Zpolonius -Zborrowck=mir -Ztwo-phase-borrows",
    "-Zborrowck=mir -Ztwo-phase-borrows",
]
REPEAT_TIMES = 3


@contextmanager
def chdir(d):
    #print(f"changing directory to {d}")
    starting_dir = os.getcwd()
    os.chdir(d)
    try:
        yield
    finally:
        os.chdir(starting_dir)


@contextmanager
def temp_env(**environment):
    """
    Temporarily set environment variables.
    """
    old_env = copy.deepcopy(os.environ)

    try:
        for key, val in environment.items():
            os.environ[key] = str(val)

        yield
    finally:
        os.environ = old_env


def run_command(command):
    res = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=False)
    if res.returncode != 0:
        raise RuntimeError(
            f"error running {' '.join(command)}. stderr={res.stderr}")
    return res


def clean_dir(project=None):
    project_part = ["-p", project] if project else []

    #res = run_command([*CLEAN_COMMAND, *project_part])
    shutil.rmtree(
        pathlib.Path("target/debug") / pathlib.Path("build"),
        ignore_errors=True)
    shutil.rmtree(
        pathlib.Path("target/debug") / pathlib.Path("incremental"),
        ignore_errors=True)


def run_experiment(option_set, directory):
    print(f"running experiment {option_set} on {directory}")
    with chdir(directory):
        clean_dir(project=directory.stem)
        start_time = time.time()
        with temp_env(RUSTFLAGS=option_set):
            _res = run_command(CHECK_COMMAND)

    return time.time() - start_time


def run_experiments(directory):
    def go(option_set):
        print(f"running with {option_set} on {directory}")
        print("warming up...")
        run_experiment(option_set, directory)
        print("warmed up!")
        return [
            run_experiment(option_set, directory) for _ in range(REPEAT_TIMES)
        ]

    polonius_stats, nll_stats = [go(setting) for setting in ALGORITHMS]
    _t, p = scipy.stats.ttest_ind(polonius_stats, nll_stats)

    return [min(polonius_stats), min(nll_stats), p]


def clone_repo(url):
    print(f"Cloning {url}")
    workdir = pathlib.Path("work")
    with chdir(workdir):
        repo_name = url.split("/")[-1].split(".git")[0]
        try:
            shutil.rmtree(repo_name)
        except FileNotFoundError:
            pass
        run_command(["git", "clone", "--recurse-submodules", "--quiet", url])
    return workdir / repo_name


def print_experiment(results):
    polonius, nll, p = results
    print(f"{polonius}\t{nll}\t{p}")


def clone_repos():
    # read a list of repositories from a file
    # clone them into a working directory, and collect their names
    # use their names to run benchmarks
    print("Cloning repositories...")
    return [
        clone_repo(url.strip())
        for url in open(pathlib.Path("repositories.txt"))
        if url.strip()[0] != "#"
    ]


if __name__ == '__main__':
    #[pathlib.Path(x) for x in sys.argv[1:]]
    print("P\tNLL\t\p")
    for d in clone_repos():
        print(f"Benchmarking {d}")
        try:
            print_experiment(run_experiments(d))
        except RuntimeError as e:
            print(f"error running experiments: {e}")
            continue

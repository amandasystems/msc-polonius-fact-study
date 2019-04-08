#!/usr/bin/env python3
import copy
import csv
import os
import pathlib
import random
import re
import shutil
import statistics
import datetime
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
NR_BENCHES = 0
EMA = None
ALPHA = 0.5

try:
    with open("results.csv") as fp:
        PREVIOUS_RESULTS = list(csv.reader(fp))
        SEEN_REPOS = set([r[0] for r in PREVIOUS_RESULTS])
except FileNotFoundError:
    PREVIOUS_RESULTS = None
    SEEN_REPOS = set()


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
    #print(f"running experiment {option_set} on {directory}")
    with chdir(directory):
        clean_dir(project=directory.stem)
        start_time = time.time()
        with temp_env(RUSTFLAGS=option_set):
            _res = run_command(CHECK_COMMAND)

    return time.time() - start_time


def run_experiments(directory):
    def go(option_set):
        #print(f"running with {option_set} on {directory}")
        #print("warming up...")
        run_experiment(option_set, directory)
        #print("warmed up!")
        return [
            run_experiment(option_set, directory) for _ in range(REPEAT_TIMES)
        ]

    polonius_stats, nll_stats = [go(setting) for setting in ALGORITHMS]
    _t, p = scipy.stats.ttest_ind(polonius_stats, nll_stats)

    return [min(polonius_stats), min(nll_stats), p]


def repo_name_from(url):
    return url.split("/")[-1].split(".git")[0]

def clone_repo(url):
    #print(f"Cloning {url}")
    workdir = pathlib.Path("work")
    repo_name = repo_name_from(url)
    with chdir(workdir):
        try:
            shutil.rmtree(repo_name)
        except FileNotFoundError:
            pass
        with temp_env(GIT_TERMINAL_PROMPT="0"):
            run_command([
                "git",
                "clone",
                #"--recurse-submodules",
                "--quiet",
                url
            ])
    return workdir / repo_name


def print_experiment(results):
    polonius, nll, p = results
    print(f"{polonius}\t{nll}\t{p}")


def clone_repos():
    global NR_BENCHES
    print("Cloning repositories...")
    repo_urls = [
        url.strip() for url in open(pathlib.Path("repositories.txt"))
        if url.strip()[0] != "#" and not repo_name_from(url) in SEEN_REPOS
    ]
    random.shuffle(repo_urls)
    NR_BENCHES = len(repo_urls)
    print(f"Read {len(repo_urls)} repos, already have stats for {len(SEEN_REPOS)}")
    return (clone_repo(url) for url in repo_urls)


if __name__ == '__main__':
    with open("results.csv", "w") as csvfile:
        writer = csv.writer(csvfile, delimiter=",")
        if not PREVIOUS_RESULTS:
            writer.writerow(["Repo", "Polonius Runtime", "NLL Runtime", "p"])
        else:
            for row in PREVIOUS_RESULTS:
                writer.writerow(row)
        prev_time = None
        for i, d in enumerate(clone_repos(), start=1):
            if prev_time is not None:
                expired_time = time.time() - prev_time
                EMA = expired_time if EMA is None else ALPHA * expired_time + (1 - ALPHA) * EMA
                eta = datetime.timedelta(seconds=(NR_BENCHES - i) * EMA)
            else:
                eta = None
            print(f"Benchmarking {d.stem}: it's {i}/{NR_BENCHES}. EMA = {EMA}s. ETA = {eta}", end="\r")
            prev_time = time.time()
            try:
                writer.writerow([d.stem, *run_experiments(d)])
                csvfile.flush()
            except RuntimeError as e:
                print(f"error running experiments: {e}")
                continue
            finally:
                shutil.rmtree(d, ignore_errors=True)

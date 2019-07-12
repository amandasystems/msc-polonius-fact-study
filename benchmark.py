#!/usr/bin/env python3
import copy
import csv
import datetime
import os
import pathlib
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

CLEAN_COMMAND = ["cargo", "+nightly", "clean"]
CHECK_COMMAND = ["cargo", "+nightly", "check"]
ALGORITHMS = [
    "-Zpolonius -Zborrowck=mir",
    "-Zborrowck=mir",
]
REPEAT_TIMES = 3
NR_BENCHES = 0
EMA = None
ALPHA = 0.5

PREVIOUS_RESULTS = None
SEEN_REPOS = set()
WRAPPER_PATH = os.path.abspath(pathlib.Path("./rust-shim.sh"))

with open("blacklist.txt") as fp:
    BLACKLIST = set([l.strip() for l in fp.readlines()])


def inputs_or_workdir():
    if len(sys.argv) == 1:
        print("Using directory work", file=sys.stderr)
        crate_fact_list = [p for p in Path("./work").iterdir()]
    else:
        crate_fact_list = [Path(p) for p in sys.argv[1:]]

    return [p for p in crate_fact_list if p.is_dir()]


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
        with temp_env(RUSTFLAGS=option_set), temp_env(
                RUSTC_WRAPPER=WRAPPER_PATH):
            _res = run_command(CHECK_COMMAND)
            print(_res.stdout)
            print(_res.stderr)

    return time.time() - start_time


def run_experiments(directory):
    import scipy.stats

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


def clone_repo(url, keep_files=False):
    workdir = pathlib.Path("work")
    repo_name = repo_name_from(url)
    with chdir(workdir):
        if not keep_files:
            try:
                shutil.rmtree(repo_name)
            except FileNotFoundError:
                pass
        if not (pathlib.Path("./") / repo_name).exists():
            with temp_env(GIT_TERMINAL_PROMPT="0"):
                run_command([
                    "git",
                    "clone",
                    #"--recurse-submodules",
                    "--quiet",
                    url
                ])
    return workdir / repo_name


def drop_git_ending(url):
    url = url.rstrip("/")
    if url[-4:] == ".git":
        return url[:-4]
    return url


def print_experiment(results):
    polonius, nll, p = results
    print(f"{polonius}\t{nll}\t{p}")


def git_url_in_set(url, url_set):
    return url in url_set or "{url}.git" in url_set or drop_git_ending(
        url) in url_set


def read_repo_file(repo_file):
    return {
        url.strip()
        for url in open(repo_file)
        if url.strip()[0] != "#" and not repo_name_from(url) in SEEN_REPOS
    }


def clone_repos(repo_urls, keep_files=False):
    global NR_BENCHES
    global BLACKLIST

    NR_BENCHES = len(repo_urls)

    for url in repo_urls:
        if git_url_in_set(url, BLACKLIST):
            print(f"clone_repos: {url} is blacklisted!", file=sys.stderr)
            continue
        try:
            yield clone_repo(url, keep_files)
        except RuntimeError:
            print(
                f"clone_repos: error cloning {url}, blacklisting it...",
                file=sys.stderr)
            blacklist_repo(url)


def blacklist_repo(url):
    global BLACKLIST
    if not git_url_in_set(url, BLACKLIST):
        BLACKLIST.add(url)
        with open("blacklist.txt", "a") as fp:
            fp.write(f"{url}\n")


if __name__ == '__main__':
    try:
        with open("results.csv") as fp:
            PREVIOUS_RESULTS = list(csv.reader(fp))
            SEEN_REPOS = set([r[0] for r in PREVIOUS_RESULTS])
    except FileNotFoundError:
        pass

    with open("results.csv", "w") as csvfile:
        writer = csv.writer(csvfile, delimiter=",")
        if not PREVIOUS_RESULTS:
            writer.writerow(["Repo", "Polonius Runtime", "NLL Runtime", "p"])
        else:
            for row in PREVIOUS_RESULTS:
                writer.writerow(row)
        prev_time = None
        for i, d in enumerate(
                clone_repos(pathlib.Path("repositories.txt")), start=1):
            if prev_time is not None:
                expired_time = time.time() - prev_time
                EMA = expired_time if EMA is None else ALPHA * expired_time + (
                    1 - ALPHA) * EMA
                eta = datetime.timedelta(seconds=(NR_BENCHES - i) * EMA)
            else:
                eta = None
            print(
                f"Benchmarking {d.stem}: it's {i}/{NR_BENCHES}. EMA = {EMA}s. ETA = {eta}",
                end="\n")
            prev_time = time.time()
            try:
                writer.writerow([d.stem, *run_experiments(d)])
                csvfile.flush()
            except RuntimeError as e:
                with open(f"{d.stem}.failure", "w") as fp:
                    fp.write(f"error running experiments: {e}")
                continue
            finally:
                shutil.rmtree(d, ignore_errors=True)

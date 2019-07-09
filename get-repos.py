#!/usr/bin/env python3

# get-repos repositories.txt

import importlib
import os
import random
import sys
from multiprocessing import Pool
from pathlib import Path

from benchmark import clone_repos, read_repo_file, repo_name_from

collect_facts = importlib.import_module("collect-facts")

ERROR_LOGFILE = Path.cwd() / "errors.log"
COMPLETED_LOGFILE = Path.cwd() / "fetched-repos.log"
NR_WORKERS = 10


def log_completed(repo):
    with open(COMPLETED_LOGFILE, "a") as fp:
        fp.write(f"{repo}\n")


def log_error(e):
    with open(ERROR_LOGFILE, "a") as fp:
        fp.write(f"{e}\n")
        fp.write("======\n")


def main(repo_file):
    with open(COMPLETED_LOGFILE, "w") as fp:
        fp.write("")

    with open(ERROR_LOGFILE, "w") as fp:
        fp.write("")

    print(f"reading repos from {repo_file}")

    repos = [
        repo_url for repo_url in read_repo_file(Path(repo_file)) if
        not collect_facts.has_facts(Path("./work") / repo_name_from(repo_url))
    ]

    print(f"processing {len(repos)} repositories")

    #random.shuffle(repos)

    with Pool(NR_WORKERS) as pool:
        for repo_count, repo in enumerate(clone_repos(repos, keep_files=True)):
            print(
                f"Generating facts for {repo_count}/{len(repos)}: {repo}".
                ljust(os.get_terminal_size(0).columns),
                end="\r")
            pool.apply_async(
                collect_facts.facts_from_repo,
                args=(repo, ),
                callback=log_completed,
                error_callback=log_error)


if __name__ == '__main__':
    main(sys.argv[1])

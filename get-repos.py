#!/usr/bin/env python3

# get-repos repositories.txt

import json
import multiprocessing as mp
import os
import shutil
import sys
import time
from pathlib import Path

from benchmark import (chdir, clone_repos, read_repo_file, repo_name_from,
                       run_command)

NLL_FACT_OPTIONS = "-Znll-facts"
RUST_VERSION = "+stage1"
HARD_TIMEOUT = "60m"
SOFT_TIMEOUT = "30m"
ERROR_LOGFILE = Path.cwd() / "repo-errors.log"
COMPLETED_LOGFILE = Path.cwd() / "repo-ok.csv"
NR_WORKERS = 10


def get_facts_for_targets(package, targets):
    if len(targets) == 1:
        run_command([
            "timeout", f"--kill-after={HARD_TIMEOUT}", SOFT_TIMEOUT, "cargo",
            RUST_VERSION, "rustc", "--package", package, "--", "-Znll-facts"
        ])
        return

    for target in targets:
        if target['kind'][0] == "bin":
            bin_name = target['name']
            run_command([
                "timeout", f"--kill-after={HARD_TIMEOUT}", SOFT_TIMEOUT,
                "cargo", RUST_VERSION, "rustc", "--package", package, "--bin",
                bin_name, "--", "-Znll-facts"
            ])
        else:
            run_command([
                "timeout", f"--kill-after={HARD_TIMEOUT}", SOFT_TIMEOUT,
                "cargo", RUST_VERSION, "rustc", "--package", package, "--lib",
                "--", "-Znll-facts"
            ])


def get_this_crates_facts():
    packages = json.loads(
        run_command(["cargo", "metadata", "--no-deps",
                     "--format-version=1"]).stdout)['packages']

    for package in packages:
        get_facts_for_targets(package['name'], package['targets'])


def rm_path(p):
    if p.is_dir():
        shutil.rmtree(p)
    else:
        os.remove(p)


def cleanup_repo(repo_path):
    for p in repo_path.iterdir():
        if "nll-facts" in str(p):
            continue
        else:
            rm_path(p)


def do_collect_facts(repo):
    try:
        with chdir(repo):
            get_this_crates_facts()
        return repo, None
    except Exception as e:
        return repo, e
    finally:
        cleanup_repo(repo)


def has_nll_facts_folder(repo_url):
    repo_name = repo_name_from(repo_url)
    facts_path = Path("./work") / repo_name / "nll-facts"
    return facts_path.is_dir()


def main(repo_file):
    print(f"Reading repos from {repo_file}")

    # Assume every folder with an nll-facts folder contains all necessary
    # facts already:
    repos = [
        r for r in read_repo_file(Path(repo_file))
        if not has_nll_facts_folder(r)
    ]

    print(f"Processing {len(repos)} repositories")
    err_count = 0
    ok_count = 0

    start_time = time.time()
    with mp.Pool(NR_WORKERS) as pool:
        jobs = pool.imap_unordered(do_collect_facts,
                                   clone_repos(repos, keep_files=True))

        with open(COMPLETED_LOGFILE, "w") as ok_fp, open(ERROR_LOGFILE,
                                                         "w") as err_fp:
            for i, (repo, error) in enumerate(jobs, start=1):
                if error:
                    err_fp.write(f"{repo.stem}\n{error}\n")
                    err_fp.write("======\n")
                    err_fp.flush()
                    err_count += 1
                else:
                    ok_fp.write(f"{repo.stem},{time.time()}\n")
                    ok_fp.flush()
                    ok_count += 1
                status = "Done" if not error else "Error"
                print(
                    f"E: {err_count} OK: {ok_count}: {status} processing repo {i}/{len(repos)}: {repo}"
                    .ljust(os.get_terminal_size(0).columns),
                    end="\r")

        pool.close()
        pool.join()
    print("")
    print(
        f"Finished in {str(time.time() - start_time)}. Errors: {err_count}, successes: {ok_count}"
    )


if __name__ == '__main__':
    main(sys.argv[1])

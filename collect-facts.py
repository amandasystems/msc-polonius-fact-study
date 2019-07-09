#!/usr/bin/env python3

# collect-facts <repositories>

import json
import os
import shutil
import sys
from pathlib import Path

from benchmark import chdir, run_command

NLL_FACT_OPTIONS = "-Znll-facts"
RUST_VERSION = "+stage1"
HARD_TIMEOUT = "30m"
SOFT_TIMEOUT = "15m"


def find_rust_files(d):
    return d.rglob("*.rs")


def get_nll_facts(rs_file):
    print(f"Getting facts from {rs_file}")
    try:
        run_command([
            "timeout", f"--kill-after={HARD_TIMEOUT}", SOFT_TIMEOUT, "rustc",
            RUST_VERSION, "-Znll-facts",
            str(rs_file)
        ])
    except RuntimeError as e:
        print(f"rustc returned error on {rs_file}")


def get_this_crates_facts():
    targets = json.loads(run_command(["cargo",
                                      "read-manifest"]).stdout)['targets']
    if len(targets) == 1:
        run_command([
            "timeout", f"--kill-after={HARD_TIMEOUT}", SOFT_TIMEOUT, "cargo",
            RUST_VERSION, "rustc", "--", "-Znll-facts"
        ])
        return

    #print("multiple targets: building them one at a time!")
    for target in targets:
        if target['kind'][0] == "bin":
            bin_name = target['name']
            run_command([
                "timeout", f"--kill-after={HARD_TIMEOUT}", SOFT_TIMEOUT,
                "cargo", RUST_VERSION, "rustc", "--bin", bin_name, "--",
                "-Znll-facts"
            ])
        else:
            run_command([
                "timeout", f"--kill-after={HARD_TIMEOUT}", SOFT_TIMEOUT,
                "cargo", RUST_VERSION, "rustc", "--lib", "--", "-Znll-facts"
            ])


def rm_path(p):
    if p.is_dir():
        shutil.rmtree(p)
    else:
        os.remove(p)


def has_facts(repo):
    return (repo / "nll-facts").exists()


def facts_from_repo(repo):
    try:
        with chdir(repo):
            get_this_crates_facts()
            for p in Path('.').iterdir():
                if "nll-facts" in str(p):
                    continue
                else:
                    rm_path(p)
    except RuntimeError as e:
        print(f"error: giving up on {repo}")
        shutil.rmtree(repo)
        raise e
    return repo


if __name__ == '__main__':
    repo_list = [Path(p) for p in sys.argv[1:]]

    for repo in repo_list:
        facts_from_repo(repo)

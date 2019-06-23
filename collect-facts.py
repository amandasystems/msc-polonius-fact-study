#!/usr/bin/env python3

# collect-facts <repositories>

import os
import shutil
import sys
from pathlib import Path

from benchmark import chdir, clone_repos, run_command

NLL_FACT_OPTIONS = "-Znll-facts"
RUST_VERSION = "+stage1"


def find_rust_files(d):
    return d.rglob("*.rs")


def get_nll_facts(rs_file):
    print(f"Getting facts from {rs_file}")
    try:
        run_command(["rustc", RUST_VERSION, "-Znll-facts", str(rs_file)])
    except RuntimeError as e:
        print(e)


def facts_from_repo(repo):
    if (repo / "nll-facts").exists():
        print(f"NLL facts already exists, skipping {repo}")
        return
    print(f"Generating facts for {repo}")
    with chdir(repo):
        try:
            run_command(["cargo", RUST_VERSION, "rustc", "--", "-Znll-facts"])
        except RuntimeError as e:
            print(e)
            for rs_file in find_rust_files(Path(".")):
                get_nll_facts(rs_file)
                #clean_path = str(rs_file).replace("/", "!")
                #facts_dir_name = Path(f"{clean_path}.nll-facts.d/nll-facts")
                #print(facts_dir_name)
                #shutil.move("nll-facts", str(facts_dir_name))
        for p in Path('.').iterdir():
            if "nll-facts" in str(p):
                continue
            else:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    os.remove(p)
    with open("fetched-repos.txt", "a") as fp:
        fp.write(f"{url}\n")


if __name__ == '__main__':
    repo_list = [Path(p) for p in sys.argv[1:]]

    for repo in repo_list:
        facts_from_repo(repo)

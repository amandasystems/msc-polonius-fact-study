#!/usr/bin/env python3

# get-repos repositories.txt

import importlib
import sys
from multiprocessing import Pool
from pathlib import Path

from benchmark import clone_repos

collect_facts = importlib.import_module("collect-facts")

if __name__ == '__main__':
    with Pool(10) as pool:
        for repo in clone_repos(Path(sys.argv[1]), keep_files=True):
            pool.apply_async(collect_facts.facts_from_repo, (repo, ))

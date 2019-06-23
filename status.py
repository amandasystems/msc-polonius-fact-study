#!/usr/bin/env python3
from pathlib import Path


def file_len(fname):
    with open(fname) as f:
        i = 0
        for i, l in enumerate(f):
            pass
        return i + 1


def dir_size_bytes(d):
    return sum(f.stat().st_size for f in d.rglob('*.facts'))


if __name__ == '__main__':
    blacklist_len = file_len("blacklist.txt")
    whitelist_len = file_len("repositories.txt")
    fetched_facts_len = file_len("fetched-repos.txt")

    fact_dirs = [d for d in Path("work").rglob("nll-facts") if d.is_dir()]

    print(
        f"Calculating the size of {len(fact_dirs)} accumulated fact directories..."
    )

    fact_size_bytes = sum([dir_size_bytes(fact_dir) for fact_dir in fact_dirs])

    print(
        f"Accumulated {fact_size_bytes / 1024 / 1024 / 1024:.1f} GB of raw facts."
    )
    print(
        f"Blacklisted {blacklist_len} and whitelisted {whitelist_len} repos.")
    print(f"Fully done processing {fetched_facts_len} repos.")

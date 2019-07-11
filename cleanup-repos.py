#!/usr/bin/env python3

import csv
import os
import shutil

from benchmark import inputs_or_workdir
from parse_nll_facts import missing_facts


def validate_crates(dirs):
    with open("missing-facts.csv", "w") as fp:
        writer = csv.writer(fp)

        writer.writerow(["crate", "missing files"])

        incomplete_count = 0

        for i, p in enumerate(dirs, start=1):
            print(
                f"Validating repo {i}/{len(dirs)}...".ljust(
                    os.get_terminal_size(0).columns),
                end="\r")
            facts_path = p / "nll-facts"
            crate_name = p.stem
            fact_files_missing = missing_facts(facts_path)

            if fact_files_missing:
                writer.writerow([
                    crate_name,
                    ';'.join([str(pth) for pth in fact_files_missing])
                ])
                shutil.rmtree(p)
                incomplete_count += 1
    return incomplete_count


def main():
    crate_paths = inputs_or_workdir()

    for crate_path in crate_paths:
        git_dir = crate_path / ".git/"
        if git_dir.is_dir():
            print(
                f"Cleaing up the Git repo for {crate_path}".ljust(
                    os.get_terminal_size(0).columns),
                end="\r")
            shutil.rmtree(git_dir)

    print("")
    print("validating crate folders...")
    incomplete_count = validate_crates(crate_paths)
    print("")
    if incomplete_count:
        print(f"deleted {incomplete_count} incomplete repos!")


if __name__ == '__main__':
    main()

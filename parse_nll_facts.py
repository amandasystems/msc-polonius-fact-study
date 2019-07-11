#!/usr/bin/env python3
import csv
import os
import re
import resource
import shutil
import sys
from collections import namedtuple
from pathlib import Path

import networkx as nx

from benchmark import inputs_or_workdir, run_command

FACT_NAMES = [
    "borrow_region",
    "cfg_edge",
    "invalidates",
    "killed",
    "outlives",
    "universal_region",
    "var_defined",
    "var_drop_used",
    "var_drops_region",
    "var_initialized_on_exit",
    "var_used",
    "var_uses_region",
]

MAX_MEM_BYTES_SOFT = 8 * (1024**3)
MAX_MEM_BYTES_HARD = 10 * (1024**3)
SOFT_TIMEOUT = "30m"
HARD_TIMEOUT = "35m"

FnFacts = namedtuple("FnFacts", ['name', *FACT_NAMES])
Point = namedtuple("Point", ['level', 'block', 'offset'])


def read_tuples(path):
    assert isinstance(path, Path), "must be a Path"

    with open(path) as fp:
        for line in fp:
            tpl = line\
                .strip()\
                .split("\t")
            if not all(tpl):
                continue
            yield tpl


def read_fn_nll_facts(fn_path):
    assert isinstance(fn_path, Path), "must be a Path"
    #print(f"reading {fn_path}", file=sys.stderr)
    return FnFacts(
        **{
            "name": fn_path.stem,
            **{
                field: list(read_tuples(fn_path / f"{field}.facts"))
                for field in FACT_NAMES
            }
        })


def nll_fn_paths(facts_path):
    assert isinstance(facts_path, Path), "must be a Path"
    return (p for p in facts_path.iterdir()
            if p.is_dir() and not p.stem[0] == ".")


def facts_to_row(fn_facts):
    assert isinstance(fn_facts, FnFacts), "must be a FnFacts instance!"
    return [fn_facts.name, *[len(fact) for fact in fn_facts[1:]]]


def missing_facts(d):
    files_missing = []
    if not d.is_dir():
        return [d]
    for fn_dir in d.iterdir():
        if fn_dir.is_dir() and not fn_dir.stem[0] == ".":
            for fact_name in FACT_NAMES:
                fact_file = fn_dir / Path(f"{fact_name}.facts")
                if not fact_file.is_file():
                    files_missing.append(fact_file)
                    continue

    return files_missing


def unique_loans(fn_facts):
    loans = {l for (_r, l, _p) in fn_facts.borrow_region}
    loans |= {l for (l, _p) in fn_facts.killed}
    loans |= {l for (_p, l) in fn_facts.invalidates}
    return len(loans)


def unique_variables(fn_facts):
    variables = {v for (v, _p) in fn_facts.var_used}
    variables |= {v for (v, _p) in fn_facts.var_defined}
    variables |= {v for (v, _p) in fn_facts.var_drop_used}
    variables |= {v for (v, _r) in fn_facts.var_uses_region}
    variables |= {v for (v, _r) in fn_facts.var_drops_region}
    return len(variables)


def unique_regions(fn_facts):
    regions = {r for (r, _l, _p) in fn_facts.borrow_region}
    regions |= {r for (_v, r) in fn_facts.var_uses_region}
    regions |= {r for (_v, r) in fn_facts.var_drops_region}
    regions |= {r1 for (r1, _r2, p) in fn_facts.outlives}
    regions |= {r2 for (_r1, r2, p) in fn_facts.outlives}
    return len(regions)


def run_external_analysis(crate_path):
    # call myself with different args
    return run_command([
        "timeout", f"--kill-after={HARD_TIMEOUT}", SOFT_TIMEOUT, sys.argv[0],
        str(crate_path)
    ]).stdout


def dirs_to_csv(dirs, out_fp):
    writer = csv.writer(out_fp)
    writer.writerow([
        "program",
        "function",
        *FACT_NAMES,
        "loans",
        "variables",
        "regions",
        "cfg nodes",
        "cfg density",
        "cfg transitivity",
        "cfg number of attracting components",
    ])

    for crate_count, crate_path in enumerate(dirs):
        print(
            f"processing crate #{crate_count}/{len(dirs)}: {crate_path.stem}"\
            .ljust(os.get_terminal_size(0).columns),
            file=sys.stderr,
            end="\r")
        try:
            out_fp.write(run_external_analysis(crate_path))
        except RuntimeError as e:
            print(f"\n====Error\n{e}\n=====", file=sys.stderr)


def parse_point(p):
    """
    Parse a point on the format '"Mid(bb5030[1])"'
    """
    p = p.replace("\\", "").replace("'", "").replace('"', "")
    return Point(*re.match(r"(.+)\(bb(.+)\[(\d+)\]\)", p).groups())


def block_cfg_from_facts(facts):
    assert isinstance(facts, FnFacts), "must be a FnFacts instance!"
    G = nx.DiGraph()

    for edge in facts.cfg_edge:
        start, end = [parse_point(p).block for p in edge]
        if start != end:
            G.add_edge(start, end)
    return G


def main(args):
    crate_fact_list = inputs_or_workdir()

    ok_crates = list(read_crates(crate_fact_list))
    dirs_to_csv(ok_crates, sys.stdout)


def set_ulimit():
    resource.setrlimit(resource.RLIMIT_AS,
                       (MAX_MEM_BYTES_SOFT, MAX_MEM_BYTES_HARD))


def do_analysis(crate_path):
    crate_name = crate_path.stem
    facts_path = crate_path / "nll-facts"
    writer = csv.writer(sys.stdout)
    for fn_path in nll_fn_paths(facts_path):
        fn_facts = read_fn_nll_facts(fn_path)
        cfg = block_cfg_from_facts(fn_facts)
        crate_name = crate_path.stem
        writer.writerow([
            crate_name,
            *facts_to_row(fn_facts),
            unique_loans(fn_facts),
            unique_variables(fn_facts),
            unique_regions(fn_facts),
            cfg.number_of_nodes(),
            nx.density(cfg),
            nx.transitivity(cfg),
            nx.number_attracting_components(cfg),
        ])


def single_main(args):
    """
    This main function is called if we were called like parse_nll_facts
    <path-to-a-crate>.

    """
    set_ulimit()
    do_analysis(Path(sys.argv[1]))


if __name__ == '__main__':
    if len(sys.argv) == 1:
        main(sys.argv)
    else:
        single_main(sys.argv)

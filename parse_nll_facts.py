#!/usr/bin/env python3
import csv
import re
import sys
from collections import namedtuple
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

from benchmark import inputs_or_workdir

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


def read_nll_facts(facts_path):
    assert isinstance(facts_path, Path), "must be a Path"
    return (read_fn_nll_facts(p) for p in facts_path.iterdir()
            if p.is_dir() and not p.stem[0] == ".")


def facts_to_row(fn_facts):
    assert isinstance(fn_facts, FnFacts), "must be a FnFacts instance!"
    return [fn_facts.name, *[len(fact) for fact in fn_facts[1:]]]


def has_all_facts(d):
    for fn_dir in d.iterdir():
        if fn_dir.is_dir() and not fn_dir.stem[0] == ".":
            facts_exist = [(fn_dir / Path(f"{field}.facts")).is_file()
                           for field in FACT_NAMES]
            if not all(facts_exist):
                return False

    return True


def read_dirs(dirs):
    """Read the facts from a list of directories and return tuples of program
    name, facts.

    The expected format of a directory is either some
    path/<program_name>/nll-facts/<function>/<field>.facts, or some path
    <program_name>/<function>/<field>.facts. There can be any number of
    <program_name>s or <function>s.
    """
    for p in dirs:
        facts_path = p / "nll-facts"
        program_name = p.stem
        if facts_path.is_dir() and has_all_facts(facts_path):
            yield (program_name, read_nll_facts(facts_path))
        else:
            print(f"invalid repository: {p}", file=sys.stderr)


def unique_loans(fn_facts):
    loans = set([l for (_r, l, _p) in fn_facts.borrow_region])
    loans |= set([l for (l, _p) in fn_facts.killed])
    loans |= set([l for (_p, l) in fn_facts.invalidates])
    return len(loans)


def unique_variables(fn_facts):
    variables = set([v for (v, _p) in fn_facts.var_used])
    variables |= set([v for (v, _p) in fn_facts.var_defined])
    variables |= set([v for (v, _p) in fn_facts.var_drop_used])
    variables |= set([v for (v, _r) in fn_facts.var_uses_region])
    variables |= set([v for (v, _r) in fn_facts.var_drops_region])
    return len(variables)


def unique_regions(fn_facts):
    regions = set([r for (r, _l, _p) in fn_facts.borrow_region])
    regions |= set([r for (_v, r) in fn_facts.var_uses_region])
    regions |= set([r for (_v, r) in fn_facts.var_drops_region])
    regions |= set([r1 for (r1, _r2, p) in fn_facts.outlives])
    regions |= set([r2 for (_r1, r2, p) in fn_facts.outlives])
    return len(regions)


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

    for program_name, facts in dirs:
        for fn_facts in facts:
            print(
                f"processing {program_name}::{fn_facts.name}", file=sys.stderr)
            cfg = block_cfg_from_facts(fn_facts)
            writer.writerow([
                program_name,
                *facts_to_row(fn_facts),
                unique_loans(fn_facts),
                unique_variables(fn_facts),
                unique_regions(fn_facts),
                cfg.number_of_nodes(),
                nx.density(cfg),
                nx.transitivity(cfg),
                nx.number_attracting_components(cfg),
            ])
        #gc.collect()


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
    dirs_to_csv(read_dirs(crate_fact_list), sys.stdout)


if __name__ == '__main__':
    main(sys.argv)

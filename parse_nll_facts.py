#!/usr/bin/env python3
import csv
import re
import sys
from collections import namedtuple
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

FIELD_NAMES = [
    "cfg_edge",
    "region_live_at",
    "universal_region",
    "var_defined",
    "var_drop_used",
    "var_drops_region",
    "var_used",
    "var_uses_region",
]

FnFacts = namedtuple("FnFacts", ['name', *FIELD_NAMES])
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
    return FnFacts(
        **{
            "name": fn_path.stem,
            **{
                field: list(read_tuples(fn_path / f"{field}.facts"))
                for field in FIELD_NAMES
            }
        })


def read_nll_facts(facts_path):
    assert isinstance(facts_path, Path), "must be a Path"
    return [
        read_fn_nll_facts(p) for p in facts_path.iterdir()
        if p.is_dir() and not p.stem[0] == "."
    ]


def facts_to_row(fn_facts):
    assert isinstance(fn_facts, FnFacts), "must be a FnFacts instance!"
    return [fn_facts.name, *[len(fact) for fact in fn_facts[1:]]]


def read_dirs(dirs):
    """Read the facts from a list of directories and return tuples of program
    name, facts.

    The expected format of a directory is either some
    path/<program_name>/nll-facts/<function>/<field>.facts, or some path
    <program_name>/<function>/<field>.facts. There can be any number of
    <program_name>s or <function>s.
    """
    for p in dirs:
        p = Path(p)
        if not p.is_dir():
            continue
        facts_path = p / "nll-facts"
        program_name = p.stem
        if not facts_path.is_dir():
            facts_path = p
        try:
            yield (p.stem, read_nll_facts(facts_path))
        except FileNotFoundError:
            continue


def dirs_to_csv(dirs, out_fp):
    writer = csv.writer(out_fp)
    writer.writerow(["program", "function", *FIELD_NAMES])
    for program_name, facts in dirs:
        for fn_facts in facts:
            writer.writerow([program_name, *facts_to_row(fn_facts)])


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
    program_data = list(read_dirs(args[1:]))
    dirs_to_csv(program_data, sys.stdout)
    #G = block_cfg_from_facts(program_data[0][1][0])
    #nx.draw(G, with_labels=True, font_weight='bold')
    #plt.show()


if __name__ == '__main__':
    main(sys.argv)

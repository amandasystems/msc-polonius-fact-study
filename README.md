These are some utilities I made to study Polonius' performance for my Master's
thesis.

In general, the order is as follows: first you run `find-repos.py` to scrape
repositories from crates.io or Github and store them in `repositories.seen.txt`.
Then you run `find-repos.py` again to move those to the blacklist
`blacklist.txt` (if they don't compile) or whitelist `repositories.txt` (if they
do).

`collect-facts.py` uses `repositories.txt` to check out the repositories and
collect the `nll-facts` from them and clean out all other files (warning:
poorly!). These facts are then used by `benchmark-solving.py`, which benchmarks
Polonius' runtime solving the facts, and `parse_nll_facts.py`, which generates
statistics on the input data, including some light graph analysis on the CFG
using networkx.

In practice, you probably want to use the Makefile rules.

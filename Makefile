all: repo-stats.csv

# Find new repositories to test
.PRECIOUS: repositories.seen.txt
repositories.seen.txt:
	time ./find-repos.py "get-new"

# Build a list of ok repositores (and a blacklist)
.PRECIOUS: repositories.txt
repositories.txt: repositories.seen.txt
	time ./find-repos.py "empty-inbox"

# Generate Polonius inputs for repositories.txt
work/.sentinel: repositories.txt
	./get-repos.py repositories.txt
	./cleanup-repos.py
	touch work/.sentinel

# Benchmark solve-time on the fetched repositories
.PRECIOUS: solve.csv
solve.csv: work/.sentinel
	 time ./benchmark-solving.py > solve.csv

# Compute summary statistics on each repository's facts
.PRECIOUS: facts.csv
facts.csv: work/.sentinel
	 time ./parse_nll_facts.py > facts.csv

.PHONY:
update-data:
	scp "barbelith.local:~/local-benchmark/solve.csv" .
	scp "barbelith.local:~/local-benchmark/facts.csv" .

# Join facts.csv to solve.csv. This select statement is just for removing the
# duplicated columns from the join:
repo-stats.csv: solve.csv facts.csv
	xsv join program,function solve.csv program,function facts.csv \
		| xsv select 1-5,8-26 > $@

.PHONY:
clean:
	rm -rf work/.sentinel missing-facts.csv repo-errors.log repo-ok.csv fetched-repos.log
	./cleanup-repos.py

.PHONY:
veryclean: clean
	rm -rf work/*

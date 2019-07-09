all: repo-stats.csv

.PHONY:
build-facts:
	./get-repos.py repositories.txt


.PHONY:
solve.csv:
	 ./benchmark-solving.py > solve.csv

.PHONY:
facts.csv:
	  ./parse_nll_facts.py > facts.csv

.PHONY:
update-data:
	scp "barbelith.local:~/local-benchmark/solve.csv" .
	scp "barbelith.local:~/local-benchmark/facts.csv" .

# This select statement is just for removing the duplicated columns from the
# join:
repo-stats.csv: solve.csv facts.csv
	xsv join program,function solve.csv program,function facts.csv \
		| xsv select 1-5,8-26 > $@

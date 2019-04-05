#!/usr/bin/env python3
import itertools
import time

from github import Github

from benchmark import ALGORITHMS, clone_repo, run_experiment

with open("blacklist.txt") as fp:
    BLACKLIST = set([l.strip() for l in fp.readlines()])

with open("repositories.txt") as fp:
    WHITELIST = set([l.strip() for l in fp.readlines()])


def get_crates_io_repos():
    pass


def get_github_repos():
    repo_iterator = Github().search_repositories(
        sort="stars", order="desc", query="language:rust")
    return (r.clone_url for r in repo_iterator if verify_repo(r.clone_url))


def verify_repo(url):
    if url in BLACKLIST:
        print(f"skipping blacklisted url {url}...")
        return False
    elif url in WHITELIST:
        print(f"skipping verification of whitelisted url {url}...")
        return True
    try:
        path = clone_repo(url)
        results = run_experiment(ALGORITHMS[1], path)
    except Exception as e:
        print(f"repo {url} died with {e}, skipping and blacklisting...")
        BLACKLIST.add(url)
        with open("blacklist.txt", "a") as fp:
            fp.write(f"{url}\n")
        return False
    print(f"repo {url} compiled with results {results}")
    return True


if __name__ == '__main__':
    count = 0
    with open("repositories.txt", "w") as fp:
        for repo_url in get_github_repos():
            fp.write(f"{repo_url}\n")
            fp.flush()
            if count % 10 == 0:
                print("Sleeping...")
                time.sleep(5)
            count += 1

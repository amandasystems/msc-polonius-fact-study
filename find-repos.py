#!/usr/bin/env python3
import itertools
import shutil
import time

import requests
from github import Github

from benchmark import ALGORITHMS, blacklist_repo, clone_repo, run_experiment

with open("blacklist.txt") as fp:
    BLACKLIST = set([l.strip() for l in fp.readlines()])

with open("repositories.txt") as fp:
    WHITELIST = set([l.strip() for l in fp.readlines()])

with open("repositories.seen.txt") as fp:
    SEEN = set([l.strip() for l in fp.readlines()])

EMA = None
ALPHA = 0.5
CRATES_URL = "https://crates.io/api/v1/crates"


def get_crates():
    for i in itertools.count(start=1):
        params = {"page": i, "per_page": 20, "sort": "recent_downloads"}
        response = requests.get(CRATES_URL, params=params)
        response.raise_for_status()
        if response.json()['meta']['total'] == 0:
            break
        for crate in response.json()['crates']:
            yield crate


def get_crates_io_repos():
    def extract_url(crate):
        return crate['repository'].replace("/tree/master/", "").rstrip("/")

    return (extract_url(c) for c in get_crates() if c['repository'])


def get_github_repos():
    gh = Github()
    repo_iterator = gh.search_repositories(
        sort="stars", order="desc", query="language:rust")

    rate_limit_remaining = gh.get_rate_limit().search.remaining
    for i, r in enumerate(repo_iterator):
        if i % 10 == 0:
            rate_limit_remaining = gh.get_rate_limit().search.remaining

        while rate_limit_remaining <= 1:
            rate_limit_remaining = gh.get_rate_limit().search.remaining
            remaining = gh.rate_limiting_resettime - time.time()
            print("Hitting rate limit for GitHub!")
            yield None

        yield r.clone_url


def git_url_in_set(url, url_set):
    return url in url_set or "{url}.git" in url_set or url.replace(
        ".git", "") in url_set


def verify_repo(url):
    global EMA
    try:
        path = clone_repo(url)
    except RuntimeError:
        print(f"verify_repo: clone error for {url}")
        return False
    try:
        results = run_experiment(ALGORITHMS[1], path)
        EMA = results if EMA is None else ALPHA * results + (1 - ALPHA) * EMA
    except RuntimeError as e:
        print(
            f"====\nrepo {url} died:\n---\n{e}\n---\nskipping and blacklisting\n===="
        )
        return False
    finally:
        assert path.stem != "work", "Clone path is weird???"
        shutil.rmtree(path)

    print(f"repo {url} compiled with results {results}, EMA: {EMA}")
    return True


def interleave_iterators(iter_a, iter_b):
    for a, b in itertools.zip_longest(iter_a, iter_b):
        if a is not None:
            yield a
        if b is not None:
            yield b


def whitelist_repo(repo_url):
    global WHITELIST
    WHITELIST.add(url)
    with open("repositories.txt", "a") as fp:
        fp.write(f"{repo_url}\n")
        fp.flush()


def seen_repo(repo_url):
    global SEEN
    SEEN.add(url)
    with open("repositories.seen.txt", "a") as fp:
        fp.write(f"{repo_url}\n")
        fp.flush()


def empty_inbox():
    print(f"Going through {len(SEEN)} collected unverified repos")
    try:
        for repo_url in SEEN:
            if not git_url_in_set(repo_url, BLACKLIST) and not git_url_in_set(
                    repo_url, WHITELIST):
                verify_and_whitelist(repo_url)
    finally:
        print("Dumping repositories back...")
        with open("repositories.seen.txt", "w") as fp:
            for url in sorted(SEEN):
                if not git_url_in_set(repo_url,
                                      BLACKLIST) and not git_url_in_set(
                                          repo_url, WHITELIST):
                    fp.write(f"{url}\n")


def verify_and_whitelist(repo_url):
    if verify_repo(repo_url):
        print(f"whitelisting: {repo_url}")
        whitelist_repo(repo_url)
    else:
        print(f"blacklisting: {repo_url}")
        blacklist_repo(repo_url)


if __name__ == '__main__':
    count = 0
    with open("repositories.txt", "w") as fp:
        for url in sorted(WHITELIST):
            fp.write(f"{url}\n")

    SEEN -= WHITELIST
    SEEN -= BLACKLIST

    ## go through the backlog from .seen.txt and verify_and_whitelist
    if SEEN:
        empty_inbox()
        exit(0)

    for repo_url in interleave_iterators(get_github_repos(),
                                         get_crates_io_repos()):
        if not repo_url:
            continue
        if git_url_in_set(repo_url, BLACKLIST):
            print(f"skipping blacklisted url {repo_url}...")
            continue
        elif git_url_in_set(repo_url, WHITELIST):
            print(f"skipping already-verified {repo_url}")
            continue
        elif git_url_in_set(repo_url, SEEN):
            print(f"skipping already-seen {repo_url}")
            continue

        seen_repo(repo_url)

        if count % 15 == 0:
            print("Sleeping...")
            time.sleep(10)
            count += 1

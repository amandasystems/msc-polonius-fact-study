#!/usr/bin/env python3

from benchmark import drop_git_ending
from pathlib import Path
import sys


def username_and_repo_name(url):
    components = url.split("/")
    username, repo_name = components[-2:]
    return (username, repo_name)


def repo_url_to_id(url):
    url = drop_git_ending(url)
    if "github.com" in url:
        return ("github", *username_and_repo_name(url))
    if "gitlab.com" in url:
        return ("gitlab", *username_and_repo_name(url))
    if "bitbucket.org" in url:
        return ("bitbucket", *username_and_repo_name(url))

    return url


def main():
    target_file = Path(sys.argv[1])

    with open("blacklist.txt") as blacklist_fp:
        blacklist_ids = {
            repo_url_to_id(url.strip())
            for url in blacklist_fp if url.strip()
        }

    deduped_whitelist = list()
    seen_whitelist_ids = set()

    with open(target_file) as whitelist_fp:
        for url in whitelist_fp:
            url = url.strip()
            if not url:
                continue
            url_id = repo_url_to_id(url)
            if url_id in blacklist_ids:
                print(f"{url_id} is blacklisted!")
                continue
            if url_id in seen_whitelist_ids:
                print(f"{url_id} is a duplicate!")
                continue

            seen_whitelist_ids.add(url_id)
            deduped_whitelist.append((url_id, url))

    with open(target_file, "w") as whitelist_fp:
        whitelist_fp.writelines((f"{url}\n" for _, url in deduped_whitelist))

    print(f"Wrote {len(deduped_whitelist)} urls!")


if __name__ == '__main__':
    main()

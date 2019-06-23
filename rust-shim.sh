#!/bin/bash

echo "$@" >> ~/rust-commands.log

rustup run nightly "$@"


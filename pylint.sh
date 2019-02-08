#!/bin/sh

find . -name '*.py' | xargs python3 -m pylint

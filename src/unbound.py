#!/usr/bin/env python
#
# igcollect - Stats for Unbound DNS cache/resolver
#
# Copyright (c) 2016 InnoGames GmbH
#

from __future__ import print_function
from argparse import ArgumentParser
from subprocess import Popen, PIPE
from time import time


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--prefix', default='unbound')
    return parser.parse_args()


def parse_unbound_stats():
    out = Popen(('/usr/sbin/unbound-control', 'stats'), stdout=PIPE).\
        stdout.read().splitlines()

    return {
        key.replace('total.', ''): val for key, val in (
            stat.split('=') for stat in out
        ) if key.startswith('total.')
    }


def main():
    args = parse_args()
    template = args.prefix + '.{} {} ' + str(int(time()))
    for key, val in parse_unbound_stats().items():
        print(template.format(key, val))


if __name__ == '__main__':
    main()

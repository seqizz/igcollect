#!/usr/bin/env python
#
# igcollect - Linux network
#
# Copyright (c) 2018, InnoGames GmbH
#

from argparse import ArgumentParser
from time import time
import os


class InterfaceStatistics(object):
    '''
        Supported types of interfaces for a metrics sending
        If there is more than one conditions they multipied by AND
    '''
    NET_TYPES = {
        'bond': {
            'bonding': '_check_dir',
        },
        'bond_slave': {
            'bonding_slave': '_check_dir',
        },
        'bridge': {
            'bridge': '_check_dir',
        },
        'bridge_slave': {
            'brport': '_check_dir',
        },
        'general_slave': {
            'master': '_check_symlink',
        },
        'lo': {
            ("772", ): "_check_type",
        },
        'ovs-br0': {
            'br0': '_check_name',
        },
        'ovs-system': {
            'ovs-system': '_check_name',
        },
        'phys': {
            'device': '_check_dir',
        },
        'tunnel': {
            # any of tuple member could be a type
            ("768", "776"): '_check_type',
        },
        'vlan': {
            "DEVTYPE=vlan": '_check_uevent',
        },
    }
    _scn = '/sys/class/net'

    def __init__(self, included_types=[]):
        self.included_types = included_types
        self.netdev_stat = {}

    def _check_dir(self, dev, directory):
        return os.path.isdir(os.path.join(self._scn, dev, directory))

    def _check_name(self, dev, name):
        return dev == name

    def _check_symlink(self, dev, symlink):
        return os.path.isdir(os.path.join(self._scn, dev, symlink))

    def _check_type(self, dev, types):
        _is_tunnel = False
        with open(os.path.join(self._scn, dev, 'type'), 'r') as ft:
            dev_type = ft.readline().strip()
            for t in types:
                if dev_type == t:
                    _is_tunnel = True
        return _is_tunnel

    def _check_uevent(self, dev, string):
        with open(os.path.join(self._scn, dev, 'uevent'), 'r') as ue:
            return string in ue.read()

    def _read_stat(self, dev, param):
        with open(os.path.join(self._scn, dev, 'statistics', param)) as fp:
            return int(fp.read().strip())

    def get_interfaces(self):
        for dev in os.listdir(self._scn):
            if self.included_types:
                for i_type in self.included_types:
                    checks = self.NET_TYPES[i_type]
                    results = []
                    for arg, check in checks.items():
                        method = getattr(self, check)
                        results.append(method(dev, arg))
                    if False not in results:
                        self.netdev_stat[dev] = {}
            else:
                self.netdev_stat[dev] = {}

    def fill_metrics(self):
        self.timestamp = int(time())
        metric_names = {
            'bytesIn': [
                'rx_bytes'
            ],
            'bytesOut': [
                'tx_bytes'
            ],
            'pktsIn': [
                'rx_packets'
            ],
            'pktsOut': [
                'tx_packets'
            ],
            'errsIn': [
                'rx_errors'
            ],
            'errsOut': [
                'tx_errors'
            ],
            'dropIn': [
                'rx_dropped',
                'rx_missed_errors'
            ],
            'dropOut': [
                'tx_dropped'
            ],
            'fifoIn': [
                'rx_fifo_errors'
            ],
            'fifoOut': [
                'tx_fifo_errors'
            ],
            'frameIn': [
                'rx_length_errors',
                'rx_over_errors',
                'rx_crc_errors',
                'rx_frame_errors'
            ],
            'collsOut': [
                'collisions'
            ],
            'carrierOut': [
                'tx_carrier_errors',
                'tx_aborted_errors',
                'tx_window_errors',
                'tx_heartbeat_errors'
            ],
        }
        for dev in self.netdev_stat:
            for m in metric_names:
                self.netdev_stat[dev][m] = 0
                for param in metric_names[m]:
                    self.netdev_stat[dev][m] += self._read_stat(dev, param)

    def print_metrics(self, prefix):
        for dev in self.netdev_stat:
            for metric in self.netdev_stat[dev]:
                print('{}.{}.{} {} {}'.format(
                    prefix, dev.replace('.', '_'), metric,
                    self.netdev_stat[dev][metric], self.timestamp
                ))


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('-p', '--prefix', default='network')
    parser.add_argument('-e', '--enabled-types', action='append',
                        default=[],
                        choices=InterfaceStatistics.NET_TYPES.keys(),
                        help='list of enabled interfaces')
    return parser.parse_args()


def main():
    args = parse_args()
    ns = InterfaceStatistics(args.enabled_types)
    ns.get_interfaces()
    ns.fill_metrics()
    ns.print_metrics(args.prefix)


if __name__ == '__main__':
    main()

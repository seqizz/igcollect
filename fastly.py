#!/usr/bin/env python
#
# igcollect - Fastly CDN
#
# Copyright (c) 2016, InnoGames GmbH
#

import sys
import json
import urllib2
import argparse
import time

GRAPHITE_PREFIX = 'cdn.fastly'
FASTLY_BASE_URL = 'https://api.fastly.com'
AVG_KEYS = ('hit_ratio', 'hits_time', 'miss_time')
SUM_KEYS = (
    'body_size', 'bandwidth', 'errors', 'header_size', 'hits', 'miss', 'pass',
    'pipe', 'requests', 'status_1xx', 'status_200', 'status_204', 'status_2xx',
    'status_301', 'status_302', 'status_304', 'status_3xx', 'status_4xx',
    'status_503', 'status_5xx', 'uncacheable')
API_KEY = None


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-k', '--key', dest='apikey', required=True,
                        help='here you can provided the Fastly API Key this '
                             'will replace one contained in the script')
    parser.add_argument('-s', '--service', dest='service',
                        help='will only query the one service, if omitted all '
                             'services will be queried')
    parser.add_argument('-t', '--to', dest='end_time', type=int,
                        help='until when do you want to print the data')
    parser.add_argument('-f', '--from', dest='start_time', type=int,
                        help='start of the data printed')
    parser.add_argument('-i', '--interval', dest='interval',
                        choices=['minute', 'hour', 'day'], default='minute',
                        help='interval the query should return the data in')
    parser.add_argument('-l', '--list', action='store_true', dest='show_list',
                        help='Shows you available services')
    parser.add_argument('-r', '--regions', action='store_true', dest='regions',
                        help='Shows you the currently available regions')
    return parser.parse_args()


def main(args):
    global API_KEY
    API_KEY = args.apikey

    if not API_KEY:
        print('you have to specify a api key with --key parameter')
        sys.exit(1)

    # Just show a list of possible services
    if args.show_list:
        all_services = get_services()
        for service_id, service_name in all_services.items():
            print('{}:{}'.format(service_name, service_id))
        sys.exit(0)

    # Query the API for all regions and print the list of them
    if args.regions:
        print(get_regions())
        sys.exit(0)

    # region Setting the from and to timestamps
    interval = args.interval
    now = int(time.time())

    # Always set the end time to now - 30 minutes to not get rate limited.
    # If you want more recent data, you need to specify start and end time
    # using the -f and -t parameters.
    if args.end_time:
        end_time = args.end_time
    else:
        end_time = now - 1800  # 30 * 60

    if args.start_time:
        start_time = args.start_time
    else:
        # Select reasonable default intervals for the query. For minutely
        # interval, we return hours worth of data; for hourly, we return
        # one day; and for a daily interval, we'll return a month (30 days).
        if interval == 'minute':
            start_time = now - 3600  # 60 * 60
        elif interval == 'hour':
            start_time = now - 86400  # 24 * 60 60
        elif interval == 'day':
            start_time = now - 3456000  # 30 * 24 * 60 * 60
        else:
            start_time = now - 3600
    # endregion Setting the from and to timestamps

    service = None
    if args.service:
        service = get_service_by_name(args.service)
        if not service:
            print('Unknown Service: {0:s}'.format(args.service))
            sys.exit(1)
        all_services = {service: args.service}
    else:
        all_services = get_services()

    string = GRAPHITE_PREFIX + '.{service}.{region}.{{value}}'
    regions = get_regions()
    for region in regions:
        try:
            stats_data = get_service_data(service=service, region=region,
                                          cfrom=start_time,
                                          to=end_time, interval=interval)
        except BaseException as e:
            print(e)
            continue

        for service, data in stats_data.items():
            if service not in all_services:
                continue

            service_name = all_services[service]
            service_name = service_name.replace(' ', '_')
            try:
                output = string.format(service=service_name, region=region)

                for entry in data:
                    for key in entry:
                        value = format_key(entry, key)
                        if not value:
                            continue
                        print(output.format(value=value))

            except BaseException as e:
                print(e)
                continue


def get_service_data(service=None, region=None, cfrom=None, to=None,
                     interval=None):
    query = ''
    if region:
        query += 'region={}&'.format(region)
    if cfrom:
        query += 'from={}&'.format(cfrom)
    if to:
        query += 'to={}&'.format(to)
    if to:
        query += 'by={}&'.format(interval)

    if not service:
        url = '/stats?' + query
        services_data = get_data(url)['data']
    else:
        url = '/stats/service/{s}?{q}'.format(s=service, q=query)
        services_data = {service: get_data(url)['data']}

    return {service_id: data for service_id, data in services_data.items()}


def get_services():
    """Query the services API"""
    service_data = get_data('/service')
    return {s['id']: s['name'] for s in service_data}


def get_service_by_name(name):
    """Search for a service by name"""
    try:
        service_info = get_data('/service/search?name={:s}'.format(name))
        if service_info:
            return service_info['id']
    except BaseException as e:
        print(e)


def get_regions():
    """Query the regions API"""
    try:
        return get_data('/stats/regions')['data']
    except BaseException as e:
        # If the api is not available return a default set of regions
        print(e)
        return ('africa', 'anzac', 'asia', 'europe', 'latam', 'usa')


def get_data(fastly_url):
    url = FASTLY_BASE_URL + fastly_url
    req = urllib2.Request(url=url, headers={'Fastly-Key': API_KEY})
    fd = urllib2.urlopen(req, timeout=10)
    return json.loads(fd.read())


def format_key(entry, key):
    format_string = '{key}{count} {value} {start_time}'

    # These values should be summarized by graphite using the
    # average function later
    if key in AVG_KEYS:
        return format_string.format(key=key, count='',
                                    value=str(float(entry[key])),
                                    start_time=str(entry['start_time']))

    # These values contain an amount for an interval and
    # therefore need to be summarized in graphite using the
    # sum() function, in the default behavior this is done for
    # all metrics ending in .count therefore we'll amend it
    # here.
    if key in SUM_KEYS:
        return format_string.format(key=key, count='.count',
                                    value=str(float(entry[key])),
                                    start_time=str(entry['start_time']))


if __name__ == '__main__':
    main(parse_args())

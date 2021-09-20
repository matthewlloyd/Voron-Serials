#!/usr/bin/python3

import datetime

def format_utc(utc):
    return datetime.utcfromtimestamp(utc).strftime('%Y-%m-%d %H:%M:%S %Z')

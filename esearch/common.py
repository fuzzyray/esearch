#!/usr/bin/python
#
# Some functions for esearch,
# eupdatedb and esync.
#
# Author: David Peter <davidpeter@web.de>
#

from __future__ import print_function

import sys
from portage import catpkgsplit
from portage.output import red, green

NORMAL =  1
COMPACT = 2
VERBOSE = 3
EBUILDS = 4
OWN =     5


SyncOpts = {
    "sync": "EMERGE_DEFAULT_OPTS=\"\" /usr/bin/emerge --sync",
    "webrsync": "EMERGE_DEFAULT_OPTS=\"\" /usr/sbin/emerge-webrsync",
    "delta-webrsync": "EMERGE_DEFAULT_OPTS=\"\" /usr/bin/emerge-delta-webrsync -u",
    "metadata": "EMERGE_DEFAULT_OPTS=\"\" /usr/bin/emerge --metadata"
}

logfile_sync =  "/var/log/emerge-sync.log"
tmp_path = "/tmp"
tmp_prefix = tmp_path + "/esync"


CONFIG = {
    'esearchdbdir': "/var/cache/edb/",
    'esearchdbfile': "esearchdb.py",
    'tmpfile': tmp_path + "/esearchdb.py.tmp",
    # -1==quiet, 0==normal, +1==verbose
    'verbose': 0,
    # current esearch database version
    'needdbversion': 63,
    'stdout': sys.stdout,
    'stderr': sys.stderr,
    'outputm': NORMAL,
    'searchdesc': False,
    'fullname': False,
    'pattern': False,
    'instonly': False,
    'notinst': False,
    'found_in_overlay': False,
    'syncprogram': SyncOpts['sync'],
    'eoptions': '',
    'eupdatedb_extra_options': '',
    # too time comsuming to import & get it from portage here
    # just set a default
    'showtitles': True,
    }


version = 'git-0.8'


# get the version from a string like 'foo-bar/bar-0.4_rc2-r1'
def pkg_version(pkg):
    # from /usr/bin/emerge
    if len(pkg) > 1:
        parts = catpkgsplit(pkg)
        if parts == None:
            return ""

        if parts[3] != 'r0':
            version = parts[2] + "-" + parts[3]
        else:
            version = parts[2]
        return version
    else:
        return False


def outofdateerror(stderr=CONFIG['stderr']):
    error("The version of the esearch index is out of date, please run " +
        green("eupdatedb"), stderr=stderr)


def error(msg, fatal=True, stderr=CONFIG['stderr']):
    print(red(" * Error:"), msg, file=stderr)
    print('', file=stderr)
    if fatal:
        sys.exit(1)

#!/usr/bin/python -u
#
# 'python -u' for unbuffered output, so you can call
#   $ esync | tee esync.log
#
# This script imports the current esearch index,
# calls `emerge sync` and `eupdatedb` and then
# shows the packages which were updated or added
# during the sync.
#
# Author: David Peter <davidpeter@web.de>
#


from __future__ import print_function

import os
import sys
from getopt import getopt, GetoptError

#sys.path.insert(0, "/usr/lib/portage/pym")

import portage
try:
    from portage.output import red, green, bold, darkgreen, nocolor, xtermTitle
except ImportError:
    print("Critical: portage imports failed!")
    sys.exit(1)

from esearch.common import (CONFIG, SyncOpts, outofdateerror, logfile_sync,
    tmp_path, tmp_prefix, version, EPREFIX, COMPACT)
from esearch.update import updatedb
from esearch.search import searchdb

sys.path.append(tmp_path)


def usage():
    print("esync (%s) - Calls 'emerge sync' and 'eupdatedb' and shows updates" \
        % version)
    print("")
    print(bold("Usage:"), "esync [", darkgreen("options"), "]")
    print(bold("Options:"))
    print(darkgreen("  --help") + ", " + darkgreen("-h"))
    print("    Print this help message")
    print("")
    print(darkgreen("  --webrsync") + ", " + darkgreen("-w"))
    print("    Use 'emerge-webrsync' instead of 'emerge --sync'")
    print("")
    print(darkgreen("  --delta-webrsync") + ", " + darkgreen("-d"))
    print("    Use 'emerge-delta-webrsync' instead of 'emerge --sync'")
    print("")
    print(darkgreen("  --metadata") + ", " + darkgreen("-m"))
    print("    Use 'emerge --metadata' instead of 'emerge --sync'")
    print("")
    print(darkgreen("  --nocolor") + ", " + darkgreen("-n"))
    print("    Don't use ANSI codes for colored output")
    print("")
    print(darkgreen("  --quiet") + ", " + darkgreen("-q"))
    print("    Less output (implies --nospinner)")
    print("")
    print(darkgreen("  --verbose") + ", " + darkgreen("-v"))
    print("    Verbose output")
    print("")
    print(darkgreen("  --nospinner") + ", " + darkgreen("-s"))
    print("    Don't display the remaining index count")

    sys.exit(0)


def parseopts(opts, config=None):

    if config is None:
        config = CONFIG

    # reset the default
    config['showtitles'] = "notitles" not in portage.features
    for a in opts[0]:
        arg = a[0]
        if arg in ("-h", "--help"):
            usage()
        elif arg in ("-w", "--webrsync"):
            config['syncprogram'] = SyncOpts["webrsync"]
        elif arg in ("-d", "--delta-webrsync"):
            config['syncprogram'] = SyncOpts["delta-webrsync"]
        elif arg in ("-m", "--metadata"):
            config['syncprogram'] = SyncOpts["metadata"]
        elif arg in ("-n", "--nocolor"):
            config['eoptions'] = "-n"
            nocolor()
            config['showtitles'] = False
        elif arg in ("-q", "--quiet"):
            config['eupdatedb_extra_options'] = "-q"
            config['verbose'] = -1
        elif arg in ("-v", "--verbose"):
            config['verbose'] = 1
        elif arg in ("-s", "--nospinner"):
            config['eupdatedb_extra_options'] = "-q"
    return config


def emsg(msg, config):
    if config['showtitles']:
        xtermTitle(msg)
    if config['verbose'] == -1:
        return
    print(green(" *"), msg)


def gettree(tree, config):
    emsg("Importing " + tree + " portage tree", config)
    if '.pyc' in config['esearchdbfile']:
        dbfile = config['esearchdbfile']
    else:
        dbfile = config['esearchdbfile'] + 'c'
    try:
        target = tmp_prefix + tree + "tree.pyc"
        if os.path.exists(target):
            os.unlink(target)
        os.symlink(os.path.join(config['esearchdbdir'], dbfile), target)
    except OSError as e:
        if e.errno != 17:
            print(e)
            print("")
            sys.exit(1)
    try:
        if tree == "old":
            from esyncoldtree import db
            try:
                from esyncoldtree import dbversion
                if dbversion < config['needdbversion']:
                    outofdateerror()
            except ImportError:
                outofdateerror()
        else:
            from esyncnewtree import db
    except ImportError:
        print(red(" * Error:"), "Could not find esearch-index. Please run", \
            green("eupdatedb"), "as root first")
        print("")
        sys.exit(1)
    os.unlink(target)
    return db


def sync(config):

    tree_old = gettree("old", config)

    if config['verbose'] >= 0:
        emsg("Doing '" + config['syncprogram'] + "' now", config)

    if config['verbose'] == 1:
        errorcode = os.system(config['syncprogram'] + " | tee " + logfile_sync + " 2>&1")
    else:
        errorcode = os.system(config['syncprogram'] + " > " + logfile_sync + " 2>&1")

    if errorcode != 0:
        print(red(" * Error:"),\
            "'" + config['syncprogram'] + "'",\
             "failed, see", logfile_sync, "for errors")
        print("")
        return False

    if config['verbose'] >= 0:
        print("")
        emsg("Doing 'eupdatedb' now", config)
        print("")

    # run eupdatedb natively
    success = updatedb(config)
    if not success:
        print("")
        print(red(" * Error:"), "running updatedb failed")
        return False

    if config['verbose'] >= 0:
        print("")

    tree_new = gettree("new", config)

    emsg("Preparing databases", config)

    new = {}
    for pkg in tree_new:
        new[pkg[1]] = pkg[3]

    old = {}
    for pkg in tree_old:
        old[pkg[1]] = pkg[3]

    emsg("Searching for changes", config)
    print("")

    # alphabetic sort
    items = list(new.items())
    items.sort(lambda x, y: cmp(x[0], y[0]))

    old_keys = list(old.keys())

    haspkg = False

    # update our config to run searchdb
    config['outputm'] = COMPACT
    config['fullname'] = True

    for (pkg, version) in items:
        if (pkg not in old_keys) or (old[pkg] != new[pkg]):
            success = searchdb(config, pkg, new)
            haspkg = True

    if not haspkg:
        emsg("No updates found", config)
    return True


def main():
    try:
        opts = getopt(sys.argv[1:], "hwdmnqvs",
            ["help", "webrsync", "delta-webrsync",
            "nocolor", "verbose", "metadata", "nospinner",
            "quiet"])
    except GetoptError as error:
        print(red(" * Error:"), error, "(see", darkgreen("--help"), "for all options)")
        print()
        sys.exit(1)

    config = parseopts(opts)
    success = sync(config)
    # sys.exit() values are opposite T/F
    sys.exit(not success)


if __name__ == '__main__':

    main()

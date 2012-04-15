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

from esearch.common import (CONFIG, SyncOpts, error, outofdateerror,
    logfile_sync, laymanlog_sync, tmp_path, tmp_prefix, version,
    EPREFIX, COMPACT, warn)
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
    print(darkgreen("  --layman-sync") + ", " + darkgreen("-l"))
    print("    Use layman to sync any installed overlays, then sync the main tree")
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
        elif arg in ('-l', '--layman-sync'):
            config['layman-sync'] = True
        elif arg in ("-n", "--nocolor"):
            nocolor()
            config["nocolor"] = True
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
        ext = ".pyc"
    else:
        ext = ".py"
    try:
        target = tmp_prefix + tree + "tree" + ext
        if os.path.exists(target):
            os.unlink(target)
        os.symlink(os.path.join(config['esearchdbdir'], config['esearchdbfile']), target)
    except OSError as e:
        if e.errno != 17:
            error(str(e), fatal=True)
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
        error("Could not find " + tree +
            "esearch-index. Please run " +
            green("eupdatedb") + " as root first", fatal=True)
    os.unlink(target)
    return db


def layman_sync(config):
    # check for an available layman api
    try:
        from layman import Layman
    except ImportError:
        # run it in a subprocess
        if config['verbose'] >= 0:
            emsg("Doing " + config['layman-cmd'] +" now", config)

        if config['verbose'] == 1:
            errorcode = os.system(config['layman-cmd'] + " | tee " +
                laymanlog_sync + " 2>&1")
        else:
            errorcode = os.system(config['layman-cmd'] + " > " +
                laymanlog_sync + " 2>&1")

        if errorcode != 0:
            error("'" + config['layman-cmd'] + "' failed, see " +
                laymanlog_sync + " for errors", fatal=False)
            print("")
            return False, []
        return True, []
    # run the api to sync
    emsg("Running the Layman API", config)
    if config['verbose']<1:
        quietness=0
    else:
        quietness=4
    _layman = Layman(stdout=config['stdout'], stderr=config['stderr'],
        quiet=config['verbose']<1, quietness=quietness,
        verbose=config['verbose']>0, nocolor=config['nocolor'])
    repos = _layman.get_installed()
    success = _layman.sync(repos, output_results=config['verbose']>0)
    warnings = _layman.sync_results[1]
    if not success:
        error("Syncing with the layman api "\
             "failed.\n   Failures were:", fatal=False)
        fatals = _layman.sync_results[2]
        for ovl, result in fatals:
            error(result, fatal=False)

    return success, warnings


def sync(config):

    tree_old = gettree("old", config)

    if config['layman-sync']:
        success, warnings = layman_sync(config)
        if not success:
            return False

    if config['verbose'] >= 0:
        emsg("Doing '" + config['syncprogram'] + "' now", config)

    if config['verbose'] == 1:
        errorcode = os.system(config['syncprogram'] + " | tee " +
            logfile_sync + " 2>&1")
    else:
        errorcode = os.system(config['syncprogram'] + " > " +
            logfile_sync + " 2>&1")

    if errorcode != 0:
        error("'" + config['syncprogram'] + "' failed, see " +
            logfile_sync + " for errors", fatal=False)
        return False

    if config['verbose'] >= 0:
        print("")
        emsg("Doing 'eupdatedb' now", config)
        print("")

    # run eupdatedb natively
    success = updatedb(config)
    if not success:
        print("")
        error("running updatedb failed", fatal=False)
        return False

    if config['verbose'] >= 0:
        print("")

    # uncomment the sys.path line below if you comment out the
    # emerge sync code section for testing
    #sys.path.insert(0, config['esearchdbdir'])
    from esearchdb import db as tree_new

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
    items.sort(key=lambda x: x[0])

    old_keys = list(old.keys())

    # update our config to run searchdb
    config['outputm'] = COMPACT
    config['fullname'] = True

    #individual pkgname search method
    haspkgs = False
    for (pkg, version) in items:
        if (pkg not in old_keys) or (old[pkg] != new[pkg]):
            success = searchdb(config, ["^" + pkg + "$"], tree_new)
            haspkgs = True

    if not haspkgs:
        emsg("No updates found", config)
        success = True

    if warnings:
        print("", file=config['stdout'])
        for ovl, result in warnings:
            warn(result)

    # multiple pkgname search method
    # build our re search list
    #pkg_patterns = []
    #for (pkg, version) in items:
        #if (pkg not in old_keys) or (old[pkg] != new[pkg]):
            #pkg_patterns.append("^" + pkg + "$")

    #if pkg_patterns == []:
        #emsg("No updates found", config)
        #success = True
    #else:
        #success = searchdb(config, pkg_patterns, tree_new)

    return success


def main():
    try:
        opts = getopt(sys.argv[1:], "hwdlmnqvs",
            ["help", "webrsync", "delta-webrsync", "layman-sync",
            "nocolor", "verbose", "metadata", "nospinner",
            "quiet"])
    except GetoptError as error:
        error(str(error) + " (see" + darkgreen("--help") + " for all options)")
    config = parseopts(opts)
    success = sync(config)
    # sys.exit() values are opposite T/F
    sys.exit(not success)


if __name__ == '__main__':

    main()

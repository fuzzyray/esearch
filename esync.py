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

import os
import sys
from getopt import *

sys.path.insert(0, "/usr/lib/portage/pym")

import portage
try:
    from portage.output import red, green, bold, darkgreen, nocolor, xtermTitle
except ImportError:
    from output import red, green, bold, darkgreen, nocolor, xtermTitle

from common import needdbversion

syncprogram =   "EMERGE_DEFAULT_OPTS=\"\" /usr/bin/emerge --sync"
logfile_sync =  "/var/log/emerge-sync.log"
tmp_prefix =    "/tmp/esync"

sys.path.append("/tmp")

eoptions = ""
eupdatedb_extra_options = ""
showtitles = "notitles" not in portage.features
verbose = False

def usage():
    print "esync (0.7.1) - Calls 'emerge sync' and 'eupdatedb' and shows updates"
    print ""
    print bold("Usage:"), "esync [", darkgreen("options"), "]"
    print bold("Options:")
    print darkgreen("  --help") + ", " + darkgreen("-h")
    print "    Print this help message"
    print ""
    print darkgreen("  --webrsync") + ", " + darkgreen("-w")
    print "    Use 'emerge-webrsync' instead of 'emerge --sync'"
    print ""
    print darkgreen("  --metadata") + ", " + darkgreen("-m")
    print "    Use 'emerge --metadata' instead of 'emerge --sync'"
    print ""
    print darkgreen("  --nocolor") + ", " + darkgreen("-n")
    print "    Don't use ANSI codes for colored output"
    print ""
    print darkgreen("  --verbose") + ", " + darkgreen("-v")
    print "    Verbose output"
    print ""
    print darkgreen("  --nospinner") + ", " + darkgreen("-s")
    print "    Don't display the remaining index count"


    sys.exit(0)

try:
    opts = getopt(sys.argv[1:], "hwmnvs", ["help", "webrsync", "nocolor", "verbose", "metadata", "nospinner"])
except GetoptError, error:
    print red(" * Error:"), error, "(see", darkgreen("--help"), "for all options)"
    print
    sys.exit(1)

for a in opts[0]:
    arg = a[0]

    if arg in ("-h", "--help"):
        usage()
    elif arg in ("-w", "--webrsync"):
        syncprogram = "EMERGE_DEFAULT_OPTS=\"\" /usr/sbin/emerge-webrsync"
    elif arg in ("-m", "--metadata"):
        syncprogram = "EMERGE_DEFAULT_OPTS=\"\" /usr/bin/emerge --metadata"
    elif arg in ("-n", "--nocolor"):
        eoptions = "-n"
        nocolor()
        showtitles = False
    elif arg in ("-v", "--verbose"):
        verbose = True
    elif arg in ("-s", "--nospinner"):
        eupdatedb_extra_options = "-q"


def emsg(msg):
    global showtitles
    if showtitles:
        xtermTitle(msg)
    print green(" *"), msg

def outofdateerror():
    print red(" * Error:"), "The version of the esearch index is out of date, please run", green("eupdatedb")
    print ""
    sys.exit(1)

def gettree(tree):
    emsg("Importing " + tree + " portage tree")
    try:
        target = tmp_prefix + tree + "tree.pyc"
        if os.path.exists(target):
            os.unlink(target)
        os.symlink("/var/cache/edb/esearchdb.pyc", target)
    except OSError, e:
        if e.errno != 17:
            print e
            print ""
            sys.exit(1)
    try:
        if tree == "old":
            from esyncoldtree import db
            try:
                from esyncoldtree import dbversion
                if dbversion < needdbversion:
                    outofdateerror()
            except ImportError:
                outofdateerror()
        else:
            from esyncnewtree import db
    except ImportError:
        print red(" * Error:"), "Could not find esearch-index. Please run", green("eupdatedb"), "as root first"
        print ""
        sys.exit(1)
    os.unlink(target)
    return db

tree_old = gettree("old")

emsg("Doing '" + syncprogram + "' now")

if verbose == True:
    errorcode = os.system(syncprogram + " | tee " + logfile_sync + " 2>&1")
else:
    errorcode = os.system(syncprogram + " > " + logfile_sync + " 2>&1")

if errorcode != 0:
    print red(" * Error:"), "'" + syncprogram + "'", "failed, see", logfile_sync, "for errors"
    print ""
    sys.exit(1)

print ""

emsg("Doing 'eupdatedb' now")
print ""
if os.system("/usr/sbin/eupdatedb " + eoptions + " " + eupdatedb_extra_options) != 0:
    print ""
    print red(" * Error:"), "eupdatedb failed"
    sys.exit(1)

print ""

tree_new = gettree("new")

emsg("Preparing databases")

new = {}
for pkg in tree_new:
    new[pkg[1]] = pkg[3]

old = {}
for pkg in tree_old:
    old[pkg[1]] = pkg[3]

emsg("Searching for changes")
print ""

# alphabetic sort
items = new.items()
items.sort(lambda x, y: cmp(x[0], y[0]))

old_keys = old.keys()

haspkg = False

for (pkg, version) in items:
    if (pkg not in old_keys) or (old[pkg] != new[pkg]):
        os.system("/usr/bin/esearch " + eoptions + " -Fc ^" + pkg + "$ | head -n1")
        haspkg = True

if not haspkg:
    emsg("No updates found")

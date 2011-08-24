#!/usr/bin/env python
#
# This is a script to update the esearch
# index file from the current portage tree.
#
# Author: David Peter <davidpeter@web.de>
#

from time import time
start = time()

import os
import sys
import re
from os import stat, unlink, environ, open, fdopen, O_RDONLY, O_EXCL, O_CREAT, O_WRONLY
from os.path import exists
from shutil import copyfile
from getopt import *

try:
	from portage.const import EPREFIX
except ImportError:
	EPREFIX = ''

sys.path.insert(0, EPREFIX + "/usr/lib/portage/pym")
sys.path.insert(0, EPREFIX + "/usr/lib/esearch")

import portage
try:
    from portage.output import red, darkgreen, green, bold, nocolor
    from portage.manifest import Manifest
    from portage.exception import PortageException
except ImportError:
    from output import red, darkgreen, green, bold, nocolor
    from portage_manifest import Manifest
    from portage_exception import PortageException

from common import needdbversion, version

esearchdbdir =  EPREFIX + "/var/cache/edb/"
tmpfile =       EPREFIX + "/tmp/esearchdb.py.tmp"

vartree = portage.vartree()

def usage():
    print "eupdatedb (0.7.1) - Update the search-index for esearch"
    print ""
    print bold("Usage:"), "eupdatedb [", darkgreen("options"), "]"
    print bold("Options:")
    print darkgreen("  --help") + ", " + darkgreen("-h")
    print "    Print this help message"
    print ""
    print darkgreen("  --verbose") + ", " + darkgreen("-v")
    print "    Verbose mode, show categories"
    print ""
    print darkgreen("  --quiet") + ", " + darkgreen("-q")
    print "    Print only summary"
    print ""
    print darkgreen("  --directory=") + "dir, " + darkgreen("-d") + " dir"
    print "    Load esearch index from dir"
    print ""
    print darkgreen("  --nocolor") + ", " + darkgreen("-n")
    print "    Don't use ANSI codes for colored output"

    sys.exit(0)

def duration(start):
    d = int(round(time() - start))
    if d >= 60:
        d = str(d / 60) + " minute(s) and " + str(d % 60) + " second(s)"
    else:
        d = str(d) + " second(s)"
    return d


def getfs(pkg):
    # from /usr/bin/emerge
    try:
        myebuild = portage.portdb.findname(pkg)
        pkgdir = os.path.dirname(myebuild)
        mf = Manifest(pkgdir, portage.settings["DISTDIR"])
        if hasattr(portage.portdb, "getFetchMap"):
            fetchlist = portage.portdb.getFetchMap(pkg)
        else:
            fetchlist = portage.portdb.getfetchlist(pkg,
                mysettings=portage.settings, all=True)[1]
        mysum = mf.getDistfilesSize(fetchlist)
        mystr = str(mysum/1024)
        mycount = len(mystr)
        while (mycount > 3):
            mycount -= 3
            mystr = mystr[:mycount] + "," + mystr[mycount:]
        mysum = mystr + " kB"

        return mysum
    except (PortageException, KeyError):
        return "[no/bad digest]"

try:
    opts = getopt(sys.argv[1:], "hvqd:n", ["help", "verbose", "quiet", "directory=", "nocolor"])
except GetoptError, error:
    print red(" * Error:"), error, "(see", darkgreen("--help"), "for all options)"
    print
    sys.exit(1)

verbose = 0

for a in opts[0]:
    arg = a[0]

    if arg in ("-h", "--help"):
        usage()
    elif arg in ("-v", "--verbose"):
        verbose = 1
    elif arg in ("-q", "--quiet"):
        verbose = -1
    elif arg in ("-d", "--directory"):
        esearchdbdir = a[1]
        if not exists(esearchdbdir):
            print red(" * Error:"), "directory '" + darkgreen(esearchdbdir) + "'", "does not exist."
            print ""
            sys.exit(1)
    elif arg in ("-n", "--nocolor"):
        nocolor()

esearchdbfile = esearchdbdir + "/esearchdb.py"

if verbose != -1 and environ.has_key("ACCEPT_KEYWORDS"):
    print red("Warning:"), "You have set ACCEPT_KEYWORDS in environment, this will result"
    print "         in a modified index file"

db = []
ebuilds = portage.portdb.cp_all()
numebuilds = len(ebuilds)

if exists(tmpfile):
    print red("Error: "), " there is probably another eupdatedb running already."
    print "         If you're sure there is no other process, remove", tmpfile
    print ""
    sys.exit(1)
try:
    dbfd = open(tmpfile, O_CREAT | O_EXCL | O_WRONLY, 0600)
except OSError:
    print red("Error: "), " failed to open temporary file."
    sys.exit(1)
dbfile = fdopen(dbfd, "w")
dbfile.write("dbversion = " + str(needdbversion) + "\n")
dbfile.write("db = (")

if not verbose:
    sys.stdout.write(green(" * ") + "indexing: ")
    sys.stdout.flush()
    nr = 0
    nrchars = 0
elif verbose == 1:
    lastcat = False

try:
    for pkg in ebuilds:
        masked = False

        if not verbose:
            nr += 1
            s = str(numebuilds - nr) + " ebuilds to go"
            sys.stdout.write((nrchars * "\b \b") + s)
            sys.stdout.flush()
            nrchars = len(s)

        pkgv = portage.portdb.xmatch("bestmatch-visible", pkg)
        if not pkgv:
            pkgv = portage.best(portage.portdb.xmatch("match-all", pkg))
            if not pkgv:
                continue
            masked = True

        if len(pkgv) > 1:
            try:
                homepage, description, license = portage.portdb.aux_get(pkgv, ["HOMEPAGE", "DESCRIPTION", "LICENSE"])
            except KeyError:
                homepage, description, license = "", "", ""
                pass

        if len(pkgv) > 1:
            filesize = getfs(pkgv)
        else:
            filesize = 0

        (curcat, pkgname) = pkg.split("/")

        if verbose == 1 and curcat != lastcat:
            if lastcat != False:
                print duration(cattime)
            print bold(" * " + curcat) + ":",
            cattime = time()
            lastcat = curcat

        dbfile.write(repr((pkgname,
                        pkg,
                        masked,
                        version(pkgv),
                        version(vartree.dep_bestmatch(pkg)),
                        filesize,
                        homepage,
                        description,
                        license)) + ",")
except KeyboardInterrupt:
    dbfile.close()
    unlink(tmpfile)
    print ""
    sys.exit(1)

print ""

dbfile.write(")")
dbfile.close()

copyfile(tmpfile, esearchdbfile)
unlink(tmpfile)

sys.path.insert(0, esearchdbdir)
import esearchdb # import the file, to generate pyc

if exists(esearchdbfile + "c"):
    esearchdbfile += "c"

print green(" *"), "esearch-index generated in", duration(start)
print green(" *"), "indexed", bold(str(numebuilds)), "ebuilds"
print green(" *"), "size of esearch-index:", bold(str(int(stat(esearchdbfile)[6]/1024)) + " kB")

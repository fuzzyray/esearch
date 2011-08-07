#!/usr/bin/env python
#
# This is a script to update the esearch
# index file from the current portage tree.
#
# Author: David Peter <davidpeter@web.de>
#

from __future__ import print_function

from time import time
start = time()

import os
import sys
from os import stat, unlink, environ, open, fdopen, O_EXCL, O_CREAT, O_WRONLY
from os.path import exists
from shutil import copyfile
from getopt import getopt, GetoptError

#sys.path.insert(0, "/usr/lib/portage/pym")
# commented out so it can run from the git checkout
#sys.path.insert(0, "/usr/lib/esearch")

import portage
try:
    from portage.output import red, darkgreen, green, bold, nocolor
    from portage.manifest import Manifest
    from portage.exception import PortageException
except ImportError:
    print("Critical: portage imports failed!")
    sys.exit(1)

from esearch.common import version, CONFIG, pkg_version



VARTREE = portage.vartree()

def usage():
    print("eupdatedb (%s) - Update the search-index for esearch" % version)
    print("")
    print(bold("Usage:"), "eupdatedb [", darkgreen("options"), "]")
    print(bold("Options:"))
    print(darkgreen("  --help") + ", " + darkgreen("-h"))
    print("    Print this help message")
    print("")
    print(darkgreen("  --verbose") + ", " + darkgreen("-v"))
    print("    Verbose mode, show categories")
    print("")
    print(darkgreen("  --quiet") + ", " + darkgreen("-q"))
    print("    Print only summary")
    print("")
    print(darkgreen("  --directory=") + "dir, " + darkgreen("-d") + " dir")
    print("    Load esearch index from dir")
    print("")
    print(darkgreen("  --nocolor") + ", " + darkgreen("-n"))
    print("    Don't use ANSI codes for colored output")

    sys.exit(0)

def duration(start):
    d = int(round(time() - start))
    if d >= 60:
        d = str(d / 60) + " minute(s) and " + str(d % 60) + " second(s)"
    else:
        d = str(d) + " second(s)"
    return d


def getfetchsize(pkg):
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


def parseopts(opts, config=None):
    if config is None:
        config = CONFIG
    config['verbose'] = 0
    for a in opts[0]:
        arg = a[0]
        if arg in ("-h", "--help"):
            usage()
        elif arg in ("-v", "--verbose"):
            config['verbose'] = 1
        elif arg in ("-q", "--quiet"):
            config['verbose'] = -1
        elif arg in ("-d", "--directory"):
            config['esearchdbdir'] = a[1]
            if not exists(config['esearchdbdir']):
                print(red(" * Error:"), "directory '" + \
                    darkgreen(config['esearchdbdir']) + "'", "does not exist.")
                print("")
                sys.exit(1)

        elif arg in ("-n", "--nocolor"):
            nocolor()
    return config


def updatedb(config=None):

    if not os.access(config['esearchdbdir'], os.W_OK):
        print(red("Warning:"), \
            "You do not have sufficient permissions to save the index file in:",\
            green(config['esearchdbdir']))
        return False

    if config['verbose'] != -1 and "ACCEPT_KEYWORDS" in environ:
        print(red("Warning:"), \
            "You have set ACCEPT_KEYWORDS in environment, this will result")
        print("         in a modified index file")

    ebuilds = portage.portdb.cp_all()
    numebuilds = len(ebuilds)

    if exists(config['tmpfile']):
        print(red("Error: "), " there is probably another eupdatedb running already.")
        print("         If you're sure there is no other process, remove", config['tmpfile'])
        print("")
        return False
    try:
        dbfd = open(config['tmpfile'], O_CREAT | O_EXCL | O_WRONLY, 0o600)
    except OSError:
        print(red("Error: "), " failed to open temporary file.")
        return False
    dbfile = fdopen(dbfd, "w")
    dbfile.write("dbversion = " + str(config['needdbversion']) + "\n")
    dbfile.write("db = (")

    if not config['verbose']:
        config['stdout'].write(green(" * ") + "indexing: ")
        config['stdout'].flush()
        nr = 0
        nrchars = 0
    elif config['verbose'] == 1:
        lastcat = False

    cattime = time()
    try:
        for pkg in ebuilds:
            masked = False

            if not config['verbose']:
                nr += 1
                s = str(numebuilds - nr) + " ebuilds to go"
                config['stdout'].write((nrchars * "\b \b") + s)
                config['stdout'].flush()
                nrchars = len(s)

            pkgv = portage.portdb.xmatch("bestmatch-visible", pkg)
            if not pkgv:
                pkgv = portage.best(portage.portdb.xmatch("match-all", pkg))
                if not pkgv:
                    continue
                masked = True

            if len(pkgv) > 1:
                try:
                    homepage, description, _license = portage.portdb.aux_get(
                        pkgv, ["HOMEPAGE", "DESCRIPTION", "LICENSE"])
                except KeyError:
                    homepage, description, _license = "", "", ""
                    pass

            if len(pkgv) > 1:
                filesize = getfetchsize(pkgv)
            else:
                filesize = 0

            (curcat, pkgname) = pkg.split("/")

            if config['verbose'] == 1 and curcat != lastcat:
                if lastcat != False:
                    print(duration(cattime))
                print(bold(" * " + curcat) + ":", end=' ')
                cattime = time()
                lastcat = curcat

            dbfile.write(repr((pkgname,
                            pkg,
                            masked,
                            pkg_version(pkgv),
                            pkg_version(VARTREE.dep_bestmatch(pkg)),
                            filesize,
                            homepage,
                            description,
                            _license)) + ",")
    except KeyboardInterrupt:
        dbfile.close()
        unlink(config['tmpfile'])
        print("")
        return False

    print("")

    dbfile.write(")")
    dbfile.close()

    copyfile(config['tmpfile'],
        os.path.join(config['esearchdbdir'], config['esearchdbfile']))
    unlink(config['tmpfile'])

    sys.path.insert(0, config['esearchdbdir'])
    import esearchdb # import the file, to generate pyc

    if exists(
        os.path.join(config['esearchdbdir'], config['esearchdbfile']) + "c"):
        config['esearchdbfile'] += "c"

    print(green(" *"), "esearch-index generated in", duration(start))
    print(green(" *"), "indexed", bold(str(numebuilds)), "ebuilds")
    print(green(" *"), "size of esearch-index:", \
        bold(str(int(stat(
            os.path.join(config['esearchdbdir'], config['esearchdbfile'])
            )[6]/1024)) + " kB"))
    return True


def main():
    try:
        opts = getopt(sys.argv[1:], "hvqd:n",
            ["help", "verbose", "quiet", "directory=", "nocolor"]
            )
    except GetoptError as error:
        print(red(" * Error:"), error, "(see", darkgreen("--help"), "for all options)")
        print()
        sys.exit(1)
    config = parseopts(opts)
    success = updatedb(config)
    # sys.exit() values are opposite T/F
    sys.exit(not success)

if __name__ == '__main__':

    main()

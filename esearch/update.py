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
from os import stat, unlink, environ, open, O_EXCL, O_CREAT, O_WRONLY
from os.path import exists
from shutil import copyfile
from getopt import getopt, GetoptError

import io

#sys.path.insert(0, "/usr/lib/portage/pym")
# commented out so it can run from the git checkout
#sys.path.insert(0, "/usr/lib/esearch")

import portage
try:
    from portage.output import yellow, darkgreen, green, bold, nocolor
    from portage.manifest import Manifest
    from portage.exception import PortageException
except ImportError:
    print("Critical: portage imports failed!")
    sys.exit(1)

from esearch.common import version, CONFIG, pkg_version, error



VARTREE = portage.vartree()


if sys.hexversion >= 0x3000000:
    _unicode = str
else:
    _unicode = unicode


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
        d = str(d // 60) + " minute(s) and " + str(d % 60) + " second(s)"
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
        mystr = str(mysum // 1024)
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
                error("directory '" + darkgreen(config['esearchdbdir']) +
                    "'", "does not exist.", stderr=config['stderr'])
        elif arg in ("-n", "--nocolor"):
            nocolor()
    return config


def updatedb(config=None):

    if not os.access(config['esearchdbdir'], os.W_OK):
        print(yellow("Warning:"),
            "You do not have sufficient permissions to save the index file in:",
            green(config['esearchdbdir']), file=config['stderr'])
        return False

    if config['verbose'] != -1 and "ACCEPT_KEYWORDS" in environ:
        print(yellow("Warning:"),
            "You have set ACCEPT_KEYWORDS in environment, this will result",
            file=config['stdout'])
        print("         in a modified index file", file=config['stdout'])

    ebuilds = portage.portdb.cp_all()
    numebuilds = len(ebuilds)

    if exists(config['tmpfile']):
        error("there is probably another eupdatedb running already.\n" +
            "         If you're sure there is no other process, remove " +
            config['tmpfile'], fatal=False)
        return False
    try:
        dbfd = open(config['tmpfile'], O_CREAT | O_EXCL | O_WRONLY, 0o600)
    except OSError:
        error("Failed to open temporary file.", fatal=False)
        return False


    dbfile = io.open(dbfd, mode="w", encoding="utf_8")
    dbfile.write(_unicode("# -*- coding: UTF8 -*-\n"))

    dbfile.write(_unicode("dbversion = ") +
        _unicode(config['needdbversion']) +
        _unicode("\n"))
    dbfile.write(_unicode("db = (\n"))

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
                filesize = '0'

            (curcat, pkgname) = pkg.split("/")

            if config['verbose'] == 1 and curcat != lastcat:
                if lastcat != False:
                    print(duration(cattime), file=config['stdout'])
                print(bold(" * " + curcat) + ":", end=' ', file=config['stdout'])
                cattime = time()
                lastcat = curcat

            installed = pkg_version(VARTREE.dep_bestmatch(pkg))
            if installed:
                installed = "\'%s\'" % installed
            else:
                installed = str(installed)

            dbfile.write(
                _unicode(
                    "(\'%s\', \'%s\', %s" %(pkgname, pkg, str(masked)) +
                    ", \'%s\', %s" % (pkg_version(pkgv), installed) +
                    ", \'%s\', \'%s\', \'%s\', \'%s\'"
                    % (filesize, homepage, description.replace("'", "\\'"),
                        _license) + "),\n"))

    except KeyboardInterrupt:
        dbfile.close()
        unlink(config['tmpfile'])
        print("", file=config['stdout'])
        return False

    print("", file=config['stdout'])

    dbfile.write(_unicode(")"))
    dbfile.close()

    copyfile(config['tmpfile'],
        os.path.join(config['esearchdbdir'], config['esearchdbfile']))
    unlink(config['tmpfile'])

    sys.path.insert(0, config['esearchdbdir'])
    import esearchdb # import the file, to generate pyc

    if exists(
        os.path.join(config['esearchdbdir'], config['esearchdbfile']) + "c"):
        config['esearchdbfile'] += "c"

    print(green(" *"), "esearch-index generated in", duration(start),
        file=config['stdout'])
    print(green(" *"), "indexed", bold(str(numebuilds)), "ebuilds",
        file=config['stdout'])
    print(green(" *"), "size of esearch-index:",
        bold(str(int(stat(
            os.path.join(config['esearchdbdir'], config['esearchdbfile'])
            )[6]/1024)) + " kB"), file=config['stdout'])
    return True


def main():
    try:
        opts = getopt(sys.argv[1:], "hvqd:n",
            ["help", "verbose", "quiet", "directory=", "nocolor"]
            )
    except GetoptError as error:
        error(error + "(see" + darkgreen("--help") +
            "for all options)" + '\n')
    config = parseopts(opts)
    success = updatedb(config)
    # sys.exit() values are opposite T/F
    sys.exit(not success)

if __name__ == '__main__':

    main()

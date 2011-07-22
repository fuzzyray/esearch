#!/usr/bin/python
#
# Some functions for esearch,
# eupdatedb and esync.
#
# Author: David Peter <davidpeter@web.de>
#

# current esearch database version
needdbversion = 63

# get the version from a string like 'foo-bar/bar-0.4_rc2-r1'
def version(pkg):
    from portage import catpkgsplit
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

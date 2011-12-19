#!/usr/bin/env python

from __future__ import print_function


import re
import sys
import distutils
from distutils import core, log
from glob import glob

import os
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pym'))

__version__ = os.getenv('VERSION', default='9999')

cwd = os.getcwd()

# Load EPREFIX from Portage, fall back to the empty string if it fails 
try: 
	from portage.const import EPREFIX 
except ImportError: 
	EPREFIX='' 

# Python files that need `__version__ = ""` subbed, relative to this dir:
python_scripts = [os.path.join(cwd, path) for path in (
	'esearch/__init__.py',
)]

class set_version(core.Command):
	"""Set python __version__ and bash VERSION to our __version__."""
	description = "hardcode scripts' version using VERSION from environment"
	user_options = []  # [(long_name, short_name, desc),]

	def initialize_options (self):
		pass

	def finalize_options (self):
		pass

	def run(self):
		ver = 'vcs' if __version__ == '9999' else __version__
		print("Settings version to %s" % ver)
		def sub(files, pattern):
			for f in files:
				updated_file = []
				with io.open(f, 'r', 1, 'utf_8') as s:
					for line in s:
						newline = re.sub(pattern, '"%s"' % ver, line, 1)
						if newline != line:
							log.info("%s: %s" % (f, newline))
						updated_file.append(newline)
				with io.open(f, 'w', 1, 'utf_8') as s:
					s.writelines(updated_file)
		quote = r'[\'"]{1}'
		python_re = r'(?<=^__version__ = )' + quote + '[^\'"]*' + quote
		sub(python_scripts, python_re)


packages = [
	str('.'.join(root.split(os.sep)[1:]))
	for root, dirs, files in os.walk('./esearch')
	if '__init__.py' in files
]

core.setup(
	name='esearch',
	version=__version__,
	description='Replacement for emerge --search',
	author='',
	author_email='',
	maintainer='Gentoo Portage Tools Team',
	maintainer_email='tools-portage@gentoo.org',
	url='http://www.gentoo.org/proj/en/portage/tools/index.xml',
	download_url='http://distfiles.gentoo.org/distfiles/esearch-%s.tar.gz'\
		% __version__,
	package_dir={'': '.'},
	packages=packages,
	scripts=(glob('bin/*')),
	data_files=(
		(os.path.join(os.sep, EPREFIX.lstrip(os.sep), 'usr/share/man/man1'), glob('man/en/*')),
		(os.path.join(os.sep, EPREFIX.lstrip(os.sep), 'usr/share/man/fr/man1'), glob('man/fr/*')),
		(os.path.join(os.sep, EPREFIX.lstrip(os.sep), 'usr/share/man/it/man1'), glob('man/it/*')),
	),
	cmdclass={
		'set_version': set_version,
	},
)

# vim: set ts=4 sw=4 tw=79:

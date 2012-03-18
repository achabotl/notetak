# Copyright (C) 2007  Lars Wirzenius <liw@iki.fi>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

DESTDIR =
prefix = /usr/local
bindir = $(prefix)/bin
sharedir = $(prefix)/share
mandir = $(sharedir)/man
man1dir = $(mandir)/man1
datadir = $(sharedir)/notetak
libdir = $(prefix)/lib
pythondir = $(libdir)/python2.4
sitedir = $(pythondir)/site-packages
appsdir = $(sharedir)/applications

all:

check:
	python-coverage -e
	python-coverage -x tests.py
	python-coverage -rm -o /usr,/var,notetakuuid | \
	    awk '{ print } /^TOTAL/ && $$2 != $$3 {exit 1}'

version:
	echo -n "notetak "
	sed -n '/^VERSION = /s/.*"\(.*\)".*/\1/p' notetak.py

install:
	install -d $(DESTDIR)$(bindir)
	install run.py $(DESTDIR)$(bindir)/notetak

	install -d $(DESTDIR)$(sitedir)
	install -m 0644 notetak.py notetakuuid.py $(DESTDIR)$(sitedir)
	sed -i -e 's:^GLADE = .*:GLADE = "$(datadir)/notetak.glade":' \
	    -e 's:^LOGO = .*:LOGO = "$(datadir)/notetak.png":' \
	    -e 's:^DEFAULT_NAME = .*:DEFAULT_NAME = os.path.expanduser("~/.notetak"):' \
	    $(DESTDIR)$(sitedir)/notetak.py

	install -d $(DESTDIR)$(man1dir)
	install -m 0644 notetak.1 $(DESTDIR)$(man1dir)
	gzip -9 $(DESTDIR)$(man1dir)/notetak.1

	install -d $(DESTDIR)$(datadir)
	install -m 0644 notetak.glade $(DESTDIR)$(datadir)/notetak.glade
	install -m 0644 notetak.png $(DESTDIR)$(datadir)/notetak.png
	
	install -d $(DESTDIR)$(appsdir)
	install -m 0644 notetak.desktop $(DESTDIR)$(appsdir)
	sed -i -e 's:^Icon=:Icon=$(datadir)/:' \
	    $(DESTDIR)$(appsdir)/notetak.desktop

clean:
	rm -rf *.pyc *.pyo .coverage unittestdir

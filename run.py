#!/usr/bin/python2.4
#
# Copyright (C) 2006, 2007  Lars Wirzenius <liw@iki.fi>
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

import logging
import os

import gnome

from notetak import *

if __name__ == "__main__":
    gnome.init(NAME, VERSION)
    app = App(log_level=logging.INFO, gconfdir="/apps/Notetak")
    app.quit = gtk.main_quit
    if len(sys.argv) > 1:
        savedir = sys.argv[1];
    else:
        savedir = os.path.expanduser("~/.notetak")
        if not os.path.exists(savedir):
            print "Creating %s." % (savedir,)
            os.makedirs(savedir)
    app.open_notelist(savedir)
    w = app.new_window()
    w.window.show()
    gtk.main()

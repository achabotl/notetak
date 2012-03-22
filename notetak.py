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


"""A note taking application for GNOME

This program was inspired by "Notational Velocity" for OS X.

Lars Wirzenius <liw@iki.fi>
"""

import inspect
import logging
import os
import sys
import time

import pygtk
pygtk.require("2.0")
import gconf
import gobject
import gtk
import gtk.glade
import pango


NAME = "Notetak"
VERSION = "0.17"
GLADE = os.path.join(os.path.dirname(__file__), "notetak.glade")
LOGO = "notetak.png"

if True: #pragma: no cover
    COPYRIGHT = "Copyright 2007 Lars Wirzenius <liw@iki.fi>"
    COMMENTS = \
    "A note taking application, inspired by Notational Velocity for OS X."
    LICENSE = """\
This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""


FONT = "Monospace"
GCONFDIR = "/apps/NotetakDevelopment"
FILETYPE = ".md"

# This is a kludge. Python 2.5 will include a uuid module.
sys.path.append(os.path.dirname(GLADE))
import notetakuuid
uuid = notetakuuid


class Note:

    """An individual note
    
    This class handles an individual note: it's on-disk and in-memory
    representation (except for the filename).
    
    A note is, conceptually, a plain text file, with the first physical
    line being the title. Naming of the file is done externally; the
    meta data stored by this class is a UUID to be used as an
    identifier, whether the note has been changed since loaded or saved,
    and the file modification time. The UUID is expected to server as
    the file name, or part thereof, but nothing in this class assumes
    that.
    
    In addition, this class supports callbacks that are triggered 
    a specified period after the last change to this note. This can be
    used by external code to, for example, automatically save a note
    after the user has stopped editing it.
    
    """

    def __init__(self):
        self.id = uuid.uuid4()
        logging.debug("Created Note, id=%s" % self.id)
        self.buffer = None
        self.mtime = None
        self.dirty = False
        self.timeout_id = None
        self.timeout_length = None
        self.timeout_callback = None
        self.immediate_change_callback = None

    def load(self,filename):
        """Load note from disk into memory"""

        logging.debug("Loading note %s" % (filename))
        f = file(filename, "r")
        data = f.read()
        f.close()
        
        basename = os.path.basename(filename)
        if basename.endswith(FILETYPE):
            self.filename = basename[:-len(FILETYPE)]
        else:
            self.filename = basename
        
        self.set_text(data)
        self.mtime = os.stat(filename).st_mtime

    def save(self,dirname):
        """Save note from memory to disk"""

        logging.debug("Saving note to %s" % (self.filename))        
        fullpath = os.path.join(dirname, (self.filename + FILETYPE))
        f = file(fullpath, "w")
        f.write(self.get_text())
        f.close()
        os.utime(fullpath, (self.mtime, self.mtime))
        self.dirty = False

    def remove(self,dirname):
        """Remove note from disk"""
        
        logging.debug("Remove note %s" % (self.filename))
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def get_buffer(self):
        """Return the GtkTextBuffer for this note"""
        return self.buffer

    def get_title(self):
        """Return title of note"""
        
        if self.buffer is None:
            return ""
        title = self.filename
        return title

    def get_text(self):
        """Return the entire contents of a note, including title"""
        
        if self.buffer is None:
            return ""
        start, end = self.buffer.get_bounds()
        return self.buffer.get_text(start, end)

    def set_text(self, text):
        """Change the entire contents of a note, including first line"""
        
        if self.buffer is None:
            self.buffer = gtk.TextBuffer()
            self.buffer.connect("changed", self.touch)
        self.buffer.set_text(text)
        start = self.buffer.get_start_iter()
        self.buffer.move_mark(self.buffer.get_insert(), start)
        self.buffer.move_mark(self.buffer.get_selection_bound(), start)

    def now(self):
        """Return current time"""
        # This is meant to be overridden by unit tests
        return time.time()

    def touch(self, *args):
        """Update the modification time for note"""
        self.mtime = self.now()
        self.dirty = True
        self.start_change_timeout()
        if self.immediate_change_callback:
            self.immediate_change_callback(self)

    def matches(self, pattern):
        """Does this note match a search pattern?
        
        The search pattern is a list of words, each word being a string.
        The matching is done ignoring case differences, but with the 
        assumption that each word has been converted to lower case by
        the caller (via word.lower()), so that this method only needs to
        convert the note text itself into lower case for matching.
        
        The pattern matches the note if each word in the pattern is
        included in the note text.
        
        """
        
        start, end = self.buffer.get_bounds()
        text = self.buffer.get_text(start, end)
        text = text.lower()
        for word in pattern:
            if word.startswith("!") and word != "!":
                if word[1:] in text:
                    return False
            else:
                if word not in text:
                    return False
        return True

    def start_change_timeout(self):
        """Start a change timeout period
        
        The callback will happen self.timeout_length milliseconds after
        this method is called. If self.timeout_length is not set, then
        no timeout period will start. That is, you have to call the
        set_changed_timeout method first.
        
        """
        
        if self.timeout_length:
            self.stop_change_timeout()
            self.timeout_id = gobject.timeout_add(self.timeout_length, 
                                                  self.buffer_changed_timeout)

    def stop_change_timeout(self):
        """Stop any current change timeout"""
        if self.timeout_id:
            gobject.source_remove(self.timeout_id)
            self.timeout_id = None
        
    def buffer_changed_timeout(self):
        """Calls the change timeout callback"""
        if self.timeout_id:
            self.timeout_callback(self)

    def set_change_timeout(self, milliseconds, callback):
        """Set the period and callback of a timeout for changes"""
        self.timeout_length = milliseconds
        self.timeout_callback = callback

    def set_immediate_change_callback(self, callback):
        """Set function to be called immediately on any change"""
        self.immediate_change_callback = callback
        
    def set_filename(self, filename):
        """Set note filename"""
        if filename.endswith(FILETYPE):
            self.filename = filename[:-len(FILETYPE)]    
        else:
            self.filename = filename
    
    def get_full_filename(self,dirname):
        """Return the filename with path to file and extension"""
        return os.path.join(dirname, self.filename, FILETYPE)


class TooManyVisibilityColumns(Exception):

    """Exception for when there are too many windows for one NoteList"""

    def __str__(self):
        return "Too many windows"


class NoteList:

    """A list of notes
    
    This class represents all notes in a note directory. Like with
    Notes, the decision of what the directory is called is left to
    external code.
    
    Because of how the GtkTreeView family of objects is implemented,
    this class also keeps track of which notes are visible in which
    application window. A GtkTreeView widget acts as the View in a
    Model/View/Controller setup, and this class acts as a Model. The
    View can show only some of the items in the Model, and this is
    controlled by a data column in the Model. To support multiple
    views into the same model, there can be many such visibility
    columns. However, all columns are created at startup, then the
    model is created. This requires deciding on a limit on the number
    of views (alas).
    
    """

    MAX_VISIBILITY_COLUMNS = 128

    def __init__(self, change_timeout_time=None, change_timeout_callback=None):
        logging.debug("Creating new NoteList")
        
        self.change_timeout_time = change_timeout_time
        self.change_timeout_callback = change_timeout_callback
        
        column_types = [gobject.TYPE_BOOLEAN] * self.MAX_VISIBILITY_COLUMNS

        self.NOTE_COLUMN = len(column_types)
        column_types += [gobject.TYPE_PYOBJECT]

        self.TITLE_COLUMN = len(column_types)
        column_types += [gobject.TYPE_STRING]

        self.liststore = apply(gtk.ListStore, column_types)
        self.liststore.set_sort_column_id(self.TITLE_COLUMN, 
                                          gtk.SORT_ASCENDING)
        self.visibility_columns = []
        self.available_visibility_columns = range(self.MAX_VISIBILITY_COLUMNS)
        self.dirty = False

    def note_filename(self, dirname, note):
        """Return the filename for a note, including the path"""
        return note.get_full_filename(dirname)

    def get_notes(self):
        """Return all notes as a Python list"""
        notes = []
        iter = self.liststore.get_iter_first()
        while iter:
            notes.append(self.liststore.get_value(iter, self.NOTE_COLUMN))
            iter = self.liststore.iter_next(iter)
        return notes

    def find_iter_for_note(self, note):
        """Find the GtkIter corresponding to a note"""
        iter = self.liststore.get_iter_first()
        while iter:
            if self.liststore.get_value(iter, self.NOTE_COLUMN) == note:
                return iter
            iter = self.liststore.iter_next(iter)
        return None

    def get_from_title_column(self, note):
        """Return the cell corresponding to note in title column"""
        iter = self.find_iter_for_note(note)
        if iter:
            return self.liststore.get_value(iter, self.TITLE_COLUMN)
        else:
            return None

    def append_note(self, note):
        """Add a new note to the end of the list"""
        logging.debug("Adding note %s to NoteList" % note.filename)
        iter = self.liststore.append()
        for i in range(self.MAX_VISIBILITY_COLUMNS):
            self.liststore.set_value(iter, i, False)
        self.liststore.set_value(iter, self.NOTE_COLUMN, note)
        self.update_title_column(note)
        note.set_immediate_change_callback(self.update_title_column)
        note.set_change_timeout(self.change_timeout_time,
                                self.change_timeout_callback)
        self.dirty = True

    def update_title_column(self, note):
        """Update title column for note"""
        iter = self.find_iter_for_note(note)
        if iter:
            self.liststore.set_value(iter, self.TITLE_COLUMN, 
                                     note.get_title())

    def remove_note(self, dirname, note):
        """Remove a note from the list"""
        logging.debug("Removing note %s from NoteList" % note.filename)
        iter = self.liststore.get_iter_first()
        while iter:
            if self.liststore.get_value(iter, self.NOTE_COLUMN) == note:
                self.liststore.remove(iter)
                if dirname is not None:
                    note.remove(dirname)
                self.dirty = True
                return
            iter = self.liststore.iter_next(iter)
        logging.debug("Oops, note %s not in NoteList, can't remove" % note.filename)

    def clear(self):
        """Remove all notes from the list"""
        logging.debug("Forgetting (not removing on disk) all notes in list")
        self.liststore.clear()

    def load(self, dirname):
        """Load all notes into memory"""
        logging.debug("Loading notes from %s" % dirname)
        for basename in os.listdir(dirname):
            fullname = os.path.join(dirname, basename)
            if os.path.isfile(fullname):
                note = Note()
                note.load(fullname)
                self.append_note(note)
        self.make_clean()
        logging.debug("Done loading notes from %s" % dirname)

    def save(self, dirname):
        """Save all notes to disk"""
        logging.debug("Saving notes to %s" % dirname)
        if not os.path.exists(dirname):
            logging.debug("Creating %s" % dirname)
            os.mkdir(dirname)
        for note in self.get_notes():
            note.save(dirname)
        self.make_clean()
        logging.debug("Done saving notes to %s" % dirname)

    def save_dirty(self, dirname):
        """Save only changed notes to disk"""
        logging.debug("Saving dirty notes to %s" % dirname)
        if not os.path.exists(dirname):
            logging.debug("Creating %s" % dirname)
            os.mkdir(dirname)
        for note in self.get_notes():
            if note.dirty:
                note.save(dirname)
        self.make_clean()
        logging.debug("Done saving dirty notes to %s" % dirname)

    def find_matching(self, pattern):
        """Return all notes matching a pattern"""
        return [note for note in self.get_notes() if note.matches(pattern)]

    def get_visibility_columns(self):
        """Return list of numbers of visibility columns currently in use"""
        return self.visibility_columns

    def add_visibility_column(self):
        """Allocate a visibility column
        
        This will raise the TooManyVisibilityColumns exception if there
        are no un-allocated visibility columns.
        
        """
        if not self.available_visibility_columns:
            raise TooManyVisibilityColumns()
        col = self.available_visibility_columns[0]
        del self.available_visibility_columns[0]
        self.visibility_columns.append(col)
        return col

    def remove_visibility_column(self, col):
        """Free up a visibility column"""
        self.visibility_columns.remove(col)
        self.available_visibility_columns.append(col)

    def get_visible_notes(self, col):
        """Return list of notes visibile according to column 'col'"""
        notes = []
        iter = self.liststore.get_iter_first()
        while iter:
            if self.liststore.get_value(iter, col):
                notes.append(self.liststore.get_value(iter, self.NOTE_COLUMN))
            iter = self.liststore.iter_next(iter)
        return notes

    def mark_visible_rows(self, col, pattern):
        """Mark in column 'col' as visible all notes matching 'pattern'"""
        iter = self.liststore.get_iter_first()
        while iter:
            note = self.liststore.get_value(iter, self.NOTE_COLUMN)
            self.liststore.set_value(iter, col, note.matches(pattern))
            iter = self.liststore.iter_next(iter)

    def is_dirty(self):
        """Has the list or any of its notes been modified?"""
        if self.dirty:
            return True
        for note in self.get_notes():
            if note.dirty:
                return True
        return False

    def make_clean(self):
        """Mark list of notes and all notes therein as unmodified"""
        self.dirty = False
        for note in self.get_notes():
            note.dirty = False


class GConfWrapper:

    """A GConf wrapper
    
    For some reason, storing and then very quickly retrieving a value does
    not always work, and this mucks up unit tests. This wrapper caches
    values so that tests always work.
    
    """

    def __init__(self, gconfdir):
        self.dict = {}
        self.gconfdir = gconfdir
        self.gc = gconf.client_get_default()
        self.gc.add_dir(self.gconfdir, gconf.CLIENT_PRELOAD_NONE)

    def set_string(self, key, value):
        self.gc.set_string(self.key(key), value)
        self.dict[key] = value

    def set_int(self, key, value):
        self.gc.set_int(self.key(key), int(value))
        self.dict[key] = int(value)
        
    def key(self, relative_key):
        return os.path.join(self.gconfdir, relative_key)
        
    def get_int(self, key):
        if key not in self.dict:
            value = self.gc.get_int(self.key(key))
            self.dict[key] = value
        try:
            return int(self.dict[key])
        except ValueError:
            return 0


class DirnameNotSet(Exception):

    """Exception for when trying to save a note list, when name is missing"""

    def __str__(self):
        return "Note list directory name not set"


class App:

    """Representation of the entire application
    
    This class represents the entire application: the list of notes,
    and all windows showing it, and things related to the application
    as a whole, rather than any one window.
    
    """
    
    
    AUTOSAVE_DELAY = 1000
    

    def __init__(self, log_level=None, gconfdir=None):
        logging.basicConfig(level=log_level,
                            format='%(asctime)s %(levelname)s: %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')
        logging.debug("Created App object")
        self.notelist = NoteList(self.AUTOSAVE_DELAY, 
                                 lambda *arsg: self.autosave_notelist())
        self.dirname = None
        self.windows = []
        self.gc = GConfWrapper(gconfdir or GCONFDIR)

    def new_notelist(self):
        """Create a new, empty note list"""
        self.notelist.clear()

    def open_notelist(self, dirname):
        """Open a note directory
        
        This loads all notes in the directory, and remembers the name of
        the directory for future operations. This method corresponds to
        the File/Open menu entry.
        
        """
        logging.debug("App.open_notelist: %s" % dirname)
        self.notelist.load(dirname)
        self.dirname = dirname

    def autosave_notelist(self):
        """Automatically save all notes if directory name has been set"""
        if self.dirname:
            self.save_notelist()

    def save_notelist(self):
        """Save all notes
        
        This requires that the directory name has been set. Other than
        not invoking "File/Save as..." automatically, this method corresponds
        to the "File/Save" menu entry.
        
        """
        logging.debug("App.save_notelist")
        if not self.dirname:
            raise DirnameNotSet()
        self.notelist.save(self.dirname)
        self.notelist.make_clean()

    def save_notelist_as(self, dirname):
        """Set new name for directory and save all notes
        
        This method corresponds to to the "File/Save as..." menu entry,
        except it assume someone's already asked the user for the new
        directory name.
        
        """
        logging.debug("App.save_notelist_as: %s" % dirname)
        self.notelist.save(dirname)
        self.dirname = dirname

    def new_window(self):
        """Create a new window showing the note list"""
        w = Window(self)
        self.windows.append(w)
        return w

    def forget_window(self, w):
        """Forget a window that has been closed"""
        if w in self.windows:
            self.windows.remove(w)
        if not self.windows:
            self.quit()


class StatusInfo:

    """Show status information to the user
    
    This is (at least currently) the number of matching notes.
    
    The status is shown in a GtkLabel widget, which is given to the
    initializer as an argument.
    
    """

    def __init__(self, status_label):
        self.widget = status_label
        self.match_count = 0
        
    def get_match_count(self):
        """Return the current match count"""
        return self.match_count
        
    def set_match_count(self, match_count):
        """Update the status information with the new match count"""
        self.match_count = match_count
        self.format()
        
    def format(self):
        """Format information and update it on-screen"""
        text = "%d matching notes" % self.match_count
        self.widget.set_text(text)


class Window:

    """The user visible top-level window
    
    This class is the Controller in the Model/View/Controller scheme.
    The GtkWindow widgets, and its child widgets, are the View, and
    the NoteList is the Model, roughly.
    
    Because this is the class that most directly controls what happens in
    the user interface, and reacts to what the user does, this is the
    messiest of the classes in this application. There seems to be no
    way of doing user interface code in a completely clean fashion.
    
    This class should be instantiated by the App.new_window method.
    
    """

    def __init__(self, app):
        logging.debug("Creating new Window %s" % self)
    
        self.app = app

        xml = gtk.glade.XML(GLADE)

        # Allocate a new visibility column for us. That column determines
        # which notes we show, and is updated whenever the search pattern
        # changes.
        self.visibility_column = app.notelist.add_visibility_column()

        # Create a new GtkTreeModelFilter that references our visibility
        # column.
        self.filter = app.notelist.liststore.filter_new()
        self.filter.set_visible_column(self.visibility_column)

        # Set up the GtkTreeView widget to show the title column in the
        # GtkListStore.
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(None, renderer, 
                                    text=app.notelist.TITLE_COLUMN)
        list_widget = xml.get_widget("note_list")
        list_widget.set_model(self.filter)
        list_widget.append_column(column)

        # Which note are we currently showing in the text window? None,
        # if we're not showing anything.
        self.selected_note = None
        
        # The GtkTreeSelection is what the users uses to select a note.
        self.selection = list_widget.get_selection()
        self.selection.connect("changed", self.on_note_list_selection_changed)
        
        self.window = xml.get_widget("window")
        w = app.gc.get_int("saved-width")
        h = app.gc.get_int("saved-height")
        if w > 0 and h > 0:
            self.window.resize(w, h)
        self.window.connect("configure-event", self.on_window_configure_event)
        
        self.search_field = xml.get_widget("title_and_search")
        self.search_field.connect("changed", self.refilter)
        self.search_field.connect("activate", self.create_new_note)
        self.search_field.connect("focus-out-event", 
                                  self.search_field_focus_out)
        
        self.clear_button = xml.get_widget("clear_button")
        self.clear_button.connect("clicked", self.clear_search_pattern)
        self.clear_button.set_property("can-focus", False)
        
        self.search_button = xml.get_widget("search_button")
        self.search_button.set_property("can-focus", False)
        
        self.status = StatusInfo(xml.get_widget("note_list_title"))

        self.paned = xml.get_widget("note_list_paned")
        p = app.gc.get_int("saved-panedpos") or -1
        if p != -1:
            self.paned.set_position(p)
        
        self.textview = xml.get_widget("textview")
        self.textview.modify_font(pango.FontDescription(FONT))
        self.empty_buffer = self.textview.get_buffer()
        self.clipboard = gtk.Clipboard()

        # We need to set some widgets sensitive or insensitive (greyed
        # out, unselectable in menus, etc) in various situations,
        # primarily when there is a selected note. This is the list of
        # such widgets. In addition the text editing widget is updated,
        # see the set_sensitives_to method.
        self.sensitives = []
        self.sensitives.append(self.textview)
        self.sensitives.append(xml.get_widget("cut"))
        self.sensitives.append(xml.get_widget("copy"))
        self.sensitives.append(xml.get_widget("paste"))
        self.sensitives.append(xml.get_widget("clear"))
        self.sensitives.append(xml.get_widget("delete_note"))
       
        self.set_sensitives_to(False)
        
        self.refilter()

        self.about_dialog = None
        self.about_menuitem = xml.get_widget("about")
        self.open_dialog = xml.get_widget("open_dialog")
        self.save_as_dialog = xml.get_widget("save_as_dialog")
        
        self.delete_dialog = xml.get_widget("delete_dialog")
        self.delete_label = xml.get_widget("delete_label")

        # This bit of code constructs a list of methods for binding to
        # GTK+ signals. This way, we don't have to maintain a list
        # manually, saving editing effort. It's enough to add a method
        # to this class and give the same name in the .glade file.
        dict = {}
        for name, member in inspect.getmembers(self):
            dict[name] = member
        xml.signal_autoconnect(dict)
        
    def close(self):
        """Close the window
        
        This should be called as reaction to the various ways in which a
        user can close a window (or all of them): via the window manager,
        or from the "Close window" menu entry, and so on.
        
        """
        logging.debug("Closing window %s" % self)
        self.app.notelist.remove_visibility_column(self.visibility_column)
        self.app.forget_window(self)

    def select_note(self, note):
        """Select a new note, or select no note"""
        self.selected_note = note
        if note:
            self.set_sensitives_to(True)
            self.textview.set_buffer(note.buffer)
        else:
            self.set_sensitives_to(False)
            self.textview.set_buffer(self.empty_buffer)

    def get_search_pattern(self):
        """Construct a search pattern from the search field contents
        
        See Note.matches for how the pattern should be like.
        
        """
        return self.search_field.get_text().lower().split()

    def set_search_pattern(self, pattern):
        """Set the contents of the search field from a search pattern"""
        self.search_field.set_text(" ".join(pattern))

    def clear_search_pattern(self, *args):
        """Set the search field to empty"""
        self.set_search_pattern([])

    def on_search_button_clicked(self, *args):
        """Do a new search"""
        self.refilter()
        
    def refilter(self, *args):
        """Search for notes matching the current search field
        
        This should be called whenever the search field changes, or the
        search results need to be updated for other reasons.
        
        """
        self.app.notelist.mark_visible_rows(self.visibility_column,
                                            self.get_search_pattern())
        self.update_match_count()

    def update_match_count(self):
        """Update the match count based on the current list of matches"""
        self.status.set_match_count(len(self.get_matching_notes()))

    def get_matching_notes(self):
        """Return list of notes marked as matching
        
        If the search field or any notes have changed after the refilter
        method was last called, this is not reflected in the return value.
        This just returns notes marked as visible according to the latest
        call to refilter.
        
        """
        list = []
        iter = self.filter.get_iter_first()
        while iter:
            note = self.filter.get_value(iter, self.app.notelist.NOTE_COLUMN)
            list.append(note)
            iter = self.filter.iter_next(iter)
        return list

    def create_new_note(self, *args):
        """Create a new note"""
        search_text = self.search_field.get_text()
        if search_text:
            note = Note()
            note.set_filename(search_text)
            note.buffer.place_cursor(note.buffer.get_end_iter())
            self.app.notelist.append_note(note)
            self.refilter()
            self.select_note(note)
            self.textview.grab_focus()

    def set_sensitives_to(self, setting):
        """Set all sensitive widgets to be sensitive or insensitive"""
        for w in self.sensitives:
            w.set_sensitive(setting)
        self.textview.set_property("can-focus", setting)

    def create_about_dialog(self):
        """Create a new About dialog"""
        if self.about_dialog is None:
            self.about_dialog = gtk.AboutDialog()
            self.about_dialog.set_name(NAME)
            self.about_dialog.set_version(VERSION)
            self.about_dialog.set_copyright(COPYRIGHT)
            self.about_dialog.set_comments(COMMENTS)
            self.about_dialog.set_license(LICENSE)
            logo = gtk.gdk.pixbuf_new_from_file(LOGO)
            self.about_dialog.set_logo(logo)

    def show_about_dialog(self, *args):
        """Show the About dialog (create if not created)"""
        self.create_about_dialog()
        self.about_dialog.response(gtk.RESPONSE_CLOSE)
        self.about_dialog.run()
        self.about_dialog.hide()

    def on_window_configure_event(self, window, event):
        """Remember the configuration of the window
        
        This should be called whenever the size of the window changes.
        It should also be called whenever the position of the user-moveable
        divider changes, but I haven't figured out a way to do that.
        
        """
        self.app.gc.set_int("saved-width", event.width)
        self.app.gc.set_int("saved-height", event.height)
        self.app.gc.set_int("saved-panedpos", self.paned.get_position())

    def on_cut_activate(self, *args):
        """Cut selected text in the text editor to the clipboard"""
        self.selected_note.buffer.cut_clipboard(self.clipboard, True)

    def on_copy_activate(self, *args):
        """Copy selected text in text editor to the clipboard"""
        self.selected_note.buffer.copy_clipboard(self.clipboard)

    def on_paste_activate(self, *args):
        """Paste the clipboard to the text editor"""
        self.selected_note.buffer.paste_clipboard(self.clipboard, None, True)

    def on_clear_activate(self, *args):
        """Clear selection in the text editor"""
        if self.selected_note:
            mark = self.selected_note.buffer.get_mark("insert")
            iter = self.selected_note.buffer.get_iter_at_mark(mark)
            self.selected_note.buffer.select_range(iter, iter)

    def on_save_activate(self, *args):
        """Save the note list
        
        This implements the File/Save menu entry.
        
        """
        self.app.save_notelist()

    def on_open_activate(self, *args):
        """Open a new note directory
        
        This implements to the File/Open menu entry.
        
        """
        logging.debug("Window.on_open_activate called")
        result = self.open_dialog.run()
        self.open_dialog.hide()
        logging.debug("Window.on_open_activate: result = %s" % result)
        if result == gtk.RESPONSE_OK:
            self.app.open_notelist(self.open_dialog.get_filename())
            self.refilter()

    def on_save_as_activate(self, *args):
        """Save note directory with a new name
        
        This implements the "File/Save as" menu entry.
        
        """
        result = self.save_as_dialog.run()
        self.save_as_dialog.hide()
        if result == gtk.RESPONSE_OK:
            self.app.save_notelist_as(self.save_as_dialog.get_filename())

    def on_quit_activate(self, *args):
        """Quit the application
        
        This implements the File/Quit menu entry.
        
        """
        if self.app.notelist.is_dirty():
            self.app.save_notelist()
        self.app.forget_window(self)

    on_window_delete_event = on_quit_activate

    def on_note_list_selection_changed(self, selection):
        """React when user changes the selected note"""
        model, iter = selection.get_selected()
        if iter:
            note = model.get_value(iter, self.app.notelist.NOTE_COLUMN)
            self.select_note(note)
        else:
            self.select_note(None)

    def on_delete_note_activate(self, *args):
        """"Delete selected note"""
        if self.selected_note:
            title = self.selected_note.get_title()
            self.delete_label.set_markup('Do you want to remove the note ' +
                                         'titled <b>"%s"</b>?' % title)
        
            result = self.delete_dialog.run()
            self.delete_dialog.hide()
            if result == gtk.RESPONSE_OK:
                self.app.notelist.remove_note(self.app.dirname, 
                                              self.selected_note)
                self.select_note(None)
                self.update_match_count()

    def search_field_focus_out(self, widget, direction):
        text = self.search_field.get_text()
        self.search_field.select_region(len(text), len(text))

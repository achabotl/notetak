#!/usr/bin/python2.4


import filecmp
import os
import shutil
import tempfile
import time
import unittest

import pygtk
pygtk.require("2.0")
import gnome

from notetak import *


def create_file(filename, contents, mtime):
    f = file(filename, "w")
    f.write(contents)
    f.close()
    os.utime(filename, (mtime, mtime))


def read_file(filename):
    f = file(filename, "r")
    data = f.read()
    f.close()
    return data


def get_mark_offset(note, mark_name):
    mark = note.buffer.get_mark(mark_name)
    iter = note.buffer.get_iter_at_mark(mark)
    return iter.get_offset()


class GlobalVariableTestst(unittest.TestCase):

    def test(self):
        self.failUnless(NAME)
        self.failUnless(VERSION)
        self.failUnless(os.path.exists(GLADE))


class NoteTests(unittest.TestCase):

    def setUp(self):
        self.id = "temp"
        self.title = "pink"
        self.body = "pretty"
        self.mtime = 12765
        
        self.filename = self.id + ".note"
        self.contents = self.title + "\n" + self.body
        
        create_file(self.filename, self.contents, self.mtime)

    def tearDown(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)
        if os.path.exists(self.filename + ".new"):
            os.remove(self.filename + ".new")

    def testCreate(self):
        note = Note()
        self.failIfEqual(note.id, None)
        self.failUnlessEqual(note.buffer, None)
        self.failUnlessEqual(note.mtime, None)
        self.failUnlessEqual(note.dirty, False)
        self.failUnlessEqual(note.timeout_id, None)
        self.failUnlessEqual(note.timeout_length, None)
        self.failUnlessEqual(note.timeout_callback, None)
        self.failUnlessEqual(note.immediate_change_callback, None)

    def testLoad(self):
        note = Note()
        note.load(self.filename)
        
        self.failUnlessEqual(note.id, self.id)
        self.failUnlessEqual(note.mtime, self.mtime)
        self.failIfEqual(note.buffer, None)
        
        start, end = note.buffer.get_bounds()
        self.failUnlessEqual(note.buffer.get_text(start, end), self.contents)
        
        self.failUnlessEqual(get_mark_offset(note, "insert"), 0)
        self.failUnlessEqual(get_mark_offset(note, "selection_bound"), 0)

    def testLoadWithoutDotNoteInFilename(self):
        note = Note()
        note.load("/dev/null")
        self.failUnlessEqual(note.id, "null")

    def testSave(self):
        note = Note()
        note.load(self.filename)
        note.save(self.filename + ".new")
        self.failUnlessEqual(read_file(self.filename), 
                             read_file(self.filename + ".new"))
        self.failUnlessEqual(os.stat(self.filename + ".new").st_mtime,
                             note.mtime)

    def testRemove(self):
        note = Note()
        note.load(self.filename)
        self.failUnless(os.path.exists(self.filename))
        note.remove(self.filename)
        self.failIf(os.path.exists(self.filename))

    def testRemoveNonExistent(self):
        note = Note()
        note.load(self.filename)
        note.remove(self.filename + "pink")
        self.failIf(os.path.exists(self.filename + "pink"))

    def testGetTitle(self):
        note = Note()
        note.load(self.filename)
        self.failUnlessEqual(note.get_title(), self.title)

    def testGetTitleFromUnloadedNote(self):
        note = Note()
        self.failUnlessEqual(note.get_title(), "")

    def testSetText(self):
        note = Note()
        self.failUnlessEqual(note.get_text(), "")
        note.set_text("pink")
        self.failUnlessEqual(note.get_text(), "pink")

    def testTouch(self):
        note = Note()
        note.now = lambda: 12765
        note.touch()
        self.failUnlessEqual(note.mtime, 12765)

    def testAutomaticMtimeUpdate(self):
        note = Note()
        note.load(self.filename)
        self.failUnless(note.mtime < time.time())
        note.buffer.set_text("new stuff")
        self.failUnless(time.time() - note.mtime <= 1.0)

    def remember_timestamp(self, note):
        self.timestamp_note = note
        self.timestamp = time.time()

    def testImmediateChangeCallback(self):
        note = Note()
        self.timestamp = None
        self.timestamp_note = None
        note.set_immediate_change_callback(self.remember_timestamp)
        self.failUnlessEqual(note.immediate_change_callback, 
                             self.remember_timestamp)
        note.set_text("foo")
        self.failUnlessEqual(self.timestamp_note, note)

    def testChangeTimeout(self):
        note = Note()
        self.timestamp = None
        self.timestamp_note = None
        note.set_change_timeout(1000, self.remember_timestamp)
        self.failUnlessEqual(note.timeout_length, 1000)
        self.failUnlessEqual(note.timeout_callback, self.remember_timestamp)
        note.set_text("foo")
        self.failIfEqual(note.timeout_id, None)
        # We simulate the main loop here, because we can't run it for real.
        note.buffer_changed_timeout()
        now = time.time() + 2
        self.failUnlessEqual(self.timestamp_note, note)
        self.failUnless(now - self.timestamp >= 1.0)
        self.failUnless(now - self.timestamp <= 3.0)

    def testStopChangeTimeout(self):
        note = Note()
        self.timestamp = None
        self.timestamp_note = None
        note.set_change_timeout(1000, self.remember_timestamp)
        note.set_text("foo")
        note.stop_change_timeout()
        self.failUnlessEqual(note.timeout_id, None)
        self.failUnlessEqual(self.timestamp, None)
        self.failUnlessEqual(self.timestamp_note, None)
        # We simulate the main loop here, because we can't run it for real.
        note.buffer_changed_timeout()
        now = time.time() + 2
        self.failUnlessEqual(self.timestamp, None)
        self.failUnlessEqual(self.timestamp_note, None)

    def testDirtyFromBufferChange(self):
        note = Note()
        note.load(self.filename)
        note.buffer.set_text("new stuff")
        self.failUnlessEqual(note.dirty, True)

    def testCleanAfterSave(self):
        note = Note()
        note.load(self.filename)
        note.touch()
        note.save(self.filename + ".new")
        self.failUnlessEqual(note.dirty, False)

    def testMatches(self):
        note = Note()
        note.load(self.filename)
        self.failUnlessEqual(note.matches(["pink"]), True)
        self.failUnlessEqual(note.matches(["!pink"]), False)
        self.failUnlessEqual(note.matches(["xyzzy"]), False)
        self.failUnlessEqual(note.matches(["!xyzzy"]), True)
        self.failUnlessEqual(note.matches(["pink", "xyzzy"]), False)
        self.failUnlessEqual(note.matches(["pink", "pretty"]), True)


class NoteListTestBase(unittest.TestCase):

    def setUp(self):
        self.dirname = "unittestdir"
        self.dirname = os.path.abspath(self.dirname)
        self.id1 = "pink"
        self.id2 = "pretty"

        self.filename1 = os.path.join(self.dirname, self.id1 + ".note")
        self.filename2 = os.path.join(self.dirname, self.id2 + ".note")
        
        self.title1 = "pink note"
        self.title2 = "pretty note"
        
        self.mtime1 = 12765
        self.mtime2 = 65535

        os.mkdir(self.dirname)
        create_file(self.filename1, self.title1 + "\n", self.mtime1)
        create_file(self.filename2, self.title2 + "\n", self.mtime2)
 
        self.subdir = os.path.join(self.dirname, "subdir")
        os.mkdir(self.subdir)

    def tearDown(self):
        if os.path.exists(self.filename1):
            os.remove(self.filename1)
        if os.path.exists(self.filename2):
            os.remove(self.filename2)
        if os.path.exists(self.subdir):
            os.rmdir(self.subdir)
        if os.path.exists(self.dirname):
            os.rmdir(self.dirname)


class NoteListTests(NoteListTestBase):

    def testCreate(self):
        notelist = NoteList()
        self.failUnlessEqual(notelist.get_notes(), [])
        self.failUnlessEqual(notelist.get_visibility_columns(), [])

    def testAppendNote(self):
        notelist = NoteList()
        note = Note()
        notelist.append_note(note)
        self.failUnlessEqual(notelist.get_notes(), [note])
        notelist.append_note(note)
        self.failUnlessEqual(notelist.get_notes(), [note, note])

    def testRemoveNote(self):
        notelist = NoteList()
        notelist.load(self.dirname)
        notes = notelist.get_notes()
        while notes:
            note = notes[-1]
            notes = notes[:-1]
            filename = notelist.note_filename(self.dirname, note)
            self.failUnless(os.path.isfile(filename))
            notelist.remove_note(self.dirname, note)
            self.failIf(os.path.exists(filename))
            self.failUnlessEqual(notelist.get_notes(), notes)
        self.failUnlessEqual(notelist.get_notes(), [])

    def testRemoveNoteThatDoesNotExist(self):
        notelist = NoteList()
        notelist.load(self.dirname)
        notes = notelist.get_notes()
        notelist.remove_note(self.dirname, self)
        self.failUnlessEqual(notelist.get_notes(), notes)

    def testNoNoteIterWhenEmpty(self):
        notelist = NoteList()
        note = Note()
        self.failUnlessEqual(notelist.find_iter_for_note(note), None)

    def testNothingInTitleColumnWhenEmpty(self):
        notelist = NoteList()
        note = Note()
        self.failUnlessEqual(notelist.get_from_title_column(note), None)

    def testNoteChangesUpdateTitleColumn(self):
        notelist = NoteList()
        notelist.load(self.dirname)
        for note in notelist.get_notes():
            self.failUnlessEqual(note.get_title(), 
                                 notelist.get_from_title_column(note))
        note = notelist.get_notes()[0]
        note.set_text("pink really is beautiful\nyay!")
        self.failUnlessEqual(note.get_title(),
                             notelist.get_from_title_column(note))

    def testClear(self):
        notelist = NoteList()
        notelist.load(self.dirname)
        notelist.clear()
        self.failUnlessEqual(notelist.get_notes(), [])

    def testLoad(self):
        notelist = NoteList()
        notelist.load(self.dirname)
        self.failUnlessEqual(len(notelist.get_notes()), 2)

    def list_files_only(self, dirname):
        return [x for x in os.listdir(dirname)
                if os.path.isfile(os.path.join(dirname, x))]

    def dirs_are_equal(self, dirname1, dirname2):
        files1 = sorted(self.list_files_only(dirname1))
        files2 = sorted(self.list_files_only(dirname2))
        self.failUnlessEqual(files1, files2)
        match, mismatch, errors = filecmp.cmpfiles(dirname1, dirname2, files1)
        self.failUnlessEqual(sorted(match), files1)
        self.failUnlessEqual(mismatch, [])
        self.failUnlessEqual(errors, [])

        for basename in files1:
            filename1 = os.path.join(dirname1, basename)
            filename2 = os.path.join(dirname2, basename)
            self.failUnlessEqual(os.stat(filename1).st_mtime,
                                 os.stat(filename2).st_mtime)

    def testSave(self):
        notelist = NoteList()
        notelist.load(self.dirname)
        notelist.save(self.dirname + ".new")
        self.dirs_are_equal(self.dirname, self.dirname + ".new")
        shutil.rmtree(self.dirname + ".new")

    def testSaveDirty(self):
        notelist = NoteList()
        notelist.load(self.dirname)
        notes = notelist.get_notes()
        self.failUnlessEqual(len(notes), 2)

        notes[0].buffer.set_text("yeehaa")
        notelist.save_dirty(self.dirname + ".new")

        files = self.list_files_only(self.dirname)
        match, mismatch, errors = filecmp.cmpfiles(self.dirname,
                                                   self.dirname + ".new",
                                                   files)
        self.failUnlessEqual(match, [])
        self.failUnlessEqual(mismatch, [notes[0].id + ".note"])
        self.failUnlessEqual(errors, [notes[1].id + ".note"])
        shutil.rmtree(self.dirname + ".new")

    def testFindMatching(self):
        notelist = NoteList()
        notelist.load(self.dirname)
        notes = notelist.get_notes()
        self.failUnless(notes[0].matches(["pink"]))
        self.failUnless(notes[1].matches(["pretty"]))

        self.failUnlessEqual(notelist.find_matching(["pink"]), [notes[0]])
        self.failUnlessEqual(notelist.find_matching(["pretty"]), [notes[1]])
        self.failUnlessEqual(notelist.find_matching(["pretty", "pink"]), [])
        self.failUnlessEqual(notelist.find_matching(["black"]), [])
        self.failUnlessEqual(notelist.find_matching(["!black"]), notes)
        self.failUnlessEqual(notelist.find_matching(["pink", "note"]), 
                             [notes[0]])
        self.failUnlessEqual(notelist.find_matching(["pretty", "note"]), 
                             [notes[1]])

    def testTooManyVisibilityColumnsException(self):
        self.failUnless("Exception" not in str(TooManyVisibilityColumns()))

    def all_visibility_columns_exist(self, notelist):
        self.failUnlessEqual(sorted(range(notelist.MAX_VISIBILITY_COLUMNS)),
                             sorted(notelist.visibility_columns +
                                    notelist.available_visibility_columns))

    def testAddVisibilityColumn(self):
        notelist = NoteList()
        self.all_visibility_columns_exist(notelist)
        col = notelist.add_visibility_column()
        self.failUnlessEqual(notelist.get_visibility_columns(), [col])
        self.all_visibility_columns_exist(notelist)

    def testAddTooManyVisibilityColumns(self):
        notelist = NoteList()
        for i in range(notelist.MAX_VISIBILITY_COLUMNS):
            notelist.add_visibility_column()
        self.failUnlessRaises(TooManyVisibilityColumns,
                              notelist.add_visibility_column)

    def testRemoveVisibilityColumn(self):
        notelist = NoteList()
        col = notelist.add_visibility_column()
        notelist.remove_visibility_column(col)
        self.failUnlessEqual(notelist.get_visibility_columns(), [])
        self.all_visibility_columns_exist(notelist)

    def testMarkVisibleRows(self):
        notelist = NoteList()
        notelist.load(self.dirname)

        notes = notelist.get_notes()
        self.failUnlessEqual(len(notes), 2)
        self.failUnless(notes[0].matches(["pink"]))
        self.failUnless(notes[1].matches(["pretty"]))

        col = notelist.add_visibility_column()
        self.failUnlessEqual(notelist.get_visible_notes(col), [])

        notelist.mark_visible_rows(col, ["pink"])
        self.failUnlessEqual(notelist.get_visible_notes(col), [notes[0]])

        notelist.mark_visible_rows(col, ["pretty"])
        self.failUnlessEqual(notelist.get_visible_notes(col), [notes[1]])

        notelist.mark_visible_rows(col, ["pink", "pretty"])
        self.failUnlessEqual(notelist.get_visible_notes(col), [])

        notelist.mark_visible_rows(col, ["pink", "note"])
        self.failUnlessEqual(notelist.get_visible_notes(col), [notes[0]])

        notelist.mark_visible_rows(col, ["note"])
        self.failUnlessEqual(notelist.get_visible_notes(col), 
                             notelist.get_notes())

    def testDirty(self):
        notelist = NoteList()
        self.failUnlessEqual(notelist.is_dirty(), False)

        note = Note()
        notelist.append_note(note)
        self.failUnlessEqual(notelist.is_dirty(), True)

        notelist.make_clean()
        self.failUnlessEqual(notelist.is_dirty(), False)

        note.touch()
        self.failUnlessEqual(notelist.is_dirty(), True)

        notelist.make_clean()
        self.failUnlessEqual(notelist.is_dirty(), False)


class AppTests(NoteListTestBase):

    def testCreate(self):
        app = App()
        self.failIfEqual(app.notelist, None)
        self.failUnlessEqual(app.dirname, None)
        self.failUnlessEqual(app.windows, [])

    def testNewNoteList(self):
        app = App()
        note = Note()
        app.notelist.append_note(note)
        
        notelist = app.notelist
        app.new_notelist()
        self.failUnlessEqual(app.notelist, notelist)
        self.failUnlessEqual(app.notelist.get_notes(), [])

    def testOpenNoteList(self):
        app = App()
        app.open_notelist(self.dirname)
        self.failUnlessEqual(len(app.notelist.get_notes()), 2)
        self.failUnlessEqual(app.dirname, self.dirname)

    def testDirnameNotSetException(self):
        self.failIf("Exception" in str(DirnameNotSet()))

    def testAutoSaveNoteListWithoutDirname(self):
        app = App()
        app.open_notelist(self.dirname)
        app.dirname = None
        notes = app.notelist.get_notes()
        notes[0].now = lambda: 1999
        notes[0].touch()
        filename = os.path.join(self.dirname, notes[0].id + ".note")
        os.remove(filename)
        app.autosave_notelist()
        self.failIf(os.path.exists(filename))

    def testSaveNoteListWithoutDirname(self):
        app = App()
        self.failUnlessRaises(DirnameNotSet, app.save_notelist)

    def testAutoSaveNoteList(self):
        app = App()
        app.open_notelist(self.dirname)
        notes = app.notelist.get_notes()
        notes[0].now = lambda: 1999
        notes[0].touch()
        app.autosave_notelist()
        filename = os.path.join(self.dirname, notes[0].id + ".note")
        self.failUnlessEqual(os.stat(filename).st_mtime, 1999)

    def testSaveNoteList(self):
        app = App()
        app.open_notelist(self.dirname)
        notes = app.notelist.get_notes()
        notes[0].now = lambda: 1999
        notes[0].touch()
        app.save_notelist()
        filename = os.path.join(self.dirname, notes[0].id + ".note")
        self.failUnlessEqual(os.stat(filename).st_mtime, 1999)

    def testSaveNoteListAs(self):
        app = App()
        app.open_notelist(self.dirname)
        app.save_notelist_as(self.dirname + ".new")
        self.failUnless(os.path.exists(self.dirname + ".new"))
        self.failUnlessEqual(app.dirname, self.dirname + ".new")
        shutil.rmtree(self.dirname + ".new")

    def testNewWindow(self):
        app = App()
        w = app.new_window()
        self.failUnlessEqual(app.windows, [w])

    def testForgetWindow(self):
        app = App()
        w1 = app.new_window()
        w2 = app.new_window()
        app.forget_window(w1)
        self.failUnlessEqual(app.windows, [w2])

    def app_has_quit(self):
        self.app_quits += 1

    def testForgetLastWindow(self):
        app = App()
        self.app_quits = 0
        app.quit = lambda: self.app_has_quit()
        w = app.new_window()
        app.forget_window(w)
        self.failUnlessEqual(app.windows, [])
        self.failUnlessEqual(self.app_quits, 1)


class WindowTests(NoteListTestBase):

    def testCreate(self):
        app = App()
        w = app.new_window()
        self.failUnlessEqual(w.app, app)
        self.failUnlessEqual(app.notelist.visibility_columns, 
                             [w.visibility_column])
        self.failIfEqual(w.filter, None)
        self.failUnlessEqual(w.selected_note, None)
        self.failIfEqual(w.textview, None)

    def app_has_quit(self):
        self.app_quits += 1

    def testClose(self):
        self.app_quits = 0
        app = App()
        app.quit = self.app_has_quit
        w = app.new_window()
        w.close()
        self.failUnlessEqual(self.app_quits, 1)
        self.failUnlessEqual(app.windows, [])
        self.failUnlessEqual(app.notelist.visibility_columns, [])

    def testSelectNote(self):
        app = App()
        app.open_notelist(self.dirname)
        notes = app.notelist.get_notes()
        w = app.new_window()
        w.select_note(notes[0])
        self.failUnlessEqual(w.selected_note, notes[0])
        w.select_note(None)
        self.failUnlessEqual(w.selected_note, None)

    def testTwoWindows(self):
        app = App()
        w1 = app.new_window()
        w2 = app.new_window()
        self.failIfEqual(w1.window, w2.window)
        self.failIfEqual(w1.textview, w2.textview)


class DeleteNoteTests(NoteListTestBase):

    def setUp(self):
        NoteListTestBase.setUp(self)
        self.app = App()
        self.app.open_notelist(self.dirname)
        self.w = self.app.new_window()

    def testDeleteNoteWhenNoneSelected(self):
        notes1 = self.app.notelist.get_notes()
        self.w.on_delete_note_activate()
        notes2 = self.app.notelist.get_notes()
        self.failUnlessEqual(notes1, notes2)

    def close_delete_dialog(self, dialog, *args):
        dialog.response(gtk.RESPONSE_OK)

    def testDeleteNoteWhenOneIsSelected(self):
        self.w.delete_dialog.connect("expose-event", self.close_delete_dialog)

        notes1 = self.app.notelist.get_notes()
        self.w.select_note(notes1[1])
        self.w.on_delete_note_activate()
        notes2 = self.app.notelist.get_notes()
        self.failUnlessEqual(notes1[:1], notes2)
        self.failUnlessEqual(len(notes2), self.w.status.get_match_count())

    def testDeleteWhenDirNotOpened(self):
        self.w.app.dirname = None
        self.w.delete_dialog.connect("expose-event", self.close_delete_dialog)

        notes1 = self.app.notelist.get_notes()
        self.w.select_note(notes1[1])
        self.w.on_delete_note_activate()
        notes2 = self.app.notelist.get_notes()
        self.failUnlessEqual(notes1[:1], notes2)
        

class SensitiveWidgetsTests(NoteListTestBase):

    def sensitivity_is(self, window, wanted_sensitivity):
        ok = True
        for w in window.sensitives:
            ok = w.get_property("sensitive") == wanted_sensitivity and ok
        return ok

    def can_focus_is(self, window, wanted):
        return window.textview.get_property("can-focus") == wanted

    def testInitiallyInsensitive(self):
        app = App()
        w = app.new_window()
        self.failUnless(self.sensitivity_is(w, False))

    def testChange(self):
        app = App()
        w = app.new_window()
        for value in [True, False, True, False]:
            w.set_sensitives_to(value)
            self.failUnless(self.sensitivity_is(w, value))

    def testNoteSelectionSetsSensitivityAndFocusability(self):
        app = App()
        app.open_notelist(self.dirname)
        notes = app.notelist.get_notes()
        w = app.new_window()
        self.failUnless(self.sensitivity_is(w, False))
        self.failUnless(self.can_focus_is(w, False))
        w.select_note(notes[0])
        self.failUnless(self.sensitivity_is(w, True))
        self.failUnless(self.can_focus_is(w, True))
        w.select_note(None)
        self.failUnless(self.sensitivity_is(w, False))
        self.failUnless(self.can_focus_is(w, False))


class SearchFieldTests(NoteListTestBase):

    def testSearchPatternIsInitiallyEmpty(self):
        app = App()
        w = app.new_window()
        self.failUnlessEqual(w.get_search_pattern(), [])

    def testAllNotesMatchEmptySearchPattern(self):
        app = App()
        app.open_notelist(self.dirname)
        w = app.new_window()
        self.failUnlessEqual(w.get_matching_notes(), app.notelist.get_notes())

    def testPatternIsAllLowerCase(self):
        app = App()
        w = app.new_window()
        w.set_search_pattern(["pink", "PRETTY"])
        self.failUnlessEqual(w.get_search_pattern(), ["pink", "pretty"])

    def testPatternChangeCausesRefilter(self):
        app = App()
        app.open_notelist(self.dirname)
        w = app.new_window()
        w.set_search_pattern(["pink"])
        self.failUnlessEqual(w.get_matching_notes(), 
                             app.notelist.find_matching(["pink"]))

    def testSearchButtonCausesRefilter(self):
        app = App()
        app.open_notelist(self.dirname)
        w = app.new_window()
        notes = app.notelist.get_notes()
        pattern = notes[0].get_title().split()
        w.set_search_pattern(pattern)
        matching = w.get_matching_notes()
        notes[0].set_text("black")
        self.failUnlessEqual(matching, w.get_matching_notes())
        w.search_button.clicked()
        self.failUnlessEqual([], w.get_matching_notes())

    def testClearButtonClearsSearchPattern(self):
        app = App()
        app.open_notelist(self.dirname)
        w = app.new_window()
        w.set_search_pattern(["pink"])
        w.clear_button.clicked()
        self.failUnlessEqual(w.get_search_pattern(), [])
        self.failUnlessEqual(w.get_matching_notes(), app.notelist.get_notes())

    def testSearchFieldEnterCreatesNewNote(self):
        app = App()
        w = app.new_window()
        w.set_search_pattern(["black", "is", "beautiful,", "too"])
        w.search_field.activate()
        notes = app.notelist.get_notes()
        self.failUnlessEqual(len(notes), 1)
        self.failUnlessEqual(w.get_matching_notes(), notes)
        note = notes[0]
        self.failUnlessEqual(note.get_text(), "black is beautiful, too\n")
        self.failUnlessEqual(w.selected_note, note)
        self.failUnless(w.textview.is_focus())
        
        # Is the cursor at the end of the new buffer?
        mark = note.buffer.get_insert()
        iter = note.buffer.get_iter_at_mark(mark)
        self.failUnlessEqual(iter.get_offset(), note.buffer.get_char_count())

    def testSearchFieldEnterDoesNotCreateNewNoteIfEmpty(self):
        app = App()
        w = app.new_window()
        w.set_search_pattern([])
        w.search_field.activate()
        self.failUnlessEqual(app.notelist.get_notes(), [])

    def testLosesSelectionWhenLosingFocus(self):
        app = App()
        w = app.new_window()
        w.set_search_pattern(["foo"])
        w.search_field.select_region(0, 3)
        w.search_field_focus_out(None, None)
        self.failUnlessEqual(w.search_field.get_selection_bounds(), ())


class StatusInfoTests(unittest.TestCase):

    def setUp(self):
        self.si = StatusInfo(gtk.Label(""))
    
    def tearDown(self):
        self.si = None

    def testCreate(self):
        self.failUnlessEqual(self.si.match_count, 0)

    def testSetMatchCount(self):
        self.si.set_match_count(12765)
        self.failUnlessEqual(self.si.match_count, 12765)
        self.failIfEqual(self.si.widget.get_text(), "")


class RefilterUpdatesCountInStatus(NoteListTestBase):

    def testNoNotes(self):
        app = App()
        w = app.new_window()
        self.failUnlessEqual(w.status.match_count, 0)

    def testNoMatchingNotes(self):
        app = App()
        app.open_notelist(self.dirname)
        w = app.new_window()
        w.set_search_pattern(["unmatchword"])
        self.failUnlessEqual(w.status.match_count, 0)

    def testMatchingNotes(self):
        app = App()
        app.open_notelist(self.dirname)
        w = app.new_window()
        w.set_search_pattern(["pink"])
        self.failUnlessEqual(w.status.match_count, 1)


class SelectedNoteTests(NoteListTestBase):

    def testNoInitialNote(self):
        app = App()
        app.open_notelist(self.dirname)
        w = app.new_window()
        self.failUnlessEqual(w.textview.get_buffer(), w.empty_buffer)
        self.failUnlessEqual(w.selected_note, None)

    def testSelectNote(self):
        app = App()
        app.open_notelist(self.dirname)
        w = app.new_window()
        note = app.notelist.get_notes()[0]
        w.select_note(note)
        self.failUnlessEqual(w.selected_note, note)
        self.failUnlessEqual(w.textview.get_buffer(), note.get_buffer())

    def testUnSelectNote(self):
        app = App()
        app.open_notelist(self.dirname)
        w = app.new_window()
        note = app.notelist.get_notes()[0]
        w.select_note(note)
        w.select_note(None)
        self.failUnlessEqual(w.selected_note, None)
        self.failUnlessEqual(w.textview.get_buffer(), w.empty_buffer)

    def testSelectionSelectsOneThenNone(self):
        app = App()
        app.open_notelist(self.dirname)
        w = app.new_window()
        note = app.notelist.get_notes()[1]
        iter = w.filter.get_iter_first()
        while iter:
            if w.filter.get_value(iter, app.notelist.NOTE_COLUMN) == note:
                break
            iter = w.filter.iter_next(iter)
        self.failIfEqual(iter, None)
        w.selection.select_iter(iter)
        self.failUnlessEqual(w.selected_note, note)

        w.selection.unselect_all()
        self.failUnlessEqual(w.selected_note, None)


class AboutDialogTests(unittest.TestCase):

    def testHasDialogAsAttribute(self):
        app = App()
        w = app.new_window()
        self.failUnlessEqual(w.about_dialog, None)

    def testCreate(self):
        app = App()
        w = app.new_window()
        w.create_about_dialog()
        self.failUnlessEqual(w.about_dialog.get_name(), NAME)
        self.failUnlessEqual(w.about_dialog.get_version(), VERSION)
        self.failUnlessEqual(w.about_dialog.get_copyright(), COPYRIGHT)
        self.failUnlessEqual(w.about_dialog.get_comments(), COMMENTS)
        self.failUnlessEqual(w.about_dialog.get_license(), LICENSE)

    def close_about_dialog(self, dialog, *args):
        self.about_dialog_closed = True
        dialog.response(gtk.RESPONSE_CLOSE)

    def testShow(self):
        app = App()
        w = app.new_window()
        # This is a little bit tricky: normally the About dialog needs the
        # user to click on the "Close" button to go away, but obviously
        # we don't want that to happen with automatic testing. Therefore,
        # we connect to the expose-event signal, which gets sent when the
        # window shows up on the screen. Then we immediately tell the 
        # dialog to close itself. This makes the test pass without user
        # interaction, but tests the code path.
        w.create_about_dialog()
        w.about_dialog.connect("expose-event", self.close_about_dialog)
        self.about_dialog_closed = False
        w.about_menuitem.activate()
        self.failUnless(self.about_dialog_closed)


class GconfTests(unittest.TestCase):

    def testDirIsForDevelopment(self):
        self.failUnless(GCONFDIR.endswith("Development"))

    def testGconfGetsInitialized(self):
        app = App()
        self.failIfEqual(app.gc, None)

    def testGettingNonexistentKeyReturnsDefaultValue(self):
        app = App()
        self.failUnlessEqual(app.gc.get_int("nonexistent"), 0)

    def testGettingNonIntegerReturnsDefaultValue(self):
        app = App()
        app.gc.set_string("notint", "pink")
        self.failUnlessEqual(app.gc.get_int("notint"), 0)

    def testGettingValidIntegerReturnsItAndNotDefaultValue(self):
        app = App()
        app.gc.set_int("int", 42)
        self.failUnlessEqual(app.gc.get_int("int"), 42)


class WindowSizeTests(unittest.TestCase):

    def testNewWindowGetsRememberedSize(self):
        app = App()
        app.gc.set_int("saved-width", 386)
        app.gc.set_int("saved-height", 400)
        app.gc.set_int("saved-panedpos", 128)
        w = app.new_window()
        self.failUnlessEqual(w.window.get_size(), (386, 400))
        self.failUnlessEqual(w.paned.get_position(), 128)

    def testWindowResizeChangesRememberedSizes(self):
        app = App()
        app.gc.set_int("saved-width", 384)
        app.gc.set_int("saved-height", 384)
        app.gc.set_int("saved-panedpos", 128)

        w = app.new_window()
        # We simulate the resizing here. There seems to be no
        # deterministic way to wait for the configure event being called
        # after w.window.resize() gets called.
        class Event:
            width = 512
            height = 512
        w.on_window_configure_event(None, Event())

        self.failUnlessEqual(app.gc.get_int("saved-width"), 512)
        self.failUnlessEqual(app.gc.get_int("saved-height"), 512)
        self.failUnlessEqual(app.gc.get_int("saved-panedpos"), 128)


class TextViewEditingTests(NoteListTestBase):

    def setUp(self):
        NoteListTestBase.setUp(self)
        app = App()
        app.open_notelist(self.dirname)
        self.note = app.notelist.get_notes()[0]
        self.w = app.new_window()
        self.w.select_note(self.note)
        self.note.buffer.select_range(self.note.buffer.get_start_iter(),
                                      self.note.buffer.get_end_iter())

    def testCut(self):
        self.w.on_cut_activate()
        self.failUnlessEqual(self.note.get_text(), "")

    def testCopy(self):
        text = self.note.get_text()
        self.w.on_copy_activate()
        self.failUnlessEqual(self.note.get_text(), text)

    def testPaste(self):
        text = self.note.get_text()
        self.w.on_cut_activate()
        self.w.on_paste_activate()
        self.failUnlessEqual(self.note.get_text(), text)

    def testClear(self):
        self.w.on_clear_activate()
        self.failUnlessEqual(get_mark_offset(self.note, "insert"), 0)
        self.failUnlessEqual(get_mark_offset(self.note, "selection_bound"), 0)


class FileMenuTests(NoteListTestBase):

    def setUp(self):
        NoteListTestBase.setUp(self)
        self.app = App()
        self.app.open_notelist(self.dirname)
        self.note = self.app.notelist.get_notes()[0]
        self.w = self.app.new_window()
        self.w.select_note(self.note)
        self.note.buffer.select_range(self.note.buffer.get_start_iter(),
                                      self.note.buffer.get_end_iter())

    def testGetsDirtyAfterCut(self):
        self.w.on_cut_activate()
        self.failUnlessEqual(self.note.dirty, True)
        
    def testSave(self):
        self.w.on_cut_activate()
        self.w.on_save_activate()
        self.failUnlessEqual(self.note.dirty, False)

    def choose(self, dialog, *args):
        if self.chosen in dialog.get_filenames():
            dialog.response(gtk.RESPONSE_OK)

    def testOpen(self):
        app = App()
        w = app.new_window()
        self.chosen = self.dirname
        w.open_dialog.select_filename(self.chosen)
        w.open_dialog.connect("selection-changed", self.choose)
        w.on_open_activate()
        self.failUnlessEqual(app.dirname, self.chosen)
        
        # Make sure the search field is empty, and the match list shows
        # all notes, and that the match count is updated.
        notes = app.notelist.get_notes()
        self.failUnlessEqual(w.get_search_pattern(), [])
        self.failUnlessEqual(w.get_matching_notes(), notes)
        self.failUnlessEqual(w.status.get_match_count(), len(notes))

        # Make sure the match list is sorted.
        titles = [note.get_title() for note in notes]
        self.failUnlessEqual(titles, sorted(titles))

    def testSaveAs(self):
        app = App()
        w = app.new_window()
        self.chosen = tempfile.mkdtemp()
        w.save_as_dialog.select_filename(self.chosen)
        w.save_as_dialog.connect("selection-changed", self.choose)
        w.on_save_as_activate()
        shutil.rmtree(self.chosen)
        self.failUnlessEqual(app.dirname, self.chosen)

    def app_quit(self):
        self.app_quit_called = True

    def testQuit(self):
        app = App()
        app.open_notelist(self.dirname)
        
        # Make a change. This should get saved automatically.
        note = app.notelist.get_notes()[0]
        note.set_text("pink sure is pretty today")
        id = note.id
        text = note.get_text()

        self.app_quit_called = False
        app.quit = self.app_quit
        w = app.new_window()
        w.on_quit_activate()
        self.failUnless(self.app_quit_called)
        
        # Make sure the change was saved automatically on quit.
        app2 = App()
        app2.open_notelist(self.dirname)
        note2 = app2.notelist.get_notes()[0]
        self.failUnlessEqual(note2.id, id)
        self.failUnlessEqual(note2.get_text(), text)

    def testWindowManagerClose(self):
        app = App()
        self.app_quit_called = False
        app.quit = self.app_quit
        w = app.new_window()
        w.on_window_delete_event()
        self.failUnless(self.app_quit_called)


if __name__ == "__main__":
    gnome.init(NAME, VERSION)
    unittest.main()

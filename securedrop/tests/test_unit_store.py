#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import unittest
import zipfile

# Set environment variable so config.py uses a test environment
os.environ['SECUREDROP_ENV'] = 'test'

import crypto_util
from common import SetUp, TearDown, TestSource, TestSubmission
import config
from db import db_session, Source
import store


class TestStore(unittest.TestCase):

    """The set of tests for store.py."""

    def setUp(self):
        SetUp.setup()

    def tearDown(self):
        TearDown.teardown()
        db_session.remove()

    def test_verify(self):
        with self.assertRaises(store.PathException):
            store.verify(os.path.join(config.STORE_DIR, '..', 'etc', 'passwd'))
        with self.assertRaises(store.PathException):
            store.verify(config.STORE_DIR + "_backup")

    def test_get_zip(self):
        source, _ = TestSource.init_source()
        submissions = TestSubmission.submit(source, 2)
        filenames = [os.path.join(config.STORE_DIR,
                                  source.filesystem_id,
                                  submission.filename)
                     for submission in submissions]

        archive = zipfile.ZipFile(store.get_bulk_archive(filenames))
        archivefile_contents = archive.namelist()

        for archived_file, actual_file in zip(archivefile_contents, filenames):
            actual_file_content = open(actual_file).read()
            zipped_file_content = archive.read(archived_file)
            self.assertEquals(zipped_file_content, actual_file_content)

    def test_rename_valid_submission(self):
        source, _ = TestSource.init_source()
        old_journalist_filename = source.journalist_filename
        old_filename = TestSubmission.submit(source, 1)[0].filename
        new_journalist_filename = 'nestor_makhno'
        expected_filename = old_filename.replace(old_journalist_filename,
                                                 new_journalist_filename)
        actual_filename = store.rename_submission(source.filesystem_id, old_filename,
                                                  new_journalist_filename)
        self.assertEquals(actual_filename, expected_filename)

if __name__ == "__main__":
    unittest.main(verbosity=2)

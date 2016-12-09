#!/usr/bin/env python
# -*- coding: utf-8 -*-
import common
import os
import unittest

from flask_testing import TestCase
import mock
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

import journalist
import crypto_util
import common
os.environ['SECUREDROP_ENV'] = 'test'
from db import (db_session, Journalist, Submission, Source, Reply,
                get_one_or_else)

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)


class TestDatabase(TestCase):

    def create_app(self):
        return journalist.app

    def setUp(self):
        common.shared_setup()

    def tearDown(self):
        common.shared_teardown()

    @mock.patch('flask.abort')
    def test_get_one_or_else_returns_one(self, mock):
        new_journo = Journalist(username="alice", password="sekret")
        db_session.add(new_journo)
        db_session.commit()

        query = Journalist.query.filter(Journalist.username == new_journo.username)
        selected_journo = get_one_or_else(query, logger, mock)
        self.assertEqual(new_journo, selected_journo)

    @mock.patch('flask.abort')
    def test_get_one_or_else_multiple_results(self, mock):
        journo_1 = Journalist(username="alice", password="sekret")
        journo_2 = Journalist(username="bob", password="sekret")
        db_session.add_all([journo_1, journo_2])
        db_session.commit()

        selected_journos = get_one_or_else(Journalist.query, logger, mock)
        mock.assert_called_with(500)

    @mock.patch('flask.abort')
    def test_get_one_or_else_no_result_found(self, mock):
        query = Journalist.query.filter(Journalist.username == "alice")
        selected_journos = get_one_or_else(query, logger, mock)
        mock.assert_called_with(404)

    # Check __repr__ do not throw exceptions

    def test_submission_string_representation(self):
        sid = crypto_util.hash_codename(crypto_util.genrandomid())
        codename = crypto_util.display_id()
        crypto_util.genkeypair(sid, codename)
        source = Source(sid, codename)
        db_session.add(source)
        db_session.commit()
        files = ['1-abc1-msg.gpg', '2-abc2-msg.gpg']
        filenames = common.setup_test_docs(sid, files)
        test_submission = Submission.query.filter(Submission.filename == files[0])
        test_submission.__repr__()

    def test_reply_string_representation(self):
        test_journalist = Journalist(username="foo",
                                     password="bar")
        db_session.add(test_journalist)
        db_session.commit()
        source, files = common.add_source_and_replies(test_journalist)
        test_reply = Reply.query.filter(Reply.filename == '1-def-reply.gpg')
        test_reply.__repr__()

    def test_journalist_string_representation(self):
        test_journalist = Journalist(username="foo",
                                     password="bar")
        test_journalist.__repr__()

    def test_source_string_representation(self):
        sid = crypto_util.hash_codename(crypto_util.genrandomid())
        codename = crypto_util.display_id()
        crypto_util.genkeypair(sid, codename)
        test_source = Source(sid, codename)
        test_source.__repr__()


if __name__ == "__main__":
    unittest.main(verbosity=2)

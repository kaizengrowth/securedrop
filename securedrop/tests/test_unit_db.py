#!/usr/bin/env python
# -*- coding: utf-8 -*-
import common
import os
import unittest

from flask_testing import TestCase
import mock
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

import journalist
os.environ['SECUREDROP_ENV'] = 'test'
from db import db_session, Journalist, get_one_or_else

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


if __name__ == "__main__":
    unittest.main(verbosity=2)

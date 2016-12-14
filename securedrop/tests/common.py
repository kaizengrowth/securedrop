# -*- coding: utf-8 -*-

from functools import wraps
import mock
import os
import shutil
import subprocess
import time

import gnupg

# Set environment variable so config.py uses a test environment
os.environ['SECUREDROP_ENV'] = 'test'

import config
from db import db_session, init_db, Journalist, Reply, Source, Submission
import crypto_util
import store


class TestJournalist:
    """Test fixtures for working with :class:`db.Journalist`.
    """
    @staticmethod
    def init_journalist(is_admin=False):
        """Initialize a journalist into the database. Return their
        :class:`db.Journalist` object and password string.

        :param bool is_admin: Whether the user is an admin.

        :returns: A 2-tuple. The first entry, the :class:`db.Journalist`
                  initialized. The second, their password string.
        """
        username = crypto_util.genrandomid()
        user_pw = crypto_util.genrandomid()
        user = Journalist(username, user_pw, is_admin)
        db_session.add(user)
        db_session.commit()
        return user, user_pw

    @staticmethod
    def init_admin():
        return TestJournalist.init_journalist(True)

    @staticmethod
    def mock_verify_token(app):
        patcher = mock.patch('db.Journalist.verify_token')
        app.addCleanup(patcher.stop)
        app.mock_journalist_verify_token = patcher.start()
        app.mock_journalist_verify_token.return_value = True


class TestSource:
    """Test fixtures for working with :class:`db.Source`.
    """
    @staticmethod
    def init_source():
        """Initialize a source: create their database record, the
        filesystem directory that stores their submissions & replies,
        and their GPG key encrypted with their codename.

        :returns: A 2-tuple. The first entry, the :class:`db.Source`
        initialized. The second, their codename string.
        """
        # Create source identity and database record
        codename = crypto_util.genrandomid()
        filesystem_id = crypto_util.hash_codename(codename)
        journalist_filename = crypto_util.display_id()
        source = Source(filesystem_id, journalist_filename)
        db_session.add(source)
        db_session.commit()
        # Create the directory to store their submissions and replies
        os.mkdir(store.path(source.filesystem_id))
        # Generate their key, blocking for as long as necessary
        crypto_util.genkeypair(source.filesystem_id, codename)

        return source, codename

    # NOTE: this method is potentially dangerous to rely on for now due
    # to the fact flask_testing.TestCase only uses on request context
    # per method (see
    # https://github.com/freedomofpress/securedrop/issues/1444).
    @staticmethod
    def new_codename(client, session):
        """Helper function to go through the "generate codename" flow.
        """
        with client as c:
            c.get('/generate')
            codename = session['codename']
            c.post('/create')
        return codename


class TestSubmission:
    """Test fixtures for working with :class:`db.Submission`.
    """
    @staticmethod
    def submit(source, num_submissions):
        """Generates and submits *num_submissions*
        :class:`db.Submission`s on behalf of a :class:`db.Source`
        *source*.

        :param db.Source source: The source on who's behalf to make
                                 submissions.

        :param int num_submissions: Number of random-data submissions
                                    to make.

        :returns: A list of the :class:`db.Submission`s submitted.
        """
        assert num_submissions >= 1
        submissions = []
        for _ in range(num_submissions):
            source.interaction_count += 1
            fpath = store.save_message_submission(source.filesystem_id,
                                                  source.interaction_count,
                                                  source.journalist_filename,
                                                  str(os.urandom(1)))
            submission = Submission(source, fpath)
            submissions.append(submission)
            db_session.add(submission)

        db_session.commit()
        return submissions

    @staticmethod
    def mark_downloaded(*submissions):
        for submission in submissions:
            submission.downloaded = True
        db_session.commit()


class TestReply:
    """Test fixtures for working with :class:`db.Reply`.
    """
    @staticmethod
    def reply(journalist, source, num_replies):
        """Generates and submits *num_replies* replies to *source*
        :class:`db.Source`.

        :param db.Journalist journalist: The journalist to write the
                                         reply from.

        :param db.Source source: The source to send the reply to.

        :param int num_replies: Number of random-data replies to make.

        :returns: A list of the :class:`db.Reply`s submitted.
        """
        assert num_replies >= 1
        replies = []
        for _ in range(num_replies):
            source.interaction_count += 1
            fname = "{}-{}-reply.gpg".format(source.interaction_count,
                                             source.journalist_filename)
            crypto_util.encrypt(str(os.urandom(1)),
                                [
                                    crypto_util.getkey(source.filesystem_id),
                                    config.JOURNALIST_KEY
                                ],
                                store.path(source.filesystem_id, fname))
            reply = Reply(journalist, source, fname)
            replies.append(reply)
            db_session.add(reply)

        db_session.commit()
        return replies


class SetUp:
    """Test fixtures for initializing a generic test environment.
    """
    # TODO: the PID file for the redis worker is hard-coded below.
    # Ideally this constant would be provided by a test harness.
    # It has been intentionally omitted from `config.py.example`
    # in order to isolate the test vars from prod vars.
    # When refactoring the test suite, the test_worker_pidfile
    # test_worker_pidfile is also hard-coded in `manage.py`.
    test_worker_pidfile = "/tmp/securedrop_test_worker.pid"

    @staticmethod
    def create_directories():
        # Create directories for the file store and the GPG keyring
        for d in (config.SECUREDROP_DATA_ROOT, config.STORE_DIR,
                  config.GPG_KEY_DIR, config.TEMP_DIR):
            if not os.path.isdir(d):
                os.mkdir(d)

    @staticmethod
    def init_gpg():
        # Initialize the GPG keyring
        gpg = gnupg.GPG(homedir=config.GPG_KEY_DIR)
        # Import the journalist key for testing (faster to import a pre-generated
        # key than to gen a new one every time)
        for keyfile in ("test_journalist_key.pub", "test_journalist_key.sec"):
            gpg.import_keys(open(keyfile).read())
        return gpg

    @classmethod
    def setup(cls):
        """Set up the file system, GPG, and database."""
        SetUp.create_directories()
        SetUp.init_gpg()
        init_db()
        # Do tests that should always run on app startup
        crypto_util.do_runtime_tests()
        # Start the Python-RQ worker if it's not already running
        if not os.path.exists(cls.test_worker_pidfile):
            subprocess.Popen(["rqworker",
                              "-P", config.SECUREDROP_ROOT,
                              "--pid", cls.test_worker_pidfile])


class TearDown:
    """Test fixtures for tearing down a generic test environment.
    """
    @staticmethod
    def teardown():
        shutil.rmtree(config.SECUREDROP_DATA_ROOT)

    # TODO: now that SD has a logout button, we can deprecate use of
    # this function.
    @staticmethod
    def logout(test_client):
        with test_client.session_transaction() as sess:
            sess.clear()


class Async:
    """Test fixtures for use with asynchronous processes.
    """
    redis_success_return_value = 'success'

    @classmethod
    def wait_for_redis_worker(cls, job, timeout=5):
        """Raise an error if the Redis job doesn't complete successfully
        before a timeout.

        :param rq.job.Job job: A Redis job to wait for.

        :param int timeout: Seconds to wait for the job to finish.

        :raises: An :exc:`AssertionError`.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if job.result == cls.redis_success_return_value:
                return
            elif job.result not in (None, cls.redis_success_return_value):
                assert False, 'Redis worker failed!'
            time.sleep(0.1)
        assert False, 'Redis worker timed out!'

    @staticmethod
    def wait_for_assertion(assertion_expression, timeout=5):
        """Calls an assertion_expression repeatedly, until the assertion
        passes or a timeout is reached.

        :param assertion_expression: An assertion expression. Generally
                                     a call to a
                                     :class:`unittest.TestCase` method.

        :param int timeout: Seconds to wait for the function to return.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                return assertion_expression()
            except AssertionError:
                time.sleep(0.1)
                pass
        # one more try, which will raise any errors if they are outstanding
        return assertion_expression()

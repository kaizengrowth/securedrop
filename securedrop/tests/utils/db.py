# -*- coding: utf-8 -*-
"""Testing utilities that involve database (and often related
filesystem) interaction.
"""
import mock
import os

# Set environment variable so config.py uses a test environment
os.environ['SECUREDROP_ENV'] = 'test'
import config
import crypto_util
import db
import store


class TestJournalist(db.Journalist):
    """A wrapper class around :class:`db.Journalist` with extra methods
    and attributes intended to provide special utility for testing.
    """
    def __init__(self, is_admin=False):
        """Initialize a journalist into the database.

        :param bool is_admin: Whether the user is an admin.
        """
        username = crypto_util.genrandomid()
        self.pw = crypto_util.genrandomid()
        super(TestJournalist, self).__init__(username, self.pw, is_admin)
        db.db_session.add(self)
        db.db_session.commit()

    def reply(journalist, source, num_replies):
        """Generates and submits *num_replies* replies to the *source*.

        :param db.Source source: The source to send the replies to.

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
            reply = db.Reply(self, source, fname)
            replies.append(reply)
            db.db_session.add(reply)

        db.db_session.commit()
        return replies


class TestSource(db.Source):
    """A wrapper class around :class:`db.Source` with extra methods
    and attributes intended to provide special utility for testing.
    """
    def __init__(self):
        """Initialize a source: create their database record, the
        filesystem directory that stores their submissions & replies,
        and their GPG key encrypted with their codename.
        """
        # Create source identity and database record
        self.codename = crypto_util.genrandomid()
        filesystem_id = crypto_util.hash_codename(self.codename)
        journalist_filename = crypto_util.display_id()
        super(TestSource, self).__init__(filesystem_id, journalist_filename)
        db.db_session.add(source)
        db.db_session.commit()
        # Create the directory to store their submissions and replies
        os.mkdir(store.path(self.filesystem_id))
        # Generate their key, blocking for as long as necessary
        crypto_util.genkeypair(self.filesystem_id, self.codename)

    def submit(self, num_submissions):
        """Generates and submits *num_submissions* random submissions.

        :param int num_submissions: Number of random-data submissions
                                    to make.

        :returns: A list of the :class:`db.Submission`s submitted.
        """
        assert num_submissions >= 1
        submissions = []
        for _ in range(num_submissions):
            self.interaction_count += 1
            fpath = store.save_message_submission(self.filesystem_id,
                                                  self.interaction_count,
                                                  self.journalist_filename,
                                                  str(os.urandom(1)))
            submission = db.Submission(self, fpath)
            submissions.append(submission)
            db.db_session.add(submission)

        db.db_session.commit()
        return submissions


# NOTE: this method is potentially dangerous to rely on for now due
# to the fact flask_testing.TestCase only uses on request context
# per method (see
# https://github.com/freedomofpress/securedrop/issues/1444).
def new_codename(client, session):
    """Helper function to go through the "generate codename" flow.
    """
    with client as c:
        c.get('/generate')
        codename = session['codename']
        c.post('/create')
    return codename


def mark_downloaded(*submissions):
    for submission in submissions:
        submission.downloaded = True
    db.db_session.commit()


def mock_journalist_token(testcase):
    """Patch a :class:`unittest.TestCase` (or derivative class) so TOTP
    token verification always succeeds.

    :param unittest.TestCase testcase: The test case for which to patch
                                       TOTP verification.
    """
    patcher = mock.patch('db.Journalist.verify_token')
    testcase.addCleanup(patcher.stop)
    testcase.mock_journalist_verify_token = patcher.start()
    testcase.mock_journalist_verify_token.return_value = True

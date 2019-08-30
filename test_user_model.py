"""User model tests."""

# run these tests like:
#
#    python -m unittest test_user_model.py


import os
from unittest import TestCase

from models import db, User, Message, Follows

# BEFORE we import our app, let's set an environmental variable
# to use a different database for tests (we need to do this
# before we import our app, since that will have already
# connected to the database

os.environ['DATABASE_URL'] = "postgresql:///warbler-test"


# Now we can import app

from app import app

# Create our tables (we do this here, so we only create the tables
# once for all tests --- in each test, we'll delete the data
# and create fresh new clean test data

db.create_all()


class UserModelTestCase(TestCase):
    """Test views for messages."""

    def setUp(self):
        """Create test client, add sample data."""

        User.query.delete()
        Message.query.delete()
        Follows.query.delete()
        
        self.u = User.signup(        
            email="test@test.com",
            username="testuser",
            password="HASHED_PASSWORD",
            image_url=None
        )
        self.u.id = 1
        db.session.commit()
        self.client = app.test_client()       
    
    def test_user_repr(self):
        """ Test user repr function"""
        self.assertEqual(str(self.u), "<User #1: testuser, test@test.com>")

# Copyright 2016, Ryan Kelly.

from __future__ import absolute_import

import unittest

from server.meditate import handler


class SubmitTestCase(unittest.TestCase):

    def test_submit(self):

        class FakeContext(object):

            aws_request_id = "XXX"

        response = handler(None, FakeContext())

        self.assertEquals(response["status"], "success")
        self.assertTrue("meditation" in response)

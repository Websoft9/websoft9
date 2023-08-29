import os
import tempfile

import unittest

from appmanage.api.settings.settings import settings


class TestSettings(unittest.TestCase):
    fd = None

    @classmethod
    def setUpClass(cls):
        fd = tempfile.NamedTemporaryFile("w")
        print(fd.name)
        fd.write("a=b\nc=d\n")
        fd.flush()
        settings.init_config_from_file(fd.name)

    def test_get_config(self):
        self.assertEqual(settings.get_setting("a"), "b")
        self.assertTrue(settings.get_setting("e") is None)

    def test_update_config(self):
        self.assertEqual(settings.get_setting("a"), "b")
        settings.update_setting("a", "i")
        self.assertEqual(settings.get_setting("a"), "i")

    def test_list_settings(self):
        data = settings.list_all_settings()
        self.assertTrue(data is not None)

    def test_delete_config(self):
        settings.update_setting("x", "y")
        v = settings.get_setting("x")
        self.assertTrue(v is not None)
        settings.delete_setting("x", v)
        self.assertTrue(settings.get_setting("x") is None)
        
    @classmethod
    def tearDownClass(cls):
        if cls.fd:
            cls.fd.close()


if __name__ == '__main__':
    unittest.main()

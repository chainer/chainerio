import unittest

import chainerio
import io
import os
import pickle
import shutil
from zipfile import ZipFile


class TestZipHandler(unittest.TestCase):

    def setUp(self):
        # The following zip layout is created for all the tests
        # outside.zip
        # | - testdir
        # |   | - nested.zip
        # |   |   | - nested_dir
        # |   |   |   | - nested
        # |   | - testfile
        self.test_string = "this is a test string\n"
        self.nested_test_string = \
            "this is a test string for nested zip\n"
        self.test_string_b = self.test_string.encode("utf-8")
        self.nested_test_string_b = \
            self.nested_test_string.encode("utf-8")

        # the most outside zip
        self.zip_file_name = "outside"
        self.zip_file_path = self.zip_file_name + ".zip"

        # nested zip and nested file
        self.nested_zipped_file_name = "nested"
        self.nested_dir_name = "nested_dir/"
        self.nested_zip_file_name = "nested.zip"

        # directory and file
        self.dir_name = "testdir/"
        self.zipped_file_name = "testfile"

        self.zipped_file_path = os.path.join(
            self.dir_name, self.zipped_file_name)
        self.nested_zip_path = os.path.join(
            self.dir_name, self.nested_zip_file_name)
        self.nested_zipped_file_path = os.path.join(
            self.nested_dir_name, self.nested_zipped_file_name)
        self.fs_handler = chainerio.create_handler("posix")

        os.mkdir(self.dir_name)
        os.mkdir(self.nested_dir_name)
        with open(self.zipped_file_path, "w") as tmpfile:
            tmpfile.write(self.test_string)

        with open(self.nested_zipped_file_path, "w") as tmpfile:
            tmpfile.write(self.nested_test_string)

        with ZipFile(self.nested_zip_path, "w") as tmpzip:
            tmpzip.write(self.nested_zipped_file_path)

        os.remove(self.nested_zipped_file_path)

        shutil.make_archive(self.zip_file_name, "zip", base_dir=self.dir_name)

    def tearDown(self):
        os.remove(self.zip_file_path)
        shutil.rmtree(self.dir_name)
        shutil.rmtree(self.nested_dir_name)

    def test_read_bytes(self):
        with self.fs_handler.open_as_container(
                os.path.abspath(self.zip_file_path)) as handler:
            with handler.open(self.zipped_file_path, "rb") as zipped_file:
                self.assertEqual(self.test_string_b, zipped_file.read())

    def test_read_string(self):
        with self.fs_handler.open_as_container(
                os.path.abspath(self.zip_file_path)) as handler:
            with handler.open(self.zipped_file_path, "r") as zipped_file:
                self.assertEqual(self.test_string, zipped_file.readline())

    def test_open_non_exist(self):

        non_exist_file = "non_exist_file.txt"

        with self.fs_handler.open_as_container(non_exist_file) as handler:
            self.assertRaises(IOError, handler.open, non_exist_file)

    def test_list(self):
        with self.fs_handler.open_as_container(self.zip_file_path) as handler:
            zip_generator = handler.list()
            zip_list = list(zip_generator)
            self.assertIn(self.dir_name.split("/")[0], zip_list)
            self.assertNotIn(self.zipped_file_name, zip_list)
            self.assertNotIn("", zip_list)

            zip_generator = handler.list(self.dir_name)
            zip_list = list(zip_generator)
            self.assertNotIn(self.dir_name.split("/")[0], zip_list)
            self.assertIn(self.zipped_file_name, zip_list)
            self.assertNotIn("", zip_list)

    def test_info(self):
        with self.fs_handler.open_as_container(self.zip_file_path) as handler:
            self.assertIsInstance(handler.info(), str)

    def test_isdir(self):
        with self.fs_handler.open_as_container(self.zip_file_path) as handler:
            self.assertTrue(handler.isdir(self.dir_name))
            self.assertFalse(handler.isdir(self.zipped_file_path))

    def test_mkdir(self):
        with self.fs_handler.open_as_container(self.zip_file_path) as handler:
            self.assertRaises(io.UnsupportedOperation, handler.mkdir, "test")

    def test_makedirs(self):
        with self.fs_handler.open_as_container(self.zip_file_path) as handler:
            self.assertRaises(io.UnsupportedOperation,
                              handler.makedirs, "test/test")

    def test_pickle(self):
        pickle_file_name = "test_pickle.pickle"
        test_data = {'test_elem1': b'balabala',
                     'test_elem2': 'balabala'}
        pickle_zip = "test_pickle.zip"

        with open(pickle_file_name, "wb") as f:
            pickle.dump(test_data, f)

        with ZipFile(pickle_zip, "w") as test_zip:
            test_zip.write(pickle_file_name)

        with self.fs_handler.open_as_container(pickle_zip) as handler:
            with handler.open(pickle_file_name, 'rb') as f:
                loaded_obj = pickle.load(f)
                self.assertEqual(test_data, loaded_obj)

        os.remove(pickle_file_name)
        os.remove(pickle_zip)

    def test_exists(self):
        non_exist_file = "non_exist_file.txt"

        with self.fs_handler.open_as_container(self.zip_file_path) as handler:
            self.assertTrue(handler.exists(self.dir_name))
            self.assertTrue(handler.exists(self.zipped_file_path))
            self.assertFalse(handler.exists(non_exist_file))

    def test_remove(self):
        with self.fs_handler.open_as_container(self.zip_file_path) as handler:
            self.assertRaises(io.UnsupportedOperation,
                              handler.remove, "test/test", False)

    def test_nested_zip(self):
        with self.fs_handler.open_as_container(self.zip_file_path) as handler:
            with handler.open_as_container(
                    self.nested_zip_path) as nested_zip:
                with nested_zip.open(self.nested_zipped_file_path) as f:
                    self.assertEqual(f.read(), self.nested_test_string_b)

                with nested_zip.open(self.nested_zipped_file_path, "r") as f:
                    self.assertEqual(f.read(), self.nested_test_string)

    def test_stat(self):
        # pass for now
        # TODO(tianqi) add test after we well defined the stat
        pass

import os
import shutil
import tempfile
import unittest

import pfio


class TestContext(unittest.TestCase):

    def setUp(self):
        self.test_string_str = "this is a test string\n"
        self.test_string_bytes = self.test_string_str.encode("utf-8")
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmpfile_name = "testfile.txt"
        self.tmpfile_path = os.path.join(self.tmpdir.name, self.tmpfile_name)
        with open(self.tmpfile_path, "w") as tmpfile:
            tmpfile.write(self.test_string_str)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_set_root(self):
        # Set default context globally in this process
        pfio.set_root('posix')

        # Using the context to open local file
        with pfio.open(self.tmpfile_path, "r") as fp:
            self.assertEqual(fp.read(), self.test_string_str)

        pfio.set_root('file://' + self.tmpdir.name)
        with pfio.open(self.tmpfile_name, "r") as fp:
            self.assertEqual(fp.read(), self.test_string_str)

    def test_open_as_container(self):
        # Create a container for testing
        pfio.set_root("posix")
        zip_file_name = "test"
        zip_file_path = zip_file_name + ".zip"

        # in the zip, the leading slash will be removed
        # TODO(tianqi): related to issue #61
        dirname_zip = self.tmpdir.name.lstrip('/') + '/'
        file_name_zip = self.tmpfile_path.lstrip('/')
        first_level_dir = dirname_zip.split('/')[0]

        shutil.make_archive(zip_file_name, "zip", base_dir=self.tmpdir.name)

        with pfio.open_as_container(zip_file_path) as container:
            file_generator = container.list()
            file_list = list(file_generator)
            self.assertIn(first_level_dir, file_list)
            self.assertNotIn(file_name_zip, file_list)
            self.assertNotIn("", file_list)

            file_generator = container.list(dirname_zip)
            file_list = list(file_generator)
            self.assertNotIn(first_level_dir, file_list)
            self.assertIn(os.path.basename(file_name_zip), file_list)
            self.assertNotIn("", file_list)

            self.assertTrue(container.isdir(dirname_zip))
            self.assertFalse(container.isdir(file_name_zip))

            self.assertIsInstance(container.info(), str)
            with container.open(file_name_zip, "r") as f:
                self.assertEqual(
                    f.read(), self.test_string_str)

        pfio.remove(zip_file_path)

    def test_fs_detection_on_container_posix(self):
        # Create a container for testing
        zip_file_name = "test"
        zip_file_path = zip_file_name + ".zip"
        posix_file_path = "file://" + zip_file_path

        # in the zip, the leading slash will be removed
        file_name_zip = self.tmpfile_path.lstrip('/')

        shutil.make_archive(zip_file_name, "zip", base_dir=self.tmpdir.name)

        with pfio.open_as_container(posix_file_path) as container:
            with container.open(file_name_zip, "r") as f:
                self.assertEqual(
                    f.read(), self.test_string_str)

        pfio.remove(zip_file_path)

    @unittest.skipIf(shutil.which('hdfs') is None, "HDFS client not installed")
    def test_fs_detection_on_container_hdfs(self):
        # Create a container for testing
        zip_file_name = "test"
        zip_file_path = zip_file_name + ".zip"

        # in the zip, the leading slash will be removed
        file_name_zip = self.tmpfile_path.lstrip('/')

        # TODO(tianqi): add functionality ot pfio
        from pyarrow import hdfs

        conn = hdfs.connect()
        hdfs_home = conn.info('.')['path']
        conn.close()

        hdfs_file_path = os.path.join(hdfs_home, zip_file_path)

        shutil.make_archive(zip_file_name, "zip", base_dir=self.tmpdir.name)

        with pfio.open(hdfs_file_path, "wb") as hdfs_file:
            with pfio.open(zip_file_path, "rb") as posix_file:
                hdfs_file.write(posix_file.read())

        with pfio.open_as_container(hdfs_file_path) as container:
            with container.open(file_name_zip, "r") as f:
                self.assertEqual(
                    f.read(), self.test_string_str)

        pfio.remove(zip_file_path)
        pfio.remove(hdfs_file_path)

    def test_root_local_override(self):
        pfio.set_root('file://' + self.tmpdir.name)
        with pfio.open(self.tmpfile_name, "r") as fp:
            self.assertEqual(fp.read(), self.test_string_str)

        # override with full URI
        with open(__file__, "r") as my_script:
            with pfio.open('file://' + __file__) as fp:
                self.assertEqual(fp.read(), my_script.read().encode("utf-8"))

    # override with different filesystem
    @unittest.skipIf(shutil.which('hdfs') is None, "HDFS client not installed")
    def test_root_fs_override(self):
        from pyarrow import hdfs

        hdfs_tmpfile = "tmpfile_hdfs"
        hdfs_file_string = "this is a test string for hdfs"

        conn = hdfs.connect()
        with conn.open(hdfs_tmpfile, "wb") as f:
            f.write(hdfs_file_string.encode('utf-8'))

        pfio.set_root("hdfs")
        with pfio.open(hdfs_tmpfile, "r") as fp:
            self.assertEqual(fp.read(), hdfs_file_string)

        # override with full URI
        with open(__file__, "r") as my_script:
            with pfio.open("file://" + __file__, "r") as fp:
                self.assertEqual(fp.read(), my_script.read())

        with pfio.open(hdfs_tmpfile, "r") as fp:
            self.assertEqual(fp.read(), hdfs_file_string)

        conn.delete(hdfs_tmpfile)
        conn.close()

    def test_create_handler(self):
        posix_handler = pfio.create_handler("posix")
        self.assertIsInstance(posix_handler,
                              pfio.filesystems.posix.PosixFileSystem)

        hdfs_handler = pfio.create_handler("hdfs")
        self.assertIsInstance(hdfs_handler,
                              pfio.filesystems.hdfs.HdfsFileSystem)

        another_posix_handler = pfio.create_handler("posix")
        self.assertNotEqual(posix_handler, another_posix_handler)

        with self.assertRaises(ValueError):
            pfio.create_handler("unsupported_scheme")

    def test_list(self):
        nested_dir_name1 = "nested_dir1"
        nested_dir_name2 = "nested_dir2"

        nested_dir_path1 = os.path.join(self.tmpdir.name, nested_dir_name1)
        nested_dir_path2 = os.path.join(nested_dir_path1,
                                        nested_dir_name2)
        nested_dir_path2_relative = os.path.join(nested_dir_name1,
                                                 nested_dir_name2)
        pfio.makedirs(nested_dir_path1)
        pfio.makedirs(nested_dir_path2)

        file_list = list(pfio.list(self.tmpdir.name))
        self.assertIn(nested_dir_name1, file_list)
        self.assertIn(self.tmpfile_name, file_list)
        self.assertNotIn(nested_dir_path2_relative, file_list)

        file_list = list(pfio.list(self.tmpdir.name, recursive=True))
        self.assertIn(nested_dir_name1, file_list)
        self.assertIn(self.tmpfile_name, file_list)
        self.assertIn(nested_dir_path2_relative, file_list)

    def test_isdir(self):
        self.assertTrue(pfio.isdir("file://" + self.tmpdir.name))

    def test_mkdir(self):
        new_tmp_dir = "testmkdir/"
        pfio.mkdir("file://" + new_tmp_dir)
        self.assertTrue(os.path.isdir(new_tmp_dir))
        pfio.remove(new_tmp_dir, True)

    def test_makedirs(self):
        new_tmp_dir = "testmakedirs/"
        nested_dir = new_tmp_dir + "test_nest_dir"

        pfio.makedirs("file://" + nested_dir)
        self.assertTrue(os.path.isdir(nested_dir))
        pfio.remove(new_tmp_dir, True)

    def test_exists(self):
        non_exist_file = "non_exist_file"
        self.assertTrue(pfio.exists(self.tmpdir.name))
        self.assertFalse(pfio.exists(non_exist_file))

    def test_rename(self):
        new_tmp_dir = tempfile.TemporaryDirectory()

        try:
            src = os.path.join("file://", new_tmp_dir.name, 'src')
            dst = os.path.join("file://", new_tmp_dir.name, 'dst')
            with pfio.open(src, 'w') as fp:
                fp.write('foobar')

            assert pfio.exists(src)
            assert not pfio.exists(dst)

            pfio.rename(src, dst)
            with pfio.open(dst, 'r') as fp:
                data = fp.read()
                assert data == 'foobar'

            assert not pfio.exists(src)
            assert pfio.exists(dst)
        finally:
            new_tmp_dir.cleanup()

    def test_remove(self):
        test_file = "test_remove.txt"
        test_dir = "test_dir/"
        nested_dir = os.path.join(test_dir, "nested_file/")
        nested_file = os.path.join(nested_dir, test_file)

        with pfio.open(test_file, 'w') as fp:
            fp.write('foobar')

        # test remove on one file
        self.assertTrue(pfio.exists(test_file))
        pfio.remove(test_file)
        self.assertFalse(pfio.exists(test_file))

        # test remove on directory
        pfio.makedirs(nested_dir)
        with pfio.open(nested_file, 'w') as fp:
            fp.write('foobar')

        self.assertTrue(pfio.exists(test_dir))
        self.assertTrue(pfio.exists(nested_dir))
        self.assertTrue(pfio.exists(nested_file))

        pfio.remove(test_dir, True)

        self.assertFalse(pfio.exists(test_dir))
        self.assertFalse(pfio.exists(nested_dir))
        self.assertFalse(pfio.exists(nested_file))

    def test_stat(self):
        # pass for now
        # TODO(tianqi) add test after we well defined the stat
        pass

import abc
import contextlib
import copy
import os
import stat
from abc import abstractmethod
from io import IOBase
from types import TracebackType
from typing import Any, Callable, Iterator, Optional, Type
from urllib.parse import urlparse


class FileStat(abc.ABC):
    """Detailed file or directory information abstraction

    :meth:`pfio.IO.stat` of filesystem/container handlers return an object of
    subclass of ``FileStat``.
    In addition to the common attributes that the ``FileStat`` abstract
    provides, each ``FileStat`` subclass implements some additional
    attributes depending on what information the corresponding filesystem or
    container can handle.
    The common attributes have the same behavior despite filesystem or
    container type difference.

    Attributes:
        filename (str):
            Filename in the filesystem or container.
        last_modifled (float):
            UNIX timestamp of mtime. Note that some
            filesystems or containers do not have sub-second precision.
        mode (int):
            Permission with file type flag (regular file or directory).
            You can make a human-readable interpretation by
            `stat.filemode <https://docs.python.org/3/library/stat.html#stat.filemode>`_.
        size (int):
            Size in bytes. Note that directories may have different
            sizes depending on the filesystem or container type.
    """     # NOQA
    filename = None
    last_modified = None
    mode = None
    size = None

    def isdir(self):
        """Returns whether the target is a directory, based on the permission flag

        Returns:
            `True` if directory, `False` otherwise.
        """
        return bool(self.mode & 0o40000)

    def __str__(self):
        return '<{} filename="{}" mode="{}">'.format(
            type(self).__name__, self.filename, stat.filemode(self.mode))

    def __repr__(self):
        return str(self.__str__())


class ForkedError(RuntimeError):
    pass


class FS(abc.ABC):
    '''FS access abstraction

    '''

    cwd = None
    pid = os.getpid()

    def __init__(self):
        self.pid = os.getpid()

    @abstractmethod
    def open(self, file_path: str, mode: str = 'rb',
             buffering: int = -1, encoding: Optional[str] = None,
             errors: Optional[str] = None,
             newline: Optional[str] = None,
             closefd: bool = True,
             opener: Optional[Callable[
                 [str, int], Any]] = None) -> Type["IOBase"]:
        raise NotImplementedError()

    def open_zip(self, file_path: str, mode='r') -> Type["Zip"]:  # NOQA
        from .zip import Zip
        return Zip(self, file_path, mode)

    def subfs(self, rel_path: str) -> Type["FS"]:
        '''Virtually changes the working directory

        By default it performs shallow copy. If any resource that as
        different lifecycles than the copy source (e.g. HDFS
        connection and zipfile.ZipFile object), they also will be
        copied by overriding this method.

        '''
        sub = copy.copy(self)
        if self.cwd is not None:
            sub.cwd = os.path.join(self.cwd, rel_path)
        return sub

    def _checkfork(self):
        if self.is_forked:
            raise ForkedError()

    @property
    def is_forked(self):
        return self.pid != os.getpid()

    def close(self) -> None:
        pass

    @abstractmethod
    def list(self, path_or_prefix: Optional[str] = None,
             recursive=False) -> Iterator[str]:
        """Lists all the files and directories under
           the given ``path_or_prefix``

        Args:
            path_or_prefix (str): The path to list against.
                When we get the default value, ``list`` shows the content under
                the root path, as the default value.
                Refer to :func:`set_root` for details about the root path of
                each filesystem. However, if a ``path_or_prefix`` is given,
                then it shows only the files and directories
                under the ``path_or_prefix``.

            recursive (bool): When this is ``True``, list files and directories
                recursively.

        Returns:
            An Iterator that iterates though the files and directories.

        """
        raise NotImplementedError()

    @abstractmethod
    def stat(self, path: str) -> FileStat:
        """Show details of a file

        It returns an object of subclass of :class:`pfio.io.FileStat`
        in accordance with filesystem or container type.

        Args:
            path (str): The path to file

        Returns:
            :class:`pfio.io.FileStat` object.
        """
        raise NotImplementedError()

    def __enter__(self) -> 'FS':
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> bool:
        self.close()

    @abstractmethod
    def isdir(self, file_path: str) -> bool:
        """Returns ``True`` if the path is an existing directory

        Args:
            path (str): the path to the target directory

        Returns:
            ``True`` when the path points to a directory,
            ``False`` when it is not

        """
        raise NotImplementedError()

    @abstractmethod
    def mkdir(self, file_path: str, mode: int = 0o777,
              *args, dir_fd: Optional[int] = None) -> None:
        """Makes a directory with mode

        Args:
            path (str): the path to the directory to make

            mode (int): the mode of the new directory

        """
        raise NotImplementedError()

    @abstractmethod
    def makedirs(self, file_path: str, mode: int = 0o777,
                 exist_ok: bool = False) -> None:
        """Makes directories recursively with mode

        Also creates all the missing parents of the given path.

        Args:
            path (str): the path to the directory to make.

            mode (int): the mode of the directory

            exist_ok (bool): In default case, a ``FileExitsError`` will be
                raised when the target directory exists.

        """
        raise NotImplementedError()

    @abstractmethod
    def exists(self, file_path: str) -> bool:
        """Returns ``True`` when the given ``path`` exists

        When the ``file_path`` points to a symlink, the return value
        depends on the actual file instead of the link itself.

        Args:
            path (str): the ``path`` to the target file. The ``path`` can be a
            POSIX path or a URI.

        Returns:
            ``True`` when the file or directory exists,
            ``False`` when it is not.

        """
        raise NotImplementedError()

    @abstractmethod
    def rename(self, src: str, dst: str) -> None:
        """Renames the file from ``src`` to ``dst``

        Args:
            src (str): the current name of the file or directory.

            dst (str): the name to rename to.

        """
        raise NotImplementedError()

    @abstractmethod
    def remove(self, file_path: str, recursive: bool = False) -> None:
        """Removes a file or directory

           A combination of :func:`os.remove` and :func:`os.rmtree`.

           Args:
               path (str): the target path to remove. The ``path`` can be a
               regular file or a directory.

               recursive (bool): When the given path is a directory,
                   all the files and directories under it will be removed.
                   When the path is a file, this option is ignored.

        """
        raise NotImplementedError()


@contextlib.contextmanager
def open_url(url: str, mode: str = 'r') -> 'IOBase':
    '''Opens a file regardless of the backend FS type

    ``url`` must be compliant with URL standard in
    https://url.spec.whatwg.org/ .  As this function implements
    context manager, the FileObject can be written as::

       with open_url("s3://bucket.example.com/path/your-file.txt", 'r') as f:
           f.read()

    .. note:: Some FS resouces won't be closed when using this
        functionality.

    Returns:
        a FileObject that must be closed.

    '''
    dirname, filename = os.path.split(url)
    with from_url(dirname) as fs:
        with fs.open(filename, mode) as fp:
            yield fp


def from_url(url: str) -> 'FS':
    '''Factory pattern implementation, creates FS from URI

    .. note:: Some FS resouces won't be closed when using this
        functionality.

    '''
    parsed = urlparse(url)

    if parsed.scheme:
        scheme = parsed.scheme
    else:
        scheme = 'file'  # Default is local

    if parsed.path.endswith('.zip'):
        dirname, filename = os.path.split(parsed.path)
    else:
        dirname = parsed.path

    if scheme == 'file':
        from .local import Local
        fs = Local(dirname)
    elif scheme == 'hdfs':
        from .hdfs import Hdfs
        fs = Hdfs(dirname)
    elif scheme == 's3':
        from .s3 import S3

        # TODO: how can we handle access keys?
        fs = S3(bucket=parsed.netloc,
                endpoint=os.getenv('S3_ENDPOINT'))
        fs = fs.subfs(dirname)
    else:
        raise RuntimeError("Scheme {} is not supported", scheme)

    if parsed.path.endswith('.zip'):
        return fs.open_zip(filename)

    return fs


def recreate_on_fork(func) -> "FS":
    return _RecreateOnFork(func)


class _RecreateOnFork(FS):
    def __init__(self, func):
        self.mixin = func()
        self.func = func

    def open(self, *args, **kwargs):
        if self.mixin.is_forked:
            self.mixin = self.func()
        return self.mixin.open(*args, **kwargs)

    def subfs(self):
        if self.mixin.is_forked:
            self.mixin = self.func()
        self.mixin.subfs()

    def close(self):
        if self.mixin.is_forked:
            self.mixin = self.func()
        self.mixin.close()

    def list(self, *args, **kwargs):
        if self.mixin.is_forked:
            self.mixin = self.func()
        return self.mixin.list(*args, **kwargs)

    def stat(self, *args, **kwargs):
        if self.mixin.is_forked:
            self.mixin = self.func()
        return self.mixin.stat(*args, **kwargs)

    def isdir(self, *args, **kwargs):
        if self.mixin.is_forked:
            self.mixin = self.func()
        return self.mixin.mkdir(*args, **kwargs)

    def mkdir(self, *args, **kwargs):
        if self.mixin.is_forked:
            self.mixin = self.func()
        return self.mixin.mkdir(*args, **kwargs)

    def makedirs(self, *args, **kwargs):
        if self.mixin.is_forked:
            self.mixin = self.func()
        return self.mixin.makedirs(*args, **kwargs)

    def exists(self, *args, **kwargs):
        if self.mixin.is_forked:
            self.mixin = self.func()
        return self.mixin.exists(*args, **kwargs)

    def rename(self, *args, **kwargs):
        if self.mixin.is_forked:
            self.mixin = self.func()
        return self.mixin.rename(*args, **kwargs)

    def remove(self, *args, **kwargs):
        if self.mixin.is_forked:
            self.mixin = self.func()
        return self.mixin.remove(*args, **kwargs)
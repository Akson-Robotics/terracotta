"""drivers/base_classes.py

Base class for drivers.
"""

import contextlib
import functools
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import (Any, Callable, Dict, List, Mapping, Optional, Sequence,
                    Tuple, TypeVar, Union)

KeysType = Mapping[str, str]
MultiValueKeysType = Mapping[str, Union[str, List[str]]]
Number = TypeVar('Number', int, float)
T = TypeVar('T')


def requires_connection(
    fun: Callable[..., T] = None, *,
    verify: bool = True
) -> Union[Callable[..., T], functools.partial]:
    if fun is None:
        return functools.partial(requires_connection, verify=verify)

    @functools.wraps(fun)
    def inner(self: MetaStore, *args: Any, **kwargs: Any) -> T:
        assert fun is not None
        with self.connect(verify=verify):
            return fun(self, *args, **kwargs)

    return inner


class MetaStore(ABC):
    """Abstract base class for all Terracotta metadata backends.

    Defines a common interface for all metadata backends.
    """
    _RESERVED_KEYS = ('limit', 'page')

    @property
    @abstractmethod
    def db_version(self) -> str:
        """Terracotta version used to create the database."""
        pass

    @property
    @abstractmethod
    def key_names(self) -> Tuple[str, ...]:
        """Names of all keys defined by the database."""
        pass

    @abstractmethod
    def __init__(self, url_or_path: str) -> None:
        self.path = url_or_path

    @classmethod
    def _normalize_path(cls, path: str) -> str:
        """Convert given path to normalized version (that can be used for caching)"""
        return path

    @abstractmethod
    def create(self, keys: Sequence[str], *,
               key_descriptions: Mapping[str, str] = None) -> None:
        # Create a new, empty database (driver dependent)
        pass

    @abstractmethod
    def connect(self, verify: bool = True) -> contextlib.AbstractContextManager:
        """Context manager to connect to a given database and clean up on exit.

        This allows you to pool interactions with the database to prevent possibly
        expensive reconnects, or to roll back several interactions if one of them fails.

        Arguments:

            verify: Whether to verify the database (primarily its version) when connecting.
                Should be `true` unless absolutely necessary, such as when instantiating the
                database during creation of it.

        Note:

            Make sure to call :meth:`create` on a fresh database before using this method.

        Example:

            >>> import terracotta as tc
            >>> driver = tc.get_driver('tc.sqlite')
            >>> with driver.connect():
            ...     for keys, dataset in datasets.items():
            ...         # connection will be kept open between insert operations
            ...         driver.insert(keys, dataset)

        """
        pass

    @abstractmethod
    def get_keys(self) -> OrderedDict:
        """Get all known keys and their fulltext descriptions.

        Returns:

            An :class:`~collections.OrderedDict` in the form
            ``{key_name: key_description}``

        """
        pass

    @abstractmethod
    def get_datasets(self, where: MultiValueKeysType = None,
                     page: int = 0, limit: int = None) -> Dict[Tuple[str, ...], Any]:
        # Get all known dataset key combinations matching the given constraints,
        # and a path to retrieve the data (driver dependent)
        pass

    @abstractmethod
    def get_metadata(self, keys: KeysType) -> Optional[Dict[str, Any]]:
        """Return all stored metadata for given keys.

        Arguments:

            keys: Keys of the requested dataset. Can either be given as a sequence of key values,
                or as a mapping ``{key_name: key_value}``.

        Returns:

            A :class:`dict` with the values

            - ``range``: global minimum and maximum value in dataset
            - ``bounds``: physical bounds covered by dataset in latitude-longitude projection
            - ``convex_hull``: GeoJSON shape specifying total data coverage in latitude-longitude
              projection
            - ``percentiles``: array of pre-computed percentiles from 1% through 99%
            - ``mean``: global mean
            - ``stdev``: global standard deviation
            - ``metadata``: any additional client-relevant metadata

        """
        pass

    @abstractmethod
    def insert(self, keys: KeysType,
               path: Any, **kwargs: Any) -> None:
        """Register a new dataset. Used to populate metadata database.

        Arguments:

            keys: Keys of the dataset. Can either be given as a sequence of key values, or
                as a mapping ``{key_name: key_value}``.
            path: Path to access dataset (driver dependent).

        """
        pass

    @abstractmethod
    def delete(self, keys: KeysType) -> None:
        """Remove a dataset from the metadata database.

        Arguments:

            keys:  Keys of the dataset. Can either be given as a sequence of key values, or
                as a mapping ``{key_name: key_value}``.

        """
        pass

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(\'{self.path}\')'


class RasterStore(ABC):
    """Abstract base class for all Terracotta raster backends.

    Defines a common interface for all raster backends."""

    @abstractmethod
    # TODO: add accurate signature if mypy ever supports conditional return types
    def get_raster_tile(self, path: str, *,
                        tile_bounds: Sequence[float] = None,
                        tile_size: Sequence[int] = (256, 256),
                        preserve_values: bool = False,
                        asynchronous: bool = False) -> Any:
        """Load a raster tile with given path and bounds.

        Arguments:

            path: Path of the requested dataset.
            tile_bounds: Physical bounds of the tile to read, in Web Mercator projection (EPSG3857).
                Reads the whole dataset if not given.
            tile_size: Shape of the output array to return. Must be two-dimensional.
                Defaults to :attr:`~terracotta.config.TerracottaSettings.DEFAULT_TILE_SIZE`.
            preserve_values: Whether to preserve exact numerical values (e.g. when reading
                categorical data). Sets all interpolation to nearest neighbor.
            asynchronous: If given, the tile will be read asynchronously in a separate thread.
                This function will return immediately with a :class:`~concurrent.futures.Future`
                that can be used to retrieve the result.

        Returns:

            Requested tile as :class:`~numpy.ma.MaskedArray` of shape ``tile_size`` if
            ``asynchronous=False``, otherwise a :class:`~concurrent.futures.Future` containing
            the result.

        """
        pass

    @abstractmethod
    def compute_metadata(self, path: str, *,
                         extra_metadata: Any = None,
                         use_chunks: bool = None,
                         max_shape: Sequence[int] = None) -> Dict[str, Any]:
        # Compute metadata for a given input file (driver dependent)
        pass

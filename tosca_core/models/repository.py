"""
Module definining Tosca Repository entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2015-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Type hints
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# SQL Alchemy support
from sqlalchemy import or_, and_

# SQL Alchemy exception support
import sqlalchemy.orm.exc

# Support for TOSCA keywords that are shared between all entities
import tosca_core.models.entity

# URL support
import urllib.request, urllib.parse, urllib.error, urllib.parse

# Unique repository names
import uuid

# File system support
import os.path
from pathlib import Path

# Exceptions
import tosca_core.models.exceptions as te


# Exceptions
class RepositoryAlreadyExists(Exception):
    pass
class InvalidMetaData(Exception):
    pass


class ToscaRepository(tosca_core.models.entity.ToscaEntityMixin, db.Model):
    """A ToscaRepository object defines a named repository used in TOSCA
    service templates
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    repo_class =    db.Column(db.String, nullable=False, index=True)
    __mapper_args__ = {
        'polymorphic_identity': 'repo',
        'polymorphic_on': repo_class
    }

    ################################################################################
    # Keys
    ################################################################################
    
    # Primary key
    id =          db.Column(db.Integer, primary_key=True)

    # Foreign keys
    _profile_id = db.Column(db.Integer,
                            db.ForeignKey('tosca_profile.id'),
                            nullable=True)

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.

    _url =        db.Column(db.String, nullable=True)
    _credential = db.Column(db.PickleType, nullable=True)

    @property
    def url(self) -> str:
        if not self._url:
            raise AttributeError("'{0}' does not have 'url'".format(self.name))
        return self._url

    @property
    def credential(self) -> Any:
        if not self._credential:
            raise AttributeError("'{0}' does not have 'credential'".format(self.name))
        return self._credential

    ################################################################################
    # Model Navigation
    ################################################################################

    # Profile within which this repository is defined. 
    profile =     db.relationship('ToscaProfile',
                                  uselist=False,
                                  foreign_keys='ToscaRepository._profile_id')

    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 url: Optional[str] = None,
                 credential: Optional[Any] = None,
                 **kwargs: Any
    ) -> None:
        """Instantiate a new ToscaRepository instance"""

        # First, call superclass constructor
        super(ToscaRepository, self).__init__(**kwargs)

        # ToscaRepository-specific initialization
        if url: self._url = url
        if credential: self._credential = credential


    def get_absolute_path(self, file_name: str, relative_to: str) -> str:
        """Get absolute path for a file name that is expressed relative to
        another file. If the relative file is null, just return the
        file as an absolute path
        """
        # Extract the directory name from the 'relative_to' file
        relative_dir = os.path.dirname(relative_to)

        # Return absolute path. Prepend '/' in case relative_dir
        # doesn't start with '/'
        return os.path.normpath(os.path.join('/', relative_dir, file_name))


    def get_file_url(self, file_name: str) -> str:
        """Return the absolute URL name for a file in a repository"""

        # Strip leading / from file_name
        if os.path.isabs(file_name): file_name = os.path.relpath(file_name, '/')

        # urljoin treats the last segment of an unterminated base as a
        # filename to be replaced, so 'https://.../raw/master' + 'a/b'
        # yields '.../raw/a/b' (losing 'master'). Repository URLs are
        # always directory-style, so guarantee the trailing slash.
        # CsarRepository already does this when constructing its URL;
        # this covers user-declared 'repositories:' entries that leave
        # the slash off.
        base = self.url if self.url.endswith('/') else self.url + '/'
        return urllib.parse.urljoin(base, urllib.request.pathname2url(file_name))

    
    def url_refusal(self, file_url: str) -> Optional[str]:
        """Why a file URL may not be read, or None when it may.

        A URL with any scheme but 'file' is not checked here. A 'file:' URL
        may be read only when it names a local file whose resolved path,
        with symbolic links and '..' followed, lies inside this
        repository's own resolved directory, so a template cannot read
        arbitrary files on the host (B310). Where a repository may point is
        decided when it is onboarded (check_local_repository).

        Args:
          file_url: the URL of the file to read

        Returns:
          a sentence saying what was refused and what to do, or None
        """
        if urllib.parse.urlparse(file_url).scheme.lower() != 'file':
            return None
        file_path = local_path(file_url)
        root = local_path(self.url or '')
        if file_path is None or root is None:
            return (f"access denied: '{file_url}' is not a local file in repository "
                    f"'{self.url}'; a 'file:' URL may name no host but 'localhost'")

        # Compare resolved paths, not strings: a string prefix would also
        # admit a sibling such as '<root>-other', and an unresolved URL
        # could carry '..'.
        resolved = file_path.resolve()
        if resolved.is_relative_to(root.resolve()):
            return None
        return (f"access denied: '{resolved}' is outside repository '{root.resolve()}'; "
                f"keep the file inside the repository, and name it by a path that does "
                f"not lead out of it")

    def is_valid_url(self, file_url: str) -> bool:
        """Whether a file URL may be read; see url_refusal() for why not

        Args:
          file_url: a string containing the file url

        Returns:
          True:  if URL is valid
          False: otherwise
        """
        refusal = self.url_refusal(file_url)
        if refusal:
            logger.error(refusal)
        return refusal is None

    def exists(self, file_name: str) -> bool:
        """Check if a file exists in the repository

        Args: 
          file_name(str): name of file to retrieve

        Returns:
          True: if the file exists
          False: if the file doesn't exists

        Raises:
          None
        """

        # Get full URL name for the file to retrieve
        file_url = self.get_file_url(file_name)

        try:
            # 1. **Security Check (Fixes B310):** Only allow files the
            # repository may read.
            refusal = self.url_refusal(file_url)
            if refusal:
                raise ValueError(refusal)
    
            # 2. **Resource Management (Best Practice):** Use a 'with' statement.
            # The 'with' statement automatically calls f.close() even if an error occurs.
            # Bandit flags this function. It is suppressed because the URL scheme 
            # is explicitly validated above.
            with urllib.request.urlopen(file_url) as f: # nosec B310
                # The connection is open and the file-like object 'f' is ready to use.
                # You can now read data, check headers, etc.
                # Example: content = f.read() 
                # Optionally check the status code explicitly, but successful open 
                # generally implies 2xx unless an error was already raised.
                """
                # Commenting this out since this does not work for file URLs.
                if 200 <= f.status < 300:
                    return True
                else:
                    # Should be rare, but handles unexpected status in 3xx/4xx/5xx range 
                    # that did not raise an exception.
                    return False
                """
                logger.debug(f"URL {file_url} successfully opened and connection closed.")
                return True
            
        # 4. Handle specific network and URL errors
        except urllib.error.HTTPError as e:
            # Handle HTTP errors like 404, 500, etc.
            logger.error(f"HTTP Error: {e.code} at {file_url}")
            return False
        except urllib.error.URLError as e:
            # Handle URL errors like connection failures, bad hostnames, etc.
            logger.error(f"URL Error: {e.reason} for {file_url}")
            return False
        except ValueError as e:
            # Handle the refusal raised in step 1.
            logger.error(f"Validation Error: {e}")
            return False
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"An unexpected error occurred: {e}")
            return False
        # Old less secure method: Check existence by trying to open
        #try:
        #    f = urllib.request.urlopen(file_url)
        #    f.close()
        #    return True
        #except IOError:
        #    return False

    def retrieve(self, file_name: str) -> str:
        """Retrieve a file from a repository

        Args: 
          file_name(str): name of file to retrieve

        Returns:
          File name of a local copy of the file to be retrieved

        Raises:
          IOError: when resource doesn't exist or some other error
            occurred
        """

        logger.debug("Retrieving [%s] from [%s]", file_name, self.url)
        
        # Get full URL name for the file to retrieve
        file_url = self.get_file_url(file_name)

        # **Security Check (Fixes B310):** Only allow files the repository
        # may read.
        refusal = self.url_refusal(file_url)
        if refusal:
            raise ValueError(refusal)
    
        # Retrieve
        # Bandit flags this function. It is suppressed because the URL scheme 
        # is explicitly validated above.
        (retrieved_file_name, headers)  = urllib.request.urlretrieve(file_url) # nosec B310
        # For a file:// URL urlretrieve copies nothing and returns the URL's
        # path as it stands, still percent-encoded ('my%20repo'); decode it,
        # or a file under a directory with a space in its name is not found.
        if urllib.parse.urlparse(file_url).scheme.lower() == 'file':
            retrieved_file_name = urllib.request.url2pathname(retrieved_file_name)
        logger.debug("Retrieved [%s]", retrieved_file_name)

        return retrieved_file_name


#############################
# URL HELPERS
#############################

def is_uri(string: str) -> bool:
    """Determine if a string contains a valid URI"""

    # Try to parse string as URI
    try:
        parsed_url = urllib.parse.urlparse(string)
        # Make sure we have a valid scheme
        if not bool(parsed_url.scheme) \
           or not parsed_url.scheme in ['urn', 'http', 'https', 'ftp', 'file']:
            return False
    except Exception:
        # Unable to parse
        return False
    # Valid URI
    return True


def normalize_file_uri(url: str) -> str:
    """If 'url' is a 'file:' URI with no host or the host 'localhost',
    which RFC 8089 makes equivalent, return just its path. The result is
    then resolved within the CSAR repository that contains the importing
    TOSCA file, which makes 'file:' URIs and bare relative paths behave
    identically and effectively sandboxes imports inside the CSAR.

    Other URLs, including 'file:' URLs naming any other host, are
    returned unchanged; create_repository_for_url refuses the latter.
    """
    try:
        parsed_url = urllib.parse.urlparse(url)
    except Exception:
        return url
    if parsed_url.scheme == 'file' and parsed_url.netloc in ('', 'localhost'):
        return parsed_url.path
    return url


def local_path(url: str) -> Optional[Path]:
    """The local path a 'file:' URL names, or None when the URL is not a
    'file:' URL or names a host other than 'localhost'.

    A host is refused even when it is one of this machine's own names or
    addresses: Python opens such a URL as a local file, so accepting it
    would decide locality by name resolution.
    """
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme.lower() != 'file' or parsed_url.netloc not in ('', 'localhost'):
        return None
    return Path(urllib.request.url2pathname(parsed_url.path))


def check_local_repository(url: str, csar_url: str) -> Optional[str]:
    """Decide whether a repository URL may be onboarded.

    A repository with any scheme but 'file' is not checked here. A 'file:'
    repository must name a local directory that, resolved, lies inside the
    declaring CSAR's own directory or inside one of the operator's local
    repository roots (constants.LOCAL_REPOSITORY_ROOTS).

    Args:
      url: the repository's URL, already resolved against the CSAR
      csar_url: the URL of the declaring CSAR's repository

    Returns:
      None if the repository may be onboarded, else the reason it may not
    """
    if urllib.parse.urlparse(url).scheme.lower() != 'file':
        return None
    path = local_path(url)
    if path is None:
        return "a 'file:' URL may name no host but 'localhost'"
    resolved = path.resolve()
    from tosca_core.constants import constants
    csar_root = local_path(csar_url)
    allowed = ([csar_root] if csar_root is not None else []) \
        + [Path(root) for root in constants.LOCAL_REPOSITORY_ROOTS]
    if any(resolved.is_relative_to(root.resolve()) for root in allowed):
        return None
    return ("'{0}' is outside the CSAR and the local repository roots "
            "(LOCAL_REPOSITORY_ROOTS)".format(resolved))


def create_repository_for_url(url: str) -> tuple[ToscaRepository, str]:
    """Decompose an absolute URL into a synthetic repository (scheme +
    netloc) and the path within that repository. Used when a TOSCA
    file (import) or an artifact file is specified as an absolute URL
    without an explicit repository.

    Args:
      url(str): absolute URL to decompose

    Returns:
      tuple of (ToscaRepository, path-within-repo)

    Raises:
      RepositoryNotFound: when the URL is not valid.
    """

    # Parse the url
    parsed_url = urllib.parse.urlparse(url)

    # A 'file:' URL is never a repository of its own: one with no host or
    # 'localhost' names a file in the CSAR (normalize_file_uri), and one
    # naming another host names nothing Ubicity reads.
    if parsed_url.scheme == 'file':
        raise te.RepositoryNotFound(
            "'{0}': a 'file:' URL may name no host but 'localhost'".format(url))

    # Make sure we have the basic elements for a URL
    if not bool(parsed_url.scheme) \
       or not parsed_url.scheme in ['http', 'https', 'ftp'] \
       or not bool(parsed_url.netloc) \
       or not bool(parsed_url.path):
        raise te.RepositoryNotFound("'{0}' is not a valid URL".format(url))

    # Create repository URL from scheme + netloc
    logger.info("Creating repository URL from '%s' and '%s'",
                parsed_url.scheme, parsed_url.netloc)
    repository_url = urllib.parse.urlunparse(
        (parsed_url.scheme, parsed_url.netloc, '', '', '', ''))
    logger.info("Repo URL: %s", repository_url)
    logger.info("Path: %s", parsed_url.path)

    # Create repository
    repository = ToscaRepository(
        name=uuid.uuid4().hex,
        url=repository_url
        )
    return repository, parsed_url.path


#############################
# REPOSITORY LOOKUP FUNCTIONS
#############################

def get_repository(repository_name: str, profile_id: int) -> ToscaRepository:
    """Return repository entity by name. 

    Args:
      repository_name(str): name of the repository entity
      profile_id(integer): ID of the profile within which to find
        the repository

    Raises:
      sqlalchemy.orm.exc.NoResultFound: when no repository found with the
        specified name for the specified class
      sqlalchemy.orm.exc.MultipleResultsFound: when multiple repository
        found with the specified name for the specified class (repositories
        are supposed to be unique)

    """
    repository_entity = ToscaRepository.query.filter(
        and_(
            ToscaRepository.name == repository_name,
            ToscaRepository._profile_id == profile_id
        )
    ).one()

    return repository_entity



def get_repository_by_id(repo_id: int) -> Optional[ToscaRepository]:
    """Return repository entity by id

    Args:
      id_id(integer): ID of the repo

    Raises:
      sqlalchemy.orm.exc.NoResultFound: when no repository found with the
        specified name for the specified class
      sqlalchemy.orm.exc.MultipleResultsFound: when multiple repository
        found with the specified name for the specified class (repositories
        are supposed to be unique)

    """
    repository_entity = ToscaRepository.query.get(repo_id)
    return repository_entity


###############################
# REPOSITORY ADDITION FUNCTIONS
###############################

def add_repository(repository_entity: ToscaRepository) -> None:
    """Add repository entity. Make sure we don't already have repositories with this
    repository's name or short name

    Args:
      repository_entity(ToscaRepository): repository entity to be
        added

    Raises:

      RepositoryAlreadyExists: if this repository is already in the
        database

      sqlalchemy.orm.exc.MultipleResultsFound: when multiple
        repositories with this name are found in the database. This is
        a catastrophic error

    """

    # Check if repository already exist with the same name
    try:
        existing_repository = get_repository(repository_entity.name, repository_entity._profile_id)
        # Repository already exists. Raise an error
        logger.debug("%s already in database", 
                     repository_entity.name)
        raise RepositoryAlreadyExists("Repository {0} already in database".format(
            repository_entity.name))

    except sqlalchemy.orm.exc.NoResultFound: 
        # Good. Repository does not already exist.
        pass
        
    # Not a duplicate. Add
    db.session.add(repository_entity)




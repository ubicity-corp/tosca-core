"""Module defining a Tosca Repository that stores the contents of a
Cloud Service Archive (CSAR) file
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2017-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Typing support
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Unique ids
import uuid

# File system and file manipulation support
import os.path
import shutil
from pathlib import Path

# URL support
import urllib.request, urllib.parse, urllib.error, urllib.parse

# Database support
from tosca_core import db

# SQLAlchemy support
from sqlalchemy.orm import backref
from sqlalchemy.ext.orderinglist import ordering_list

# Classes on which this class depends
from tosca_core.models.repository import ToscaRepository

# CSAR file support
import zipfile

# String parsing support
from string import whitespace

# Configuration support
from tosca_core.constants import constants

# CSAR Support
TOSCA_META_DIR_NAME =  'TOSCA-Metadata'
TOSCA_META_FILE_NAME = 'TOSCA.meta'
TOSCA_CSAR_VERSIONS = [ '1.1', '2.0' ]

# Exceptions
class ArchiveDoesNotExist(Exception):
    pass
class ArchiveNotAFile(Exception):
    pass
class ArchiveEmpty(Exception):
    pass
class InvalidMetaData(Exception):
    pass


class CsarRepository(ToscaRepository):
    """A CSAR Repository is a special type of repository that is created
    in the local file system by extracting the contents of a TOSCA
    Cloud Service Archive (CSAR) file.
    """

    ################################################################################
    # Polymorphic mapping
    ################################################################################

    __mapper_args__ = {
        'polymorphic_identity':'csar',
    }

    ################################################################################
    # Fields
    ################################################################################

    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.

    file_name = db.Column(db.String)

    ################################################################################
    # Relationships 
    ################################################################################

    # Profiles in this CSAR
    profiles =  db.relationship('ToscaProfile',
                                collection_class=ordering_list('position'),
                                order_by='ToscaProfile.position',      
                                foreign_keys='ToscaProfile._csar_id',
                                backref=backref('csar', uselist=False))

    # This relationship's collection should not be modified directly. Its only purpose is to
    # provide a cascade path for deleting child objects.
    templates = db.relationship('ToscaTemplate',
                                cascade='all')
    
    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self, csar_file_name: str, csar_path_name: str, validate_only: bool, **kwargs: Any) -> None:
        """Instantiate a new CsarRepository instance

        Args: 
          csar_path_name(str): Path name for the archive from which
            to create the repository. Can point to an archive
            directory, or to a CSAR or YAML file.
          validate_only(boolean): True when archive is only
            validated. False when archive is intended to be
            loaded. When validating, it's OK to specify a directory
            path rather than an archive file.

        Raises:
          ArchiveDoesNotExist: when the path points to a location that
            does not exist
          ArchiveNotAFile: when the path points to a location that
            does not exist
        """

        # First, make sure the path exists
        if not os.path.exists(csar_path_name):
            raise ArchiveDoesNotExist("'{0}' does not exist".format(csar_path_name))

        # Create a unique repository name
        repo_name = uuid.uuid4().hex[:16]

        # Does path point to a directory?
        if os.path.isdir(csar_path_name):
            if not validate_only:
                raise ArchiveNotAFile("'{0}' is not a file".format(csar_path_name))
            # We're only validating, so it's OK to use the specified
            # directory as the archive. Normalize the directory name
            local_repo_dir = os.path.normpath(csar_path_name)

        else:
            # Path must be a file. Create name for the directory into
            # which to extract the archive
            local_repo_dir = os.path.join(constants.LOCAL_REPO_ROOT, repo_name)

            # Check if the archive is a CSAR file
            try:
                logger.debug("Extracting %s into %s", 
                             csar_path_name, local_repo_dir)
                with zipfile.ZipFile(csar_path_name, 'r') as csar:
                    if not csar.infolist():
                        # Empty zip archive
                        raise ArchiveEmpty("'{0}' is empty".format(csar_path_name))
                    for info in csar.infolist():
                        # Extract each file separately so we can make
                        # sure to preserve permissions
                        out_path = csar.extract(info.filename, path=local_repo_dir)
                        permissions = info.external_attr >> 16
                        os.chmod(out_path, permissions)                        
            except zipfile.BadZipfile as e:
                # Not a zip file. Must be a regular service template
                # file. Create repository folder and copy file into it.
                logger.debug("Copying %s into %s", 
                             csar_path_name, local_repo_dir)
                os.makedirs(local_repo_dir)
                shutil.copy(csar_path_name, local_repo_dir)

        # Create file URL for the repo. Make sure file URL ends with a
        # '/'
        path = os.path.abspath(local_repo_dir)
        url = urllib.parse.urljoin(
            u'file:', 
            urllib.request.pathname2url(path + os.sep)
        )

        # Call superclass constructor
        super(CsarRepository, self).__init__(
            name=repo_name,
            url=url,
            **kwargs
        )
        # Set the file name
        self.file_name = csar_file_name


    def delete_repo_dir(self) -> None:
        # Make sure we have a file URL
        parsed_url = urllib.parse.urlparse(self.url)
        if (parsed_url.scheme != 'file'):
            # Not a local repository. Don't do anything
            return

        # Extract the path name from the repo URL
        local_repo_dir = urllib.request.url2pathname(parsed_url.path)

        # Only delete repositories inside the repository root, never the
        # root itself. Compare resolved paths: a string prefix would also
        # admit a sibling such as '<root>-backup', and '..' or a symlink
        # could lead out of the root.
        repo_dir = Path(local_repo_dir).resolve()
        repo_root = Path(constants.LOCAL_REPO_ROOT).resolve()
        if repo_dir == repo_root or not repo_dir.is_relative_to(repo_root):
            logger.warning("Not deleting [%s]: outside the repository root [%s]",
                           local_repo_dir, constants.LOCAL_REPO_ROOT)
            return

        # Delete
        logger.debug("Deleting directory [%s]", local_repo_dir)
        shutil.rmtree(local_repo_dir)


    def delete(self) -> None:
        """Delete a CSAR repository. This deletes the profiles defined in this
        repository and all the files in the repo directory

        """
        # First, delete the profiles
        for profile in reversed(self.profiles):
            profile.delete()
            
        # Delete the directory
        self.delete_repo_dir()

        # Delete this object from the database
        db.session.delete(self)


    def get_meta_data(self) -> Optional[list[dict[str, str]]]:
        """If this repository represents a TOSCA archive, return the archive
        meta data

        Returns:
          meta_data(list): list of archive meta data blocks
          None:            if no meta data found

        Raises:
          InvalidMetaData (if metadata are invalid)
        """

        # First, try to get meta data from meta data file. Returns
        # None if no meta data found. This mething will raise
        # InvalidMetaData if meta data are found but invalid.
        meta_data = self._get_meta_data_from_file()
        if meta_data: return meta_data

        # No meta data file found. Archive is supposed to contain a
        # single file in the top-level directory that contains a
        # service template.  Return meta data containing name of this
        # template
        template_name = self._get_template_file()
        if not template_name: return None

        # Return synthesized list of meta meta data blocks
        return [{'Entry-Definitions': template_name }]


    def _get_meta_data_from_file(self) -> Optional[list[dict[str, str]]]:
        """If this repository contains a TOSCA archive meta data file,
        retrieve the meta data from that file

        Returns:
          meta_data(list): list of archive meta data blocks
          None:            if no meta data found

        Raises:
          InvalidMetaData: 
            - when multiple meta files found
            - when unable to read meta data file 
            - when meta data version is incorrect
            - when meta data point to invalid entry definitions file
        """

        # Check if meta file exists in the root of the archive
        meta_file_name = None
        try:
            meta_file_name = self.retrieve(TOSCA_META_FILE_NAME)
        except IOError:
            # No meta data file found in the root directory.
            pass

        # Check if meta file exists in the TOSCA-Metadata subdirectory
        # of the archive
        try:
            tosca_meta_file_name = os.path.join(TOSCA_META_DIR_NAME, 
                                                TOSCA_META_FILE_NAME)
            file_name = self.retrieve(tosca_meta_file_name)
            if meta_file_name:
                # CSAR contains two meta files, which is not allowed
                raise InvalidMetaData("Multiple 'TOSCA.meta' files found")
            else:
                meta_file_name = file_name
        except IOError:
            # No meta data file found in TOSCA-Metadata directory.
            pass

        # Make sure we found exactly one file
        if not meta_file_name: return None

        # Return meta data from file
        return self._read_meta_file(meta_file_name)


    def _read_meta_file(self, meta_file_name: str) -> list[dict[str, str]]:
        """Read meta data from a TOSCA archive meta data file, one block at a
        time.

        Returns:
          meta_data(list): list of archive meta data blocks

        Raises:
          InvalidMetaData: 
            - when unable to read meta data file 
            - when meta data contain invalid YAML
            - when meta data version is incorrect
            - when meta data point to invalid entry definitions file
        """

        # First, open Meta file
        try:
            with open(meta_file_name, 'r') as meta_file:
                # Meta is a list of blocks. Initialize empty list
                meta = []

                # Read the first block
                block = self._read_meta_file_block(meta_file)
                while block:
                    # Append to meta data
                    meta.append(block)
                    # Try to read more blocks
                    block = self._read_meta_file_block(meta_file)
                if not meta:
                    # Empty meta data
                    raise InvalidMetaData("Empty TOSCA meta file")
        except (OSError, IOError) as e:
            msg = "Unable to open meta data file {0} in {1}: {2}".format(
                meta_file_name, self.url, e)
            raise InvalidMetaData(msg)

        # Validate meta file contents. Invalid contents results in
        # InvalidMetaData exception.
        self._validate_meta_data(meta)
            
        # All good now
        return meta

    
    def _validate_meta_data(self, meta: list[dict[str, str]]) -> None:
        """Validate meta data retrieved from a TOSCA archive meta data file.

        Returns:
          None

        Raises:
          InvalidMetaData
        """
        
        # Validation must make sure all required meta data are present
        # in block zero
        block_zero = meta[0]
        
        # First, validate meta data version
        try:
            csar_version = str(block_zero['CSAR-Version'])
            if not csar_version in TOSCA_CSAR_VERSIONS:
                msg = "Unsupported CSAR version {0} in {1}".format(
                    csar_version, TOSCA_META_FILE_NAME)
                raise InvalidMetaData(msg)
        except KeyError as e:
            msg = "Missing CSAR version in {0}: {1}".format(
                TOSCA_META_FILE_NAME, e)
            raise InvalidMetaData(msg)

        # Make sure mandatory fields are present
        try:
            if csar_version == '1.1':
                template_version = block_zero['TOSCA-Meta-File-Version']
            template_author = block_zero['Created-By']
            template_name = block_zero['Entry-Definitions']
        except KeyError as e:
            msg = "Missing meta data in {0}: {1}".format(
                TOSCA_META_FILE_NAME, e)
            raise InvalidMetaData(msg)


    def _read_meta_file_block(self, meta_file: Any) -> dict[str, str]:
        """Read and parse a single block in a Meta file.  Each block is a
        list of lines. Blocks are separated by one or more empty
        lines.
        """
        
        # Initialize the block.
        block = []

        # Read lines in the block one by one
        line = meta_file.readline()
        while line:
            # First, strip trailing whitespace characters (including
            # newline). This turns empty lines into 'None'
            line = line.rstrip()
            if not line:
                # We found an empty line
                if block:
                    # Empty line in a non-empty block. This signals
                    # 'end-of-block'. Break out of the loop
                    break
                else:
                    # Current block is still empty. We allow for empty
                    # lines at the start of a block, so just ignore
                    # this line.
                    pass
            else:
                # The line we just read is not empty. Is this a
                # continuation line? Continuation lines start with
                # white space
                if line[0] in whitespace:
                    # This is a continuation line. Append to previous
                    # line in the block
                    try:
                        prev_line = block.pop()
                    except IndexError:
                        # No previous line, which means this is an
                        # empty block. Continuation lines are invalid
                        # at the start of a block.
                        raise InvalidMetaData("Invalid continuation line")
                    # Strip leading whitespaces and append to previous line
                    line = line.lstrip()
                    line = prev_line + " " + line
                # Add the line to the block.
                block.append(line)
                
            # read next line
            line = meta_file.readline()

        # Parse all the lines in the block
        block_data = {}
        for line in block:
            try:
                [ key, value ] = line.split(':', 1)
                block_data[key.strip()] = value.strip()
            except ValueError:
                msg = 'invalid line ({})'.format(line)
                raise InvalidMetaData(msg)
            
        # All done
        return block_data


    def _get_template_file(self) -> Optional[str]:
        """If this repository represents a TOSCA archive, but the archive does
        not contain a meta data file, the archive is supposed to
        contain a single file in its top-level directory that contains
        the top-level service template. Return the name of that
        template.

        Returns: 
          template_name(str): name of top-level template file if it
            exists
          None: if the archive does not contain exactly one file in
            its top level directory

        Raises:
          None
        """

        # For the time being, we only support local file repositories
        parsed_url = urllib.parse.urlparse(self.url)
        if (parsed_url.scheme != 'file'):
            # Not a local file repository
            return None

        # Extract the path name from the repo URL
        local_repo_dir = urllib.request.url2pathname(parsed_url.path)

        # Get a list of all the files in the top-level repo directory
        local_repo_files = [ e.name for e in os.scandir(local_repo_dir) if e.is_file()]

        # Make sure we have only top-level file
        if len(local_repo_files) != 1:
            logger.error("Repository does not contain a single top-level file")
            return None
        else:
            return local_repo_files[0]

############################
# CSAR LOOKUP FUNCTIONS
############################

def get_csar(csar_id: int) -> CsarRepository:
    """Return CSAR by id.

    Args:
      csar_id(int): id of the CSAR

    Raises:
      sqlalchemy.orm.exc.NoResultFound: when no csar found with the
        specified csar id
      sqlalchemy.orm.exc.MultipleResultsFound: when multiple csars
        found with the specified csar id
    """
    csar_entity = CsarRepository.query.filter(
        CsarRepository.id == csar_id
    ).one()
    return csar_entity


        

"""
Module definining Tosca Import entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2018-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Type hints
from typing import Any, Optional

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db


class ToscaImport(db.Model):
    """A ToscaImport object associates an imported profile with its
    importing profile. Association objects are required because
    profiles can be imported by multiple other profiles.

    Attributes:
      namespace(string): The optional namespace into which the profile
        is imported. If no prefix is specified, the profile is
        imported into the default namespace.
    """

    # Fields
    id =          db.Column(db.Integer, primary_key=True, autoincrement=True)
    implicit =    db.Column(db.Boolean, default=False)
    # Set where the importer is an implementing file and the imported
    # profile the one it implements: the row puts the implemented
    # profile's names in the file's default namespace, and keeps the
    # implemented profile from being deleted while the file exists.
    implements =  db.Column(db.Boolean, default=False)
    namespace =   db.Column(db.String, nullable=True)
    importer_id = db.Column(db.Integer, db.ForeignKey('tosca_profile.id'))
    imported_id = db.Column(db.Integer, db.ForeignKey('tosca_profile.id'))
    position =    db.Column(db.Integer)

    # Relationships
    imported =    db.relationship('ToscaProfile', 
                                  uselist=False,
                                  foreign_keys='ToscaImport.imported_id',
                                  backref='importer')

    @property
    def name(self) -> Optional[str]:
        try:
            return self.url
        except AttributeError:
            try:
                return self.profile
            except AttributeError:
                try:
                    return self.file
                except AttributeError:
                    return None


    # Constructor
    def __init__(self,
                 line: Optional[int] = None,
                 file: Optional[str] = None,
                 url: Optional[str] = None,
                 profile: Optional[str] = None,
                 meta_data: Optional[Any] = None,
                 description: Optional[str] = None,
                 repository: Optional[str] = None,
                 namespace_uri: Optional[str] = None,
                 namespace: Optional[str] = None,
    ) -> None:
        """Create a new ToscaImport instance"""

        # First, call superclass constructor
        super(ToscaImport, self).__init__()

        # ToscaImport-specific initialization
        if line != None: self.line = line
        if meta_data: self.meta_data = meta_data
        if description: self.description = description
        if repository != None: self.repository = repository
        if namespace != None: self.namespace = namespace

        # v1-specific keywords
        if file != None: self.file = file
        if namespace_uri != None: self.namespace_uri = namespace_uri

        # v2-specific keywords
        if profile != None: self.profile = profile
        if url != None: self.url = url

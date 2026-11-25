"""
Module defining Tosca Profile entity
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2016-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
from typing import Any, Optional

from tosca_core.models.imprt import ToscaImport

logger: logging.Logger = logging.getLogger(__name__)

# Database support
from tosca_core import db

# SQLAlchemy support
from sqlalchemy import delete, select
from sqlalchemy.orm import backref
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.orderinglist import ordering_list

# Exception support
from sqlalchemy import func
import sqlalchemy.orm.exc
import tosca_core.models.exceptions as te

# Support for TOSCA keywords that are shared between all entities
import tosca_core.models.entity

# Type management functions
import tosca_core.models.type as tt

# Types used in relationships
import tosca_core.models.function_declaration


class ToscaProfile(tosca_core.models.entity.ToscaEntityMixin, db.Model):
    """A ToscaProfile object defines a collection of type definitions,
    repository definitions, and policy definitions, as well as any
    other profiles that it imports. When used with TOSCA v1.x, each
    profile object also references the version of the Simple Profile
    that it uses.
    """
    
    ################################################################################
    # Keys
    ################################################################################
    
    # Primary key
    id =                  db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    # Every profile has a repository id, but only profiles that were
    # defined in a CSAR have a csar ID.
    _repo_id =            db.Column(db.Integer,
                                    db.ForeignKey('tosca_repository.id'),
                                    nullable=True,
                                    index=True)
    _csar_id =            db.Column(db.Integer,
                                    db.ForeignKey('tosca_repository.id'),
                                    nullable=True,
                                    index=True)
    
    ################################################################################
    # Fields
    ################################################################################

    # TOSCA Version will not be set for the builtin profile
    tosca_version =       db.Column(db.String, nullable=True)
    
    # Optional fields start with '_' and have corresponding getters
    # and setters to ensure that retrieving fields consistently raises
    # an AttributeError when not set.  Note that 'nullable' defaults
    # to True, but we explicitly set the 'nullable' flag for clarity.
    creation_time =       db.Column(db.DateTime, server_default=func.now())
    has_well_known_name = db.Column(db.Boolean, default=False)
    tosca_file_path =     db.Column(db.String)

    # For ordered list of profiles in CsarRepository
    position =            db.Column(db.Integer)
    
    # Return the well-known name for this profile. If no well-known
    # name is defined, check the well-known name of this profile's
    # importer.
    @property
    def well_known_name(self) -> Optional[str]:
        if self.has_well_known_name:
            return self.name
        else:
            for importer in self.importer:
                well_known_name = importer.importer.well_known_name
                if well_known_name: return well_known_name
        return None

    # The profile this profile implements, where it was defined by an
    # implementing file; None otherwise.
    @property
    def implements(self) -> Optional["ToscaProfile"]:
        for _import in self.imported:
            if _import.implements:
                return _import.imported
        return None

    # The implementing profiles that implement this one.
    @property
    def implemented_by(self) -> list["ToscaProfile"]:
        return [_import.importer for _import in self.importer
                if _import.implements and _import.importer is not None]

    # How a profile is named to an operator: its name where it has a
    # well-known one, otherwise its ID.
    @property
    def label(self) -> str:
        return self.name if self.has_well_known_name else f"Profile {self.id}"

    ################################################################################
    # Model Navigation.  
    ################################################################################

    # The repository that contains the definitions for this profile.
    repository =          db.relationship('ToscaRepository',
                                          uselist=False,
                                          foreign_keys='ToscaProfile._repo_id')

    # Imported profiles
    imported =            db.relationship('ToscaImport',
                                          collection_class=ordering_list('position'),
                                          order_by='ToscaImport.position',
                                          foreign_keys='ToscaImport.importer_id',
                                          lazy='selectin',
                                          backref=backref('importer', uselist=False))

    # When creating a service template, a back-reference to the
    # associated profile is automatically created.
    @property
    def service(self) -> Any:
        if not self._service:
            raise AttributeError("Profile <{0}> does not have 'service'".format(self.name))
        return self._service

    @service.setter
    def service(self, value: Any) -> None:
        if value: self._service = value

    ################################################################################
    # Collections. Retrieving a collection never raises an
    # AttributeError. If there are no elements in the container, an
    # empty container is returned.
    ################################################################################

    interface_types =     db.relationship('ToscaInterfaceType',
                                          collection_class=attribute_mapped_collection('name'),
                                          foreign_keys='ToscaType._profile_id',
                                          back_populates='profile',
                                          overlaps='profile')
    node_types =          db.relationship('ToscaNodeType',
                                          collection_class=attribute_mapped_collection('name'),
                                          foreign_keys='ToscaType._profile_id',
                                          back_populates='profile',
                                          overlaps='profile')
    relationship_types =  db.relationship('ToscaRelationshipType',
                                          collection_class=attribute_mapped_collection('name'),
                                          foreign_keys='ToscaType._profile_id',
                                          back_populates='profile',
                                          overlaps='profile')
    group_types =         db.relationship('ToscaGroupType',
                                          collection_class=attribute_mapped_collection('name'),
                                          foreign_keys='ToscaType._profile_id',
                                          back_populates='profile',
                                          overlaps='profile')
    data_types =          db.relationship('ToscaDataType',
                                          collection_class=attribute_mapped_collection('name'),
                                          foreign_keys='ToscaType._profile_id',
                                          back_populates='profile',
                                          overlaps='profile')
    artifact_types =      db.relationship('ToscaArtifactType',
                                          collection_class=attribute_mapped_collection('name'),
                                          foreign_keys='ToscaType._profile_id',
                                          back_populates='profile',
                                          overlaps='profile')
    capability_types =    db.relationship('ToscaCapabilityType',
                                          collection_class=attribute_mapped_collection('name'),
                                          foreign_keys='ToscaType._profile_id',
                                          back_populates='profile',
                                          overlaps='profile')
    policy_types =        db.relationship('ToscaPolicyType',
                                          collection_class=attribute_mapped_collection('name'),
                                          foreign_keys='ToscaType._profile_id',
                                          back_populates='profile',
                                          overlaps='profile')

    repositories =        db.relationship('ToscaRepository',
                                          collection_class=attribute_mapped_collection('name'),
                                          foreign_keys='ToscaRepository._profile_id',
                                          back_populates='profile')
    
    functions =           db.relationship('ToscaFunctionDeclaration',
                                          collection_class=attribute_mapped_collection('name'),
                                          foreign_keys='ToscaFunctionDeclaration._profile_id',
                                          back_populates='profile')
    
    ################################################################################
    # Constructor
    ################################################################################

    def __init__(self,
                 repository: Any,
                 tosca_file_path: str,
                 tosca_version: Optional[str] = None,
                 **kwargs: Any
    ) -> None:
        # First, call superclass constructor
        super(ToscaProfile, self).__init__(**kwargs)

        # ToscaProfile-specific initialization
        self.repository = repository
        self.tosca_file_path = tosca_file_path
        self.tosca_version = tosca_version

    ################################################################################
    # Profile management methods
    ################################################################################

    def add_type(self, type_entity: Any) -> None:
        """Add a type entity to this profile """
        # Link type to profile
        type_entity.profile = self
        # Add
        tt.add_type(type_entity)


    def get_relationship_type(self, type_name: str, visited: Optional[list[str]] = None) -> Any:
        return self.get_type(type_name, 'relationship', visited)

    def get_artifact_type(self, type_name: str, visited: Optional[list[str]] = None) -> Any:
        return self.get_type(type_name, 'artifact', visited)

    def get_group_type(self, type_name: str, visited: Optional[list[str]] = None) -> Any:
        return self.get_type(type_name, 'group', visited)

    def get_policy_type(self, type_name: str, visited: Optional[list[str]] = None) -> Any:
        return self.get_type(type_name, 'policy', visited)

    def get_data_type(self, type_name: str, visited: Optional[list[str]] = None) -> Any:
        return self.get_type(type_name, 'data', visited)

    def get_node_type(self, type_name: str, visited: Optional[list[str]] = None) -> Any:
        return self.get_type(type_name, 'node', visited)

    def get_capability_type(self, type_name: str, visited: Optional[list[str]] = None) -> Any:
        return self.get_type(type_name, 'capability', visited)

    def get_interface_type(self, type_name: str, visited: Optional[list[str]] = None) -> Any:
        return self.get_type(type_name, 'interface', visited)


    def get_type(self, type_name: str, type_class: str, visited: Optional[list[str]] = None) -> Any:
        """Look up a type in this profile and the profiles imported by this
        profile. We track profiles that have already been visited to
        avoid searching the same profile more than once.  There are
        two scenarios:

        1. If the type name is qualified using a namespace prefix,
           only the profiles in the specified namespace are searched.

        2. If the type name is not qualified using a namespace prefix,
           only the default namespace is searched. The default
           namespace contains all 'locally-defined' types as well as
           any imported profiles that don't have an associated
           namespace prefix.

        Args:
          type_name(str): The name of the type to find. This name
            could be qualified using a namespace prefix.
          type_class(str): The class of type to find.
          visited(list): list of profile names that have already been
            searched

        Returns:
          ToscaType: type entity for the specified name

        Raises:
          TypeNotFound: if a type could not be found for the given
            name

        """
        # Track every profile we touch (qualified lookups can recurse
        # through pass-through imports too, so cycle protection has
        # to apply regardless of qualification).
        if visited is None:
            visited = []
        if self.name in visited:
            raise te.TypeNotFound("already visited")
        visited = visited + [self.name]

        # Is the type qualified using a namespace prefix? If so,
        # separate the name into a namespace name and a type name
        # within that namespace.
        type_parts = type_name.split(':', 1)
        if len(type_parts) == 2:
            namespace = type_parts[0]
            type_name = type_parts[1]
        else:
            namespace = None

        # Check locally-defined types only if the 'default' namespace
        # is specified (i.e. when the 'namespace' name is None)
        if not namespace:
            try:
                return self.get_local_type(type_name, type_class)
            except te.TypeNotFound:
                pass

        # Type not found in locally-defined types. Check the profiles
        # that are imported in the specified namespace.
        for imported in self.imported:
            if namespace:
                if imported.namespace == namespace:
                    # Direct namespace match -- look up the local name
                    # inside that profile.
                    try:
                        return imported.imported.get_type(type_name, type_class,
                                                          visited=visited)
                    except te.TypeNotFound:
                        pass
                elif not imported.namespace:
                    # Import has no explicit namespace; the prefix may
                    # resolve via the imported file's own transitive
                    # imports (e.g. a TOSCA 1.3 file that implicitly
                    # brings in the simple profile under 'tosca:'). Pass
                    # the still-qualified name down.
                    qualified = f"{namespace}:{type_name}"
                    try:
                        return imported.imported.get_type(qualified, type_class,
                                                          visited=visited)
                    except te.TypeNotFound:
                        pass
            else:
                # Default namespace: imports without an explicit prefix,
                # plus the implicit-tosca shim for v1.x interop.
                if (not imported.namespace or
                    (imported.namespace == 'tosca' and imported.implicit)):
                    try:
                        return imported.imported.get_type(type_name, type_class,
                                                          visited=visited)
                    except te.TypeNotFound:
                        pass

        # Type not found
        error = "'{0}' not found in namespace '{1}'".format(type_name,
                                                            namespace if namespace else 'default')
        raise te.TypeNotFound(error)


    def get_local_type(self, type_name: str, type_class: str) -> Any:
        """Find a type in this profile without checking imported profiles.
        """
        # First, get the correct type collection.
        if type_class == 'data':
            types = self.data_types
        elif type_class == 'node':
            types = self.node_types
        elif type_class == 'relationship':
            types = self.relationship_types
        elif type_class == 'artifact':
            types = self.artifact_types
        elif type_class == 'capability':
            types = self.capability_types
        elif type_class == 'interface':
            types = self.interface_types
        elif type_class == 'group':
            types = self.group_types
        elif type_class == 'policy':
            types = self.policy_types
        else:
            raise Exception("type class '{0}' not found".format(type_class))

        # Look up the type in the type collection.
        try:
            return types[type_name]
        except KeyError:
            # Not found. Short name perhaps?
            for name, type_entity in types.items():
                try:
                    if type_entity.short_name == type_name:
                        return type_entity
                except AttributeError:
                    # Type entity has no short name
                    pass
        # Not found
        raise te.TypeNotFound(type_name)


    def get_node_types(self, this_profile_only: bool = False) -> dict[str, Any]:
        return self.get_types('node', this_profile_only=this_profile_only)

    def get_relationship_types(self, this_profile_only: bool = False) -> dict[str, Any]:
        return self.get_types('relationship', this_profile_only=this_profile_only)

    def get_artifact_types(self, this_profile_only: bool = False) -> dict[str, Any]:
        return self.get_types('artifact', this_profile_only=this_profile_only)

    def get_group_types(self, this_profile_only: bool = False) -> dict[str, Any]:
        return self.get_types('group', this_profile_only=this_profile_only)

    def get_policy_types(self, this_profile_only: bool = False) -> dict[str, Any]:
        return self.get_types('policy', this_profile_only=this_profile_only)

    def get_data_types(self, this_profile_only: bool = False) -> dict[str, Any]:
        return self.get_types('data', this_profile_only=this_profile_only)

    def get_capability_types(self, this_profile_only: bool = False) -> dict[str, Any]:
        return self.get_types('capability', this_profile_only=this_profile_only)

    def get_interface_types(self, this_profile_only: bool = False) -> dict[str, Any]:
        return self.get_types('interface', this_profile_only=this_profile_only)


    def get_types(self, type_class: str, visited: Optional[list[str]] = None, this_profile_only: bool = False) -> dict[str, Any]:
        """Get all types of a specified type class from this profile as
        well as its imported profiles. If 'this_profile_only' is set to
        True, we don't include types from imported "well-known"
        profiles.
        """

        # Initialize types
        types = dict()

        if visited:
            # Have we already checked this profile?
            if self.name in visited:
                return types
        else:
            visited = list()
        # Add this profile to the 'visited' list
        visited.append(self.name)

        # Add locally-defined types
        types.update(self.get_local_types(type_class))

        # Next, add imported profiles that don't advertise a
        # well-known-name. A type this profile defines wins over an
        # imported type of the same name, and an earlier import over a
        # later one, which is the order get_type resolves names in.
        for imported in self.imported:
            if this_profile_only and imported.imported.has_well_known_name:
                # Skip this profile
                pass
            else:
                imported_types = imported.imported.get_types(type_class,
                                                             visited=visited,
                                                             this_profile_only=this_profile_only)
                for type_name, type_entity in imported_types.items():
                    types.setdefault(type_name, type_entity)

        # All done
        return types


    def get_local_types(self, type_class: str) -> dict[str, Any]:
        """Get all types of a specified type class from the profile without
        checking its imported profiles"""
        if type_class == 'data':
            return self.data_types
        elif type_class == 'node':
            return self.node_types
        elif type_class == 'relationship':
            return self.relationship_types
        elif type_class == 'artifact':
            return self.artifact_types
        elif type_class == 'capability':
            return self.capability_types
        elif type_class == 'interface':
            return self.interface_types
        elif type_class == 'group':
            return self.group_types
        elif type_class == 'policy':
            return self.policy_types
        else:
            raise Exception("type class '{0}' not found".format(type_class))


    def get_artifact_types_for_ext(self, ext: str) -> list[Any]:
        """Get the list of artifact types for a give file extension

        Args:
          ext(str): The file extension

        Returns:
          ToscaArtifactType[]

        Raises:
          None
        """

        # Get all artifact types for this service
        artifact_types = self.get_artifact_types()

        # Filter out the ones that support the given file extension
        returned_types = []
        for artifact_type_name, artifact_type in artifact_types.items():
            if artifact_type.supports_extension(ext):
                returned_types.append(artifact_type)

        # All done
        return returned_types


    def get_function(self, function_name: str, visited: Optional[list[str]] = None) -> Any:
        """Look up a function in this profile and the profiles imported by
        this profile. We track profiles that have already been visited
        to avoid searching the same profile more than once.  There are
        two scenarios:

        1. If the function name is qualified using a namespace prefix,
           only the profiles in the specified namespace are searched.

        2. If the function name is not qualified using a namespace
           prefix, only the default namespace is searched. The default
           namespace contains all 'locally-defined' functions as well
           as any imported profiles that don't have an associated
           namespace prefix.
        Args:
          function_name(str): The name of the function to find. This name
            could be qualified using a namespace prefix.
          visited(list): list of profile names that have already been
            searched
        Returns:
          ToscaFunctionDeclaration: function declaration for the
            specified name
        Raises:
          FunctionNotFound: if a function could not be found for the
            given name

        """
        if visited is None:
            visited = []
        if self.name in visited:
            raise te.FunctionNotFound("already visited")
        visited = visited + [self.name]

        # Is the function qualified using a namespace prefix? If so,
        # separate the name into a namespace name and a function name
        # within that namespace.
        function_parts = function_name.split(':', 1)
        if len(function_parts) == 2:
            namespace = function_parts[0]
            function_name = function_parts[1]
        else:
            namespace = None

        # Check locally-defined functions only if the 'default' namespace
        # is specified (i.e. when the 'namespace' name is None)
        if not namespace:
            try:
                return self.get_local_function(function_name)
            except te.FunctionNotFound:
                pass

        # Function not found in locally-defined functions. Check the profiles
        # that are imported in the specified namespace.
        for imported in self.imported:
            if namespace:
                if imported.namespace == namespace:
                    try:
                        return imported.imported.get_function(function_name, visited=visited)
                    except te.FunctionNotFound:
                        pass
                elif not imported.namespace:
                    # See get_type for the rationale: namespace prefixes
                    # can resolve transitively via no-namespace imports.
                    qualified = f"{namespace}:{function_name}"
                    try:
                        return imported.imported.get_function(qualified, visited=visited)
                    except te.FunctionNotFound:
                        pass
            else:
                if (not imported.namespace or
                    (imported.namespace == 'tosca' and imported.implicit)):
                    try:
                        return imported.imported.get_function(function_name, visited=visited)
                    except te.FunctionNotFound:
                        pass

        # Function not found
        error = "function '${0}' not found in namespace '{1}'".format(function_name,
                                                                      namespace if namespace else 'default')
        raise te.FunctionNotFound(error)


    def get_local_function(self, function_name: str) -> Any:
        """Get a function defined locally in this profile"""

        # Check locally-defined functions
        functions = self.functions
        try:
            return functions[function_name]
        except KeyError:
            # Not found
            raise te.FunctionNotFound(function_name)


    def get_repository(self, repository_name: str, visited: Optional[list[str]] = None) -> Any:
        """Look up a repository in this profile and the profiles imported by
        this profile. We track profiles that have already been visited
        to avoid searching the same profile more than once.  There are
        two scenarios:

        1. If the repository name is qualified using a namespace prefix,
           only the profiles in the specified namespace are searched.

        2. If the repository name is not qualified using a namespace
           prefix, only the default namespace is searched. The default
           namespace contains all 'locally-defined' repositories as well
           as any imported profiles that don't have an associated
           namespace prefix.
        Args:
          repository_name(str): The name of the repository to find. This name
            could be qualified using a namespace prefix.
          visited(list): list of profile names that have already been
            searched
        Returns:
          ToscaRepositoryDeclaration: repository declaration for the
            specified name
        Raises:
          RepositoryNotFound: if a repository could not be found for the
            given name

        """
        if visited is None:
            visited = []
        if self.name in visited:
            raise te.RepositoryNotFound("already visited")
        visited = visited + [self.name]

        # Is the repository qualified using a namespace prefix? If so,
        # separate the name into a namespace name and a repository name
        # within that namespace.
        repository_parts = repository_name.split(':', 1)
        if len(repository_parts) == 2:
            namespace = repository_parts[0]
            repository_name = repository_parts[1]
        else:
            namespace = None

        # Check locally-defined repositories only if the 'default' namespace
        # is specified (i.e. when the 'namespace' name is None)
        if not namespace:
            try:
                return self.get_local_repository(repository_name)
            except te.RepositoryNotFound:
                pass

        # Repository not found in locally-defined repositories. Check the profiles
        # that are imported in the specified namespace.
        for imported in self.imported:
            if namespace:
                if imported.namespace == namespace:
                    try:
                        return imported.imported.get_repository(repository_name, visited=visited)
                    except te.RepositoryNotFound:
                        pass
                elif not imported.namespace:
                    # See get_type for the rationale.
                    qualified = f"{namespace}:{repository_name}"
                    try:
                        return imported.imported.get_repository(qualified, visited=visited)
                    except te.RepositoryNotFound:
                        pass
            else:
                if (not imported.namespace or
                    (imported.namespace == 'tosca' and imported.implicit)):
                    try:
                        return imported.imported.get_repository(repository_name, visited=visited)
                    except te.RepositoryNotFound:
                        pass

        # Repository not found
        error = "'{0}' not found in namespace '{1}'".format(repository_name,
                                                            namespace if namespace else 'default')
        raise te.RepositoryNotFound(error)


    def get_local_repository(self, repository_name: str) -> Any:
        """Get a repository defined locally in this profile"""

        # Check locally-defined repositories
        repositories = self.repositories
        try:
            return repositories[repository_name]
        except KeyError:
            # Not found
            raise te.RepositoryNotFound(repository_name)


    ################################################################################
    # Profile Deletion
    ################################################################################

    def delete(self, cleanup_imports: bool = True, check_only: bool = False) -> Optional[bool]:
        # Is this profile currently imported by some other profile?
        if row := db.session.execute(
                select(ToscaImport.importer_id, ToscaImport.implements).where(
                    ToscaImport.imported_id == self.id).where(
                        ToscaImport.importer_id.is_not(None)).limit(1)).first():
            imported_by, implements = row
            relation = 'implemented' if implements else 'imported'
            msg = f"Cannot delete Profile {self.id}. It is {relation} by Profile {imported_by} (and maybe others)."
            if check_only:
                logger.info(msg)
                return False
            else:
                raise te.DeletionRefused(msg)
        else:
            if check_only:
                return True
        if svc := self._service:
            if not svc.delete(check_only=True):
                msg = f"Cannot delete Profile {self.id}; its Service Template cannot be deleted."
                if check_only:
                    logger.info(msg)
                    return False
                else:
                    raise te.DeletionRefused(msg)
            else:
                if check_only:
                    return True
                svc.delete()
        all_my_types = db.session.scalars(select(tt.ToscaType).where(tt.ToscaType._profile_id == self.id)).all()
        with db.session.no_autoflush:
            for my_type in all_my_types:
                db.session.delete(my_type)
        # print(f"DEBUG: Deleting <Profile {self.id}>")
        db.session.delete(self)

        db.session.flush()
        potential_orphan_ids = set(
            db.session.scalars(select(ToscaImport.imported_id).where(ToscaImport.importer_id.is_(None)).where(
                ToscaImport.imported_id.is_not(None))).all())
        not_orphans = set()
        for profile_id in potential_orphan_ids:
            if db.session.execute(select(ToscaImport.importer_id).where(ToscaImport.imported_id == profile_id).where(
                    ToscaImport.importer_id.is_not(None)).limit(1)).scalar_one_or_none():
                not_orphans.add(profile_id)
        orphan_ids = sorted(potential_orphan_ids - not_orphans)
        # print(f"DEBUG: … potential_orphans: {potential_orphan_ids}, excluded: {sorted(not_orphans)}, to_delete: {sorted(orphan_ids)}")
        for profile_id in orphan_ids:
            if orphan := db.session.get(ToscaProfile, profile_id):
                if not orphan.has_well_known_name:
                    # print(f"DEBUG: Deleting <Profile {orphan.id}> (orphaned)")
                    orphan.delete(cleanup_imports=False)
                else:
                    # print(f"DEBUG: … skipping <Profile {orphan.id}> - has_well_known_name == True")
                    pass
        if cleanup_imports:
            db.session.flush()
            result = db.session.execute(delete(ToscaImport).where(ToscaImport.importer_id.is_(None)))
            # print(f"DEBUG: {result.rowcount} ToscaImport objects deleted")
        else:
            # print(f"DEBUG: (cleanup of ToscaImport objects deferred)")
            pass


############################
# PROFILE LOOKUP FUNCTIONS
############################

def get_profile(profile_id: int) -> ToscaProfile:
    """Return service entity by id.

    Args:
      profile_id(int): id of the profile

    Raises:
      sqlalchemy.orm.exc.NoResultFound: when no profile found with the
        specified profile id
      sqlalchemy.orm.exc.MultipleResultsFound: when multiple profiles
        found with the specified profile id
    """
    profile_entity = ToscaProfile.query.filter(
        ToscaProfile.id == profile_id
    ).one()
    return profile_entity


def get_profile_by_name(profile_name: str) -> ToscaProfile:
    """Return profile by name. Note that name lookups are case-insensitive.

    Args:
      profile_name(str): name of the profile

    Raises:
      sqlalchemy.orm.exc.NoResultFound: when no profile found with the
        specified name
      sqlalchemy.orm.exc.MultipleResultsFound: when multiple profiles
        found with the specified name (profiles
        are supposed to be unique)

    """
    profile_entity = ToscaProfile.query.filter(
        func.lower(ToscaProfile.name) == profile_name.lower()
    ).one()
    return profile_entity


##############################
# PROFILE ADDITION FUNCTIONS
##############################

def add_profile(profile_entity: ToscaProfile) -> None:
    """Add profile. Make sure we don't already have a profile with this
    name

    Args:
      profile_entity(ToscaProfile): profile to be
        added

    Raises:
      te.ProfileAlreadyExists: if this profile is already in the
        database
      sqlalchemy.orm.exc.MultipleResultsFound: when multiple
        profiles with this name are found in the database. This is
        a catastrophic error
    """
    # Check if profile already exist with the same name
    try:
        profile = get_profile_by_name(profile_entity.name)
        # Profile with this name already exists. Raise an error
        logger.debug("%s already in database",
                     profile_entity.name)
        raise te.ProfileAlreadyExists("Profile {0} already in database".format(
            profile_entity.name))

    except sqlalchemy.orm.exc.NoResultFound: 
        # Good. Profile does not already exist.
        pass
        
    # Not a duplicate. Add
    db.session.add(profile_entity)

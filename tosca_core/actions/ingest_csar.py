"""Functions for importing TOSCA Cloud Service Archives into the
system catalogs
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# JSON support for log formatting
import json

# Path support for naming Other-Definitions templates
import os

# URL composition for resolving relative repository file URIs
import urllib.parse

# Database support
from tosca_core import db
from tosca_core.constants import constants

# Exceptions
import sqlalchemy.orm.exc
import tosca_core.models.exceptions as te

# Interface to repository management functions
import tosca_core.models.repository as tr
import tosca_core.models.csar_repository as tc

# Interface to profile management functions
import tosca_core.models.profile as tn
import tosca_core.models.imprt as ti

# Interface to parser
import tosca_core.schema.parser as tp

# Validator support
from tosca_core.validate import get_validator
from tosca_core.validate.context import validation_options


def ingest_csar_file(csar_file_name: str, csar_path_name: str,
                      validate_only: bool = False,
                      skip_file_checks: bool = False) -> tuple:
    """Ingest a TOSCA Cloud Service Archive (CSAR) file. Note that in
    addition to a csar file, the provided file could also be a single
    TOSCA YAML file or an archive directory.

    Ingesting involves the following:
    - Extract the CSAR contents into a local (archive) repository
    - Create a profile
    - Initialize the profile based on the CSAR contents
    - Create a Service Template object if the CSAR file includes a
      service template

    Args:
      csar_path_name(str): name of TOSCA CSAR file
      csar_path_name(str): path to the TOSCA CSAR file
      validate_only(bool): if true, we only validate the CSAR file
        without actually importing it into the system.
      skip_file_checks(bool): if true, skip existence checks for
        artifact files. Useful when artifacts live on networks the
        validator can't reach.

    Returns:
      (profile(ToscaProfile), validation_errors(dict)): tuple
        containing the created profile and validation errors. If the
        archive is valid, validation_errors is None.
    """

    # 'skip_file_checks' only makes sense when validating: any CSAR
    # that is actually ingested must have reachable artifact files.
    if skip_file_checks and not validate_only:
        return None, 'skip_file_checks requires validate_only'

    # Bracket the ingestion with the archive's name. Everything logged in
    # between -- validator errors above all -- is emitted several layers down,
    # where the archive is no longer in scope: `process_service_template`
    # receives a profile and the parsed data and has no idea which file they
    # came from. Onboarding a set of archives therefore produced a run of
    # identical, unattributable errors. This line is what makes the ones in
    # between readable.
    logger.info("Ingesting CSAR '%s'", csar_file_name)
    with validation_options(skip_file_checks=skip_file_checks):
        result, errors = _ingest_csar_file(csar_file_name, csar_path_name, validate_only)

    # Only failures are reported. Success needs no line of its own: the next
    # 'Ingesting' entry marks the end of this one, so an archive with nothing
    # logged against it is an archive that ingested cleanly.
    if errors:
        # A string reason is short and worth naming; validation errors are a
        # structured dict already logged in detail above and returned to the
        # caller, so they are not repeated here.
        reason = errors if isinstance(errors, str) else 'validation errors'
        logger.error("CSAR '%s': ingestion failed (%s)", csar_file_name, reason)
    return result, errors


def name_other_definitions(csar_repo: tc.CsarRepository, head_name: str) -> None:
    """Name the service templates an archive's Other-Definitions carry,
    which nothing else names: the name of what heads the archive, then
    the template's path in it. The extension is dropped, and so is a
    file name of 'main', so 'substitutions/dcn/main.yaml' in a profile
    'com.example:1.0' is 'com.example:1.0/substitutions/dcn'.

    Args:
      csar_repo(CsarRepository): the ingested archive
      head_name(str): the name of the archive's entry: a profile's
        name, or the catalog entry's
    """
    for profile in csar_repo.profiles[1:]:
        try:
            service_template = profile.service
        except AttributeError:
            continue
        stem, _ = os.path.splitext(profile.tosca_file_path.lstrip('/'))
        if os.path.basename(stem) == 'main':
            stem = os.path.dirname(stem)
        service_template.name = f"{head_name}/{stem}"


def _ingest_csar_file(csar_file_name: str, csar_path_name: str,
                       validate_only: bool) -> tuple:
    # Create a local csar repository from the CSAR file
    try:
        csar_repo = tc.CsarRepository(csar_file_name, csar_path_name, validate_only)
        tr.add_repository(csar_repo)
    except tc.ArchiveDoesNotExist:
        return None, 'not found'
    except tc.ArchiveNotAFile:
        return None, 'not a file'
    except tc.ArchiveEmpty:
        return None, 'empty archive'
    except Exception as e:
        return None, 'internal error ({0})'.format(str(e))

    # Retrieve the top-level TOSCA file from the Cloud Service Archive
    # (as specified in the meta data)
    try:
        meta_data = csar_repo.get_meta_data()
        if not meta_data:
            return csar_repo, 'no metadata found in archive'
    except tc.InvalidMetaData as e:
        # csar_repo.delete_repo_dir()
        msg = 'invalid archive ({})'.format(str(e))
        return csar_repo, msg
    file_name = meta_data[0]['Entry-Definitions']

    # Ingest top-level TOSCA file. This results in the creation of a
    # profile which can (optionally) have a service template
    # associated with it.
    validation_errors = dict()
    profile, errors = ingest_tosca_file(csar_repo, file_name)
    if errors:
        validation_errors[file_name] = errors
    else:
        csar_repo.profiles.append(profile)
        
    # Ingest other TOSCA files if necessary
    try:
        other = meta_data[0]['Other-Definitions']
        import shlex
        other_files =  shlex.split(other)
        for other_file in other_files:
            other_profile, errors = ingest_tosca_file(csar_repo, other_file)
            if errors:
                validation_errors[other_file] = errors
            else:
                csar_repo.profiles.append(other_profile)
    except KeyError:
        # No other definitions
        pass

    # A CSAR must either define a profile or a service catalog entry
    # but not both
    profile = csar_repo.profiles[0] if csar_repo.profiles else None
    try:
        if profile.has_well_known_name:
            # This CSAR defines a profile. Make sure it does not also
            # define a service catalog entry.
            try:
                service = profile.service
                return csar_repo, 'defines both profile and service catalog entry'
            except AttributeError:
                pass
        else:
            # This CSAR does not define a profile. Make sure it does
            # define a service catalog entry. Validating only is a dry
            # run of onboarding, so it refuses this too.
            try:
                service = profile.service
            except AttributeError:
                return csar_repo, 'no profile or service catalog entry defined'
    except AttributeError as e:
        # No top level profile, which will have been flagged as an
        # error elsewhere.
        pass
    
    # All done
    return csar_repo, validation_errors


def ingest_tosca_file(repository: tr.ToscaRepository, file_name: str) -> tuple:
    """Retrieve the named TOSCA file from the specified repository and
    ingest its contents into the profile catalog. This results in the
    creation of a profile as well as (optionally) a service template.

    Args: 
      repository(ToscaRepository): repository that represents the
        contents of the csar file
      file_name(string): name of the TOSCA file in the
        repository

    Returns:
      None: if the service definitions are valid
      validation_errors(dict): validation errors if the service
        definitions are invalid.
    """

    # Retrieve TOSCA file from the repository
    tosca_file_path = repository.get_absolute_path(file_name, '/')
    try:
        tosca_file = repository.retrieve(tosca_file_path)
        tosca_file_url = repository.get_file_url(tosca_file_path)
    except IOError as e:
        logger.error("File [%s] not found in [%s]: %s",
                     tosca_file_path, repository.name, e)
        return None, "not found" 

    # Get TOSCA file data from the retrieved TOSCA file
    tosca_data, validation_errors = tp.get_tosca_data(tosca_file)
    if validation_errors:
        logger.info("error loading '%s':\n%s",
                    tosca_file,
                    json.dumps(validation_errors, indent=2, default=str))
        return None, validation_errors
    
    # Do the TOSCA file data specify a profile name?
    try:
        profile_name = tosca_data.profile
        has_well_known_name = True
    except AttributeError:
        # No profile name specified. Use TOSCA file URL instead
        profile_name = tosca_file_url
        has_well_known_name = False
    
    # Create profile into which to load the TOSCA file data
    try:
        profile = tn.ToscaProfile(repository, tosca_file_path, name=profile_name,
                                  tosca_version=tosca_data.tosca_definitions_version)
        profile.has_well_known_name = has_well_known_name
        tn.add_profile(profile)
    except te.ProfileAlreadyExists:
        # Duplicate profile
        return None,   { profile_name: 'duplicate profile name'  }
    except Exception as e:
        return None,   'internal error ({0})'.format(str(e)) 

    # Track import stack to avoid circular imports, and a registry of all
    # profiles created in this session to avoid re-processing the same file
    # when it is reachable via multiple import paths.
    tosca_data.import_stack = [ tosca_file_url ]
    tosca_data.profile_registry = {}

    # Load data into profile
    errors = load_tosca_data(profile, tosca_data)

    # All done
    if errors:
        return profile, errors 
    else:
        return profile, None


def load_tosca_data(profile: tn.ToscaProfile, tosca_data) -> dict:
    """Load TOSCA file data into the provided profile

    Args: 

      tosca_data(ToscaData): TOSCA file data to
        load into this profile

    Returns:
      validation_errors(dict): (possibly empty) dict of validation
        errors

    Raises:
      None
    """

    logger.debug("Load %s TOSCA file data into %s",
                 tosca_data.tosca_definitions_version, profile.name)

    # First, initialize validation errors dict
    validation_errors = {}

    # Process any repositories specified in the TOSCA file data first
    # since subsequent processing steps (such as imports) may need to
    # retrieve items from these repositories.
    errors = process_repositories(profile, tosca_data)
    if errors:
        validation_errors['repositories'] = errors

    # Next, process imports defined in the TOSCA file data. This will
    # recursively call 'load_tosca_data' to create profiles for
    # each of the imported TOSCA files.
    errors = process_imports(profile, tosca_data)
    if errors:
        validation_errors['imports'] = errors

    # Update profile meta_data with metadata from the TOSCA file
    # data. Note that metadata from imported TOSCA files may have
    # already been applied. Top-level TOSCA file wins.
    errors = process_meta_data(profile, tosca_data)
    if errors:
        validation_errors.update(errors)

    # Process type definitions from the TOSCA file data. Data types
    # may define constraints using functions that have not yet been
    # processed, since functions are processed after data types have
    # been processed. Therefore, we separate out validation of data
    # type constraints and handle it after functions have been
    # processed.
    errors, refined = process_types(profile, tosca_data)
    if errors:
        validation_errors.update(errors)
    if not refined:
        # The types were not validated, so nothing that follows would
        # be validated against a complete model.
        return validation_errors

    # Process functions from the TOSCA file data.
    errors = process_functions(profile, tosca_data)
    if errors:
        validation_errors['functions'] = errors

    # Process data type constraints. Data type constraints can use
    # functions that have just now been processed.
    errors = process_validation_for_data_types(profile, tosca_data)
    if errors:
        validation_errors.update(errors)

    # Process policies from the TOSCA file data.
    errors = process_policies(profile, tosca_data)
    if errors:
        validation_errors['policies'] = errors

    # (Optionally) create a service template object from the TOSCA
    # file data.
    errors = process_service_template(profile, tosca_data)
    if errors:
        validation_errors.update(errors)

    # All done
    return validation_errors


def process_repositories(profile: tn.ToscaProfile, tosca_data) -> dict | None:
    """Validate and add any ToscaRepositories specified in the TOSCA file
    data to this profile.

    Args: 
      tosca_data(ToscaData): TOSCA file data from which to
        retrieve the repositories to validate and add.

    Returns:
      validation_errors(dict): (possibly empty) dict of validation
        errors

    Raises:
      None
    """

    # Extract repositories from the TOSCA file data
    try:
        repositories = tosca_data.get_repositories()
    except AttributeError as e:
        # No repositories defined.
        logger.debug("TOSCA file data: no repositories to validate: %s", e)
        return None

    # Get repository validator
    validator = get_validator('ToscaRepository')

    # Validate repositories
    validation_errors = {}
    for repository_name, repository in repositories.items():
        try:
            # A 'file:<relative_path>' URL refers to a directory
            # inside the containing CSAR; resolve it against the
            # CSAR's own URL so the repository points at an actual
            # location and downstream URL composition works.
            try:
                url = tr.normalize_file_uri(repository._url)
                if not tr.is_uri(url):
                    repository._url = urllib.parse.urljoin(profile.repository.url, url)
            except AttributeError:
                pass

            profile.repositories[repository_name] = repository
            errors = validator.validate_repository(repository)
            if not errors:
                # Where on the orchestrator host a 'file:' repository may
                # point is the operator's decision: inside this CSAR, or
                # inside a configured local repository root.
                csar_url = getattr(profile.repository, 'url', '') if profile.repository else ''
                refused = tr.check_local_repository(repository.url, csar_url)
                if refused:
                    errors = {'url': refused}
            if errors:
                logger.error("TOSCA file data: invalid repository '%s'",
                             repository_name)
                validation_errors[repository_name] = errors
        except Exception as e:
            logger.error("TOSCA file data: error validating repository '%s': %s",
                        repository_name, e)
            error = 'validator error: {0}'.format(str(e))
            validation_errors[repository_name] = error

    # All done
    return validation_errors


def process_meta_data(profile: tn.ToscaProfile, tosca_data) -> dict:
    """Process meta data specified in a TOSCA file data and add them to
    this profile.

    Args: 
      tosca_data(dict): TOSCA file data from which to
        retrieve the meta_data

    Returns:
      validation_errors(dict): (possibly empty) dict of validation
        errors

    Raises:
      None
    """

    # First, copy description
    try:
        profile.description = tosca_data.description
    except AttributeError:
        pass

    # Then copy and validate meta_data.  Note that we named this
    # meta_data to avoid name conflicts.
    validation_errors = {}
    try:
        meta_data = tosca_data.meta_data
    except AttributeError:
        # No meta data defined.
        logger.debug("TOSCA file data: no meta_data to validate")
        return validation_errors

    # Validate meta data
    try:
        validator = get_validator('ToscaMetadata')
        errors = validator.validate_meta_data(meta_data)
        if errors:
            logger.error("TOSCA file data: invalid meta data")
            validation_errors['metadata'] = errors
        else:
            profile.meta_data = meta_data

    except Exception as e:
        logger.error("TOSCA file data: error validating meta_data: %s", e)
        validation_errors['meta_data'] = "validator error ({0})".format(e)

    # All done
    return validation_errors


def process_types(profile: tn.ToscaProfile, tosca_data) -> tuple[dict, bool]:
    """Validate types defined in the TOSCA file data and add them to the
    provided profile.

    Args: 
      tosca_data(dict): TOSCA file data from which to
        retrieve the type definitions.

    Returns:
      (validation_errors, refined): a (possibly empty) dict of
        validation errors, and whether every refinement the types
        declare was checked and completed. When it is False the types
        have not been validated, and nothing should be validated
        against them.

    Raises:
      None
    """

    # Retrieve type definitions from the TOSCA file data
    artifact_types = tosca_data.get_artifact_types()
    capability_types = tosca_data.get_capability_types()
    data_types = tosca_data.get_data_types()
    group_types = tosca_data.get_group_types()
    interface_types = tosca_data.get_interface_types()
    node_types = tosca_data.get_node_types()
    relationship_types = tosca_data.get_relationship_types()
    policy_types = tosca_data.get_policy_types()

    # Add types to the profile.
    validation_errors = {}
    for type_entity in \
        artifact_types + \
        capability_types + \
        data_types + \
        group_types + \
        interface_types + \
        node_types + \
        relationship_types + \
        policy_types :

        try:
            profile.add_type(type_entity)
        except te.TypeAlreadyExists:
            validation_errors[type_entity.name] = {
                'line' : type_entity.line,
                'error': 'duplicate'
            }

    # Kinds in the order they are validated: every kind a type can
    # refer to comes before the kinds that refer to it.
    kinds = [
        ('data_types', 'ToscaDataType', data_types),
        ('interface_types', 'ToscaInterfaceType', interface_types),
        ('artifact_types', 'ToscaArtifactType', artifact_types),
        ('capability_types', 'ToscaCapabilityType', capability_types),
        ('relationship_types', 'ToscaRelationshipType', relationship_types),
        ('node_types', 'ToscaNodeType', node_types),
        ('group_types', 'ToscaGroupType', group_types),
        ('policy_types', 'ToscaPolicyType', policy_types),
    ]

    # Check and complete every property and attribute refinement
    # before any type is validated, so that nothing validated reads a
    # refinement that is still incomplete. A refinement that fails its
    # checks stops here: validating the rest would validate a model
    # built on it.
    refinement_errors = {}
    for kind, validator_name, type_entities in kinds:
        errors = get_validator(validator_name).complete_refinements(type_entities)
        if errors: refinement_errors[kind] = errors
    if refinement_errors:
        validation_errors.update(refinement_errors)
        return validation_errors, False

    # Validate all type entities. This will fix up type references
    # etc.
    for kind, validator_name, type_entities in kinds:
        errors = get_validator(validator_name).validate_types(type_entities)
        if errors: validation_errors[kind] = errors

    # All done
    return validation_errors, True


def process_validation_for_data_types(profile: tn.ToscaProfile, tosca_data) -> dict:
    """Validate data type constraints defined in the TOSCA file data and
    add them to the data type definitions already in the profile.

    Args: 
      tosca_data(dict): TOSCA file data from which to
        retrieve the type definitions.
    Returns:
      validation_errors(dict): (possibly empty) dict of validation
        errors
    Raises:
      None
    """

    # Retrieve data type definitions that have already been added to
    # this profile.
    data_types = profile.get_data_types(this_profile_only=True)

    # Validate all data type validations.
    validation_errors = {}
    validator = get_validator('ToscaDataType')
    errors = validator.validate_validation_for_data_types(data_types) 
    if errors: validation_errors['data_types'] = errors
    return validation_errors


def process_functions(profile: tn.ToscaProfile, tosca_data) -> dict | None:
    """Validate functions defined in the TOSCA file data and add them to
    the provided profile.

    Args: 
      tosca_data(dict): TOSCA file data from which to retrieve
        the function definitions.

    Returns:
      validation_errors(dict): (possibly empty) dict of validation
        errors

    Raises:
      None
    """

    # Extract functions from the TOSCA file data
    try:
        functions = tosca_data.functions
    except AttributeError as e:
        # No functions defined.
        logger.debug("TOSCA file data: no functions to validate: %s", e)
        return None

    # Get function validator
    validator = get_validator('ToscaFunction')

    # Validate functions
    validation_errors = {}
    for function_name, function in functions.items():
        try:
            profile.functions[function_name] = function
            errors = validator.validate_function_declaration(function)
            if errors:
                logger.error("TOSCA file data: invalid function '%s'", 
                             function_name)
                validation_errors[function_name] = errors
        except Exception as e:
            logger.error("TOSCA file data: error validating function '%s': %s",
                        function_name, e)
            error = 'validator error: {0}'.format(str(e))
            validation_errors[function_name] = error

    # All done
    return validation_errors


def process_policies(profile: tn.ToscaProfile, tosca_data) -> dict | None:
    """Validate policies defined in the TOSCA file data and add them to
    the provided profile.

    Args: 
      tosca_data(dict): TOSCA file data from which to retrieve
        the policy definitions.

    Returns:
      validation_errors(dict): (possibly empty) dict of validation
        errors

    Raises:
      None
    """

    # Extract policies from the TOSCA file data
    try:
        policies = tosca_data.get_policies()
    except AttributeError as e:
        # No policies defined.
        logger.debug("TOSCA file data: no policies to validate: %s", e)
        return None

    # Get policy validator
    validator = get_validator('ToscaPolicy')

    # Validate policies
    validation_errors = {}
    tosca_policies = {}
    for policy_name, policy in policies.items():
        try:
            if not validator.is_valid_policy(policy):
                logger.error("TOSCA file data: invalid policy '%s'", 
                             policy_name)
                validation_errors[policy.name] = {
                    'line' : policy.line,
                    'error': 'invalid'
                }
            else:
                # Valid policy.
                tosca_policies[policy_name] = policy

        except Exception as e:
            logger.error("TOSCA file data: error validating policy '%s': %s",
                        policy_name, e)

    # All done
    return validation_errors


def process_service_template(profile: tn.ToscaProfile, tosca_data) -> dict:
    """Import a fully-validated ToscaServiceTemplate object from the TOSCA
    file data and associate it with this profile.

    Args: 
      tosca_data(dict): TOSCA file data from which to retrieve
        the service template.

    Returns:
      validation_errors(dict): (possibly empty) dict of validation
        errors

    Raises:
      None
    """

    validation_errors = {}

    # Extract service template from the TOSCA file data.
    try:
        service_template = tosca_data.get_service_template()
        db.session.add(service_template)
        service_template.profile = profile
    except AttributeError as e:
        # No service_template defined.
        logger.debug("TOSCA file data: no service template to validate: %s", e)
        return validation_errors

    # Validate service_template object
    try:
        validator = get_validator('ToscaServiceTemplate')
        errors = validator.validate_service_template(service_template)
        if errors:
            logger.error("TOSCA file data: invalid service template")
            validation_errors['service_template'] = errors
    except Exception as e:
        logger.error("TOSCA file data: error validating service template: %s", e)
        validation_errors['service_template'] = "validator error ({0})".format(e)

    # All done
    return validation_errors


def process_imports(profile: tn.ToscaProfile, tosca_data) -> dict:
    """Create fully-validated ToscaProfile objects from imports specified
    in the provided TOSCA file data and associate them with this
    profile. Also perform implicit imports of built-in types and
    Simple Profile types as necessary.

    Args: 
      tosca_data(dict): TOSCA file data that contain the
        import statements from which to create the imported profiles.

    Returns:
      validation_errors(dict): (possibly empty) dict of validation
        errors

    Raises:
      None
    """

    # All profiles import the builtin profile (except for the
    # 'builtin' profile itself). We 'import' this first to make sure
    # other imported profiles don't override built-in definitions.
    if profile.name != 'builtin':
        errors = process_implicit_import(profile, tosca_data, 'builtin')
        if errors:
            return errors
    
    # Next, process all imported files
    try:
        imports = tosca_data.imports
    except AttributeError:
        # TOSCA file data do not import any other TOSCA files.
        imports = list()

    # Iterate over imports
    validation_errors = {}
    count = 0
    for _import in imports:
        # Create an import name for logging purposes.
        name = _import.name if _import.name else 'import[{0}]'.format(count)

        # Log deprecation warning if necessary
        try:
            namespace_uri = _import.namespace_uri
            logger.info("import '%s': namespace_uri keyname has been deprecated",
                        name)
        except AttributeError:
            # Good. No deprecated namespace_uri statement.
            pass

        # Check if the import statement includes a 'file' keyword.
        try:
            file = _import.file
            # We have a file. Process it.
            try:
                errors = process_import_v1(profile, tosca_data, _import)
                if errors:
                    validation_errors[name] = errors
            except Exception as e:
                logger.error("Error importing '%s' %s", name, e)
                validation_errors[name] = str(e)
        except AttributeError:
            # No file specified in 'import' statement. Must be a
            # Version 2 import statement. Process it.
            try:
                errors = process_import_v2(profile, tosca_data, _import)
                if errors:
                    validation_errors[name] = errors
            except  sqlalchemy.orm.exc.NoResultFound:
                logger.error("Profile '%s' not found", name)
                validation_errors[name] = 'profile not found'
            except Exception as e:
                logger.error("Error importing '%s' %s", name, e)
                validation_errors[name] = str(e)

        # Continue
        count = count+1

    # Finally, 1.x versions of TOSCA automatically import a normative
    # TOSCA Simple Profile (unless we're the simple profile itself)
    if (profile.tosca_version.startswith("tosca_simple_yaml") and not 
        (profile.well_known_name and
         profile.well_known_name.startswith("http://docs.oasis-open.org/tosca/ns/simple/yaml/1"))):
        definitions_version = tosca_data.tosca_definitions_version
        supported_versions = constants.SUPPORTED_DEFINITIONS_VERSIONS
        simple_profile_name = supported_versions[definitions_version]
        errors = process_implicit_import(profile, tosca_data, simple_profile_name)
        if errors:
            validation_errors['simple'] = errors

    # All done
    return validation_errors


def process_implicit_import(profile: tn.ToscaProfile, tosca_data, implicit_profile_name: str) -> dict:
    # Find the Profile that must be imported implicitly
    try:
        implicit_profile = tn.get_profile_by_name(implicit_profile_name)
        _import = ti.ToscaImport(namespace="tosca")
        db.session.add(_import)
        _import.imported = implicit_profile
        _import.implicit = True
        profile.imported.append(_import)
        return {}
    except  sqlalchemy.orm.exc.NoResultFound:
        # Implicit profile not found
        error = 'Profile {0} not found'.format(implicit_profile_name)
    except Exception as e:
        error = 'internal error ({0})'.format(str(e))

    # Return the error
    return { implicit_profile_name: error }


def process_import_v1(profile: tn.ToscaProfile, containing_tosca_data, _import) -> dict | str | None:
    """Create a fully-validated profile from a Version 1.x import
    statement specified in the TOSCA file data and associate it with
    this profile. At this point, we have verified that the import
    statement includes a 'file' keyword.

    Args: 
      containing_tosca_data(dict): TOSCA file data that contain
        the import statement for which to create the imported
        profile.
      _import(ToscaImport): import statement for which to create the
        imported profile

    Returns:
      validation_errors(dict): (possibly empty) dict of validation
        errors

    Raises:
      None
    """

    logger.debug("%s: importing %s", profile.name, _import.file)
    # First, get the repository from which to import the TOSCA file.
    try:
        repository = profile.get_repository(_import.repository)
    except AttributeError:
        # No repository specified. if the name specified in 'file' is
        # the name of a named profile we can just import that
        # profile.
        try:
            return import_well_known_profile(profile, containing_tosca_data, _import)
        except  sqlalchemy.orm.exc.NoResultFound:
            # Not a well-known profile
            pass

    # Import TOSCA file from repository
    return import_tosca_file_from_repo(profile, containing_tosca_data, _import)


def process_import_v2(profile: tn.ToscaProfile, containing_tosca_data, _import) -> dict | str | None:
    """Create a fully-validated profile from a Version 2.x import
    statement specified in the TOSCA file data and associate it
    with this profile. 

    Args: 
      containing_tosca_data(dict): TOSCA file data that contain
        the import statement for which to create the imported profile.
      _import(ToscaImport): import statement for which to create the
        imported profile

    Returns:
      validation_errors(dict): (possibly empty) dict of validation
        errors

    Raises:
      sqlalchemy.orm.exc.NoResultFound: when well-known-profile is not
        found
    """
    # Are we importing a well known profile?
    try:
        well_known_profile_name = _import.profile
        return import_well_known_profile(profile, containing_tosca_data, _import)
    except AttributeError:
        # We're not importing a well-known profile. Are we importing a
        # URL?
        try:
            url = _import.url
            return import_tosca_file_from_repo(profile, containing_tosca_data, _import)
        except AttributeError:
            # No URL specified either.
            return 'import statement does not specify content'


def import_tosca_file_from_repo(profile: tn.ToscaProfile, containing_tosca_data, _import) -> dict | str | None:
    """Import a TOSCA file from its repository into this profile. We have
    already verified that the import statement includes either a 'url'
    keyword (in the case of Version 2) or a 'file' keyword (in the
    case of Version 1)

    Args: 
      profile(ToscaProfile): profile into which to import the profile
        created from the imported TOSCA file data
      containing_tosca_data(dict): TOSCA file data that contain
        the import statement from which to create the imported profile.
      _import(ToscaImport): import statement that identifies the TOSCA
        file as well as the repository from which to import the file.

    Returns:
      validation_errors(dict): (possibly empty) dict of validation
        errors

    Raises:
      None
    """

    # Retrieve the TOSCA file URL from the import statement.
    try:
        # Version 1?
        url = _import.file
    except AttributeError:
        # Must be Version 2
        url = _import.url

    # 'file:' URIs without a host refer to a local file. Strip the
    # scheme so the path is resolved within the containing CSAR
    # (sandboxing the import and making 'file:<path>' equivalent to a
    # bare relative path).
    url = tr.normalize_file_uri(url)

    # First, get the repository from which to import the TOSCA file.
    try:
        repository = profile.get_repository(_import.repository)
        file_name = url
        relative_to = '/'
    except AttributeError:
        # No repository specified. If the specified TOSCA file is
        # formatted as a URI we can try to find the repository from
        # the URL.
        if tr.is_uri(url):
            # No profile found for that URI. Create a repository based
            # on the URI.
            try:
                repository, url_path = tr.create_repository_for_url(url)
                _import.file = url_path
                _import.url = url_path
                file_name = url_path
                relative_to = '/'
            except Exception as e:
                # URI specified in 'file' is not a valid URL
                logger.error("Profile %s: error creating repository for '%s': %s",
                             profile.name, url, str(e))
                return 'not a valid URL'
        else:
            # File is not a URI. It must refer to a TOSCA file that is
            # in same repository as the containing TOSCA file.
            # Imported file names within the same repo are relative,
            # which means we need to create absolute path name for the
            # imported file.
            repository = profile.repository
            file_name = url
            relative_to = profile.tosca_file_path
    except Exception:
        # Repository not found. Can't continue.
        errors = {}
        errors['repository'] ="'{0}' not found".format(_import.repository)
        return errors

    # Get absolute path name for file in repo
    tosca_file_path = repository.get_absolute_path(file_name, relative_to)
    
    # Prevent circular imports
    imported_file_url = repository.get_file_url(tosca_file_path)
    if imported_file_url in containing_tosca_data.import_stack:
        logger.debug("%s: CIRCULAR", tosca_file_path)
        return 'circular import'

    # Make sure the TOSCA file exists in repository.
    try:
        tosca_file = repository.retrieve(tosca_file_path)
    except IOError as e:
        logger.error("TOSCA file [%s] not found: %s", tosca_file_path, e)
        return 'file not found'

    # Get TOSCA file data from file
    tosca_data, errors = tp.get_tosca_data(tosca_file)
    if errors:
        return errors

    # Do the TOSCA file data define a profile?
    try:
        profile_name = tosca_data.profile
        if profile_name == profile.name:
            # Don't create a new profile if profile name is the same
            # as the profile name of the importing file
            profile_name = imported_file_url
            has_well_known_name = False
        else:
            # Create a new well-known profile
            has_well_known_name = True
    except AttributeError:
        # No profile name specified. Use TOSCA file name instead.
        profile_name = imported_file_url
        has_well_known_name = False

    # At this point, we're sure we have a valid import
    # statement. Append to list of profile imports
    profile.imported.append(_import)

    # Create the profile if it doesn't already exist.
    # Check the session-level registry first: if the profile was already
    # created in this session but not yet flushed, get_profile_by_name()
    # won't find it, causing the same file to be processed again.
    profile_registry = getattr(containing_tosca_data, 'profile_registry', None)
    if profile_registry is not None and profile_name in profile_registry:
        _import.imported = profile_registry[profile_name]
        return None
    try:
        _import.imported = tn.get_profile_by_name(profile_name)
        # This profile has already been ingested. Don't load again.
        if profile_registry is not None:
            profile_registry[profile_name] = _import.imported
        return None
    except  sqlalchemy.orm.exc.NoResultFound:
        # No profile found with the specified name. Create one
        _import.imported = tn.ToscaProfile(repository, tosca_file_path, name=profile_name,
                                           tosca_version=tosca_data.tosca_definitions_version)
        _import.imported.has_well_known_name = has_well_known_name
        # Register before recursing so any re-import of this file is caught
        if profile_registry is not None:
            profile_registry[profile_name] = _import.imported

    # Load the TOSCA file data into profile
    tosca_data.import_stack = containing_tosca_data.import_stack + [ imported_file_url ]
    tosca_data.profile_registry = profile_registry
    return load_tosca_data(_import.imported, tosca_data)


def import_well_known_profile(profile: tn.ToscaProfile, containing_tosca_data, _import) -> str | None:
    """Import the well-known profile specified by '_import' into
    profile. We have already verified that the import statement
    includes either a 'profile' keyword (in the case of Version 2) or
    a 'file' keyword (in the case of Version 1)

    Args: 
      profile(ToscaProfile): profile into which to import the
        well-known-profile
      _import(ToscaImport): import statement that identifies the
        well-known-profile to be imported.

    Returns:
      validation_errors(dict): (possibly empty) dict of validation
        errors

    Raises:
      sqlalchemy.orm.exc.NoResultFound: when well-known-profile is not
        found
    """
    # Import statement must not include a repository
    try:
        repository = _import.repository
        return "'repository' not allowed when importing well-known profiles"
    except AttributeError:
        pass

    try:
        # Version 1?
        well_known_profile_name = _import.file
    except AttributeError:
        # Must be Version 2
        well_known_profile_name = _import.profile

    # Perform the import
    db.session.add(_import)
    _import.imported = tn.get_profile_by_name(well_known_profile_name)
    profile.imported.append(_import)
    logger.debug("Importing existing profile '%s'", well_known_profile_name)
    return None

        

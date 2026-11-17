"""
ToscaValidator class
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Logging support
import logging
logger = logging.getLogger(__name__)

# Exceptions and the boolean built-in for the shared boolean-expression validator
import tosca_core.models.exceptions as te
import tosca_core.models.builtin_types as builtin_types


class ToscaValidator(object):
    """The ToscaValidator class is the base class for all Tosca
    validators.
    """

    def __init__(self) -> None:
        """Constructor
        """
        super(ToscaValidator, self).__init__()


    def _validate_boolean_expression(self, owner: object, expression: object,
                                     label: str, **kwargs) -> tuple:
        """Validate that `expression` is a well-formed 2.0 boolean
        function. Shared validation tail used wherever TOSCA expects a
        boolean function expression -- node filters, workflow step
        filters / preconditions, policy trigger conditions, property /
        data-type validations, substitution filters.

        Args:
          owner: validation context (passed as the first argument to
            validate_function_value).
          expression: the (already 2.0-shaped) function to validate.
          label: short name for the synthetic boolean declaration --
            shows up in some error messages.
          **kwargs: forwarded to validate_function_value (e.g.
            value_declaration=, skip_validation_for=).

        Returns:
          (errors, canonical). On success errors is empty {} and
          canonical is the validated form the caller should persist.
          On failure canonical is None and errors is the validator's
          error dict / string.
        """
        declaration = builtin_types.get('boolean').create_declaration(label)
        try:
            canonical = declaration.validate_function_value(owner, expression, **kwargs)
            return {}, canonical
        except te.ValidationError as e:
            return e.errors, None
        except TypeError:
            return 'not a boolean function', None
        except Exception as e:
            return "validator error ({0})".format(e), None


    def _resolve_attribute_declaration(self, context: object, path: object) -> tuple:
        """Resolve a TOSCA path to its target attribute declaration.

        Shared by the output-mapping validators (workflow output,
        property output, interface output, etc.) -- all of them parse
        a mapping into a ToscaPath, then resolve it to an attribute
        declaration with the same try/except shape. This is the
        shape, with one home.

        Returns:
          (attribute_declaration, error). On success error is None
          and attribute_declaration is the resolved declaration. On
          failure attribute_declaration is None and error is a string
          the caller can return verbatim.
        """
        try:
            entity_declaration = path.get_entity_declaration(context)
            return entity_declaration.get_attribute_declaration(path.sub_entity), None
        except ValueError:
            return None, "invalid keyword '{0}'".format(path.entity)
        except KeyError:
            return None, "attribute '{0}' not found".format(path.sub_entity)
        except TypeError as e:
            return None, "validator error ({0})".format(e)


    def add_line_number(self, errors: dict, entity: object) -> None:
        """If the 'errors' dict is not empty, add the line number of the
        'entity' if it exists
        """
        if errors:
            try:
                line = entity.line
                items = list(errors.items())
                errors.clear()
                errors['line'] = line
                errors.update(items)
            except AttributeError:
                pass


    def assert_not_present(self, entity: object, attribute_name: str) -> None:
        """Assert that the specified entity does not have an attribute with
        the provided name.

        Args:
          entity: any Tosca entity
          attribute_name(str): name of the attribute to check

        Raises:
          ValidationError: if the attribute is present
        """

        try:
            attribute = getattr(entity, attribute_name)
            if attribute:
                raise RuntimeError("Invalid attribute {0}".format(attribute_name))
        except AttributeError:
            pass


    def assert_key_not_present(self, entity: object, key_name: str) -> None:
        """Assert that the specified entity does not have an attribute
        with the provided name

        Args:
          entity: any Tosca entity
          key_name(str): name of the attribute to check

        Raises:
          RuntimeError: if the attribute is present
        """
        try:
            attribute = entity[key_name]
            raise RuntimeError("Invalid key {0}".format(key_name))
        except KeyError:
            pass


    def validate_declarations(self, containing_entity: object, attribute: str, validator: "ToscaValidator") -> dict:
        """Check if an entity has valid declarations. This method does the
        following for each declaration in the map:

        1. First, it checks to see if this declaration refines a
           previous declaration. If it is, it asserts that the refinement
           was completed before validation began, and validates it.

        2. If it is not a refinement, then it is a new declaration. It
           calls the entity-specific method to validate new
           declarations.

        Every refinement is checked and completed by 'complete_declarations'
        before anything is validated, so nothing is merged here.

        Args:
          containing_entity(ToscaType or ToscaDeclaration): entity
            that contains the declarations to validate
          attribute(str): name of the containing entity attribute that
            stores the declarations to validate
          validator(ToscaValidator): validator to use for each of the
            declarations

        Returns:
          (possibly empty) dict of validation errors

        Raises:
          None
        """

        logger.debug("%s: validate %s", containing_entity.name, attribute)

        validation_errors = {}

        # Find these declarations in  the containing entity
        try:
            declarations = getattr(containing_entity, attribute)
        except AttributeError:
            # The containing entity does not have declarations in the
            # specified attribute. Nothing to validate
            declarations = {}

        # Only proceed if we found at least one declaration
        if len(declarations) == 0:
            logger.debug("<%s>: no %s to validate", containing_entity.name, attribute)
            return validation_errors
            
        # Validate each declaration
        for declaration_name, declaration in declarations.items():

            try:
                # First, check to see if this is a refinement.
                entity_to_augment = containing_entity.get_entity_declaration_to_augment(
                    attribute, declaration_name)
                logger.debug("%s: validating %s refinement '%s'",
                             containing_entity.name, attribute,
                             declaration_name)
                
                # Validate the refinement, which was checked and merged
                # before validation began
                try:
                    self.assert_augmentation_complete(
                        containing_entity, attribute, declaration_name,
                        entity_to_augment, declaration)
                    errors = validator.validate_completed_augmentation(
                        containing_entity, declaration_name,
                        entity_to_augment, declaration)
                    if errors:
                        logger.error("<%s>: %s <%s>: invalid augmentation",
                                     containing_entity.name, attribute, declaration_name)
                        if isinstance(errors, dict):
                            self.add_line_number(errors, declaration)
                        validation_errors[declaration_name] = errors

                except Exception as e:
                    logger.error("<%s>: error while validating %s augmentation <%s>: %s", 
                                 containing_entity.name, attribute, declaration_name, e)
                    validation_errors[declaration_name] = "validation error ({0})".format(e)

            except KeyError:
                # New declaration. Validate
                try:
                    logger.debug("%s: validating %s declaration '%s'",
                                 containing_entity.name, attribute,
                                 declaration_name)
                
                    errors = validator.validate_declaration(containing_entity,
                                                            declaration)
                    if errors:
                        logger.error("<%s>: invalid %s declaration <%s>", 
                                     containing_entity.name, attribute, declaration_name)
                        validation_errors[declaration_name] = errors

                except Exception as e:
                    logger.error("<%s>: error while validating %s declaration <%s>: %s", 
                                 containing_entity.name, attribute, declaration_name, e)
                    validation_errors[declaration_name] = "validation error ({0})".format(e)

        # All done
        return validation_errors


    def complete_declarations(self, containing_entity: object, attribute: str, validator: "ToscaValidator") -> dict:
        """Check and complete each declaration in the map that refines one
        the containing entity inherits, before anything is validated.

        A refinement states only what it changes, and is completed by
        merging in the declaration it refines. Doing that here, ahead of
        validation, means an expression elsewhere in the containing
        entity reads a complete declaration whatever order the entity's
        parts are validated in. The declarations are then validated by
        'validate_declarations' with 'completed' set.

        Args:
          containing_entity(ToscaType): entity that contains the
            declarations to complete
          attribute(str): name of the containing entity attribute that
            stores them
          validator(ToscaValidator): validator for the declarations,
            which checks and completes each refinement

        Returns:
          (possibly empty) dict of validation errors, keyed the way
          'validate_declarations' keys them
        """
        validation_errors = {}
        declarations = getattr(containing_entity, attribute, None) or {}
        for declaration_name, declaration in declarations.items():
            try:
                entity_to_augment = containing_entity.get_entity_declaration_to_augment(
                    attribute, declaration_name)
            except KeyError:
                # A new declaration, not a refinement. What it holds may
                # still refine the declarations of its own type.
                entity_to_augment = None
            try:
                if entity_to_augment is not None:
                    errors = validator.complete_augmentation(containing_entity,
                                                             declaration_name,
                                                             entity_to_augment,
                                                             declaration)
                    if errors:
                        logger.error("<%s>: %s <%s>: invalid augmentation",
                                     containing_entity.name, attribute, declaration_name)
                        if isinstance(errors, dict):
                            self.add_line_number(errors, declaration)
                        validation_errors[declaration_name] = errors
                        continue
                errors = validator.complete_nested_refinements(containing_entity, declaration)
                if errors:
                    logger.error("<%s>: %s <%s>: invalid nested refinement",
                                 containing_entity.name, attribute, declaration_name)
                    validation_errors[declaration_name] = errors
            except Exception as e:
                logger.error("<%s>: error while completing %s augmentation <%s>: %s",
                             containing_entity.name, attribute, declaration_name, e)
                validation_errors[declaration_name] = "validation error ({0})".format(e)
        return validation_errors


    def complete_nested_refinements(self, containing_entity: object, declaration: object) -> dict:
        """Check and complete the refinements a declaration holds against
        its own type, which is where a declaration of a complex type keeps
        them. By default a declaration holds none; a validator whose
        declarations do overrides this.

        It is called for every declaration, whether or not the declaration
        itself refines one it inherits, because a declaration made for the
        first time can still refine what its type declares.

        Args:
          containing_entity(ToscaType or ToscaDeclaration): entity that
            contains the declaration
          declaration(ToscaDeclaration): declaration whose nested
            refinements to complete

        Returns:
          (possibly empty) dict of validation errors
        """
        return {}


    def complete_operation_refinements(self, container: object) -> dict:
        """Check and complete the refinements an interface type or an
        interface declaration holds: the inputs and outputs it refines,
        and the inputs and outputs of each of its operations and
        notifications.

        An operation is never merged itself; only its inputs and outputs
        are, and each finds what it refines by looking the operation up in
        what the container refines. An operation that is not found there
        has nothing to refine, so its inputs and outputs are new
        declarations. The walk then validates all of them, neither checking
        nor merging them again.

        Args:
          container(ToscaInterfaceType or ToscaInterfaceDeclaration):
            entity whose nested refinements to complete

        Returns:
          (possibly empty) dict of validation errors, keyed by 'inputs',
          'outputs', 'operations' and 'notifications'
        """
        from . import get_validator

        errors = {}
        property_validator = get_validator('ToscaPropertyDeclaration')
        for attribute in ('inputs', 'outputs'):
            attribute_errors = self.complete_declarations(container, attribute,
                                                          property_validator)
            if attribute_errors:
                errors[attribute] = attribute_errors
        for attribute in ('operations', 'notifications'):
            operation_errors = {}
            for operation_name, operation in (getattr(container, attribute, None) or {}).items():
                # The operation validator expects 'name' to be set
                setattr(operation, 'name', operation_name)
                nested = {}
                for nested_attribute in ('inputs', 'outputs'):
                    nested_errors = self.complete_declarations(operation, nested_attribute,
                                                               property_validator)
                    if nested_errors:
                        nested[nested_attribute] = nested_errors
                if nested:
                    self.add_line_number(nested, operation)
                    operation_errors[operation_name] = nested
            if operation_errors:
                errors[attribute] = operation_errors
        return errors


    def assert_augmentation_complete(self, containing_entity: object, attribute: str,
                                     declaration_name: str, entity_to_augment: object,
                                     declaration: object) -> None:
        """Check the invariant the walk relies on wherever it is told that a
        refinement was completed before validation began: the refinement
        carries everything the declaration it refines states, so no read
        of it answers less than the model says.

        A violation is an engine fault rather than anything the CSAR did,
        so it is reported and validation continues. It matters because the
        reads that used to resolve through the augmentation chain are
        gone: an incomplete declaration now answers with whatever it
        holds, which is a missing type, default or validation rather than
        an error.

        Args:
          containing_entity(ToscaType or ToscaDeclaration): entity that
            contains the declaration
          attribute(str): name of the attribute that stores it
          declaration_name(str): name of the declaration
          entity_to_augment(ToscaDeclaration): the declaration it refines
          declaration(ToscaDeclaration): the refinement
        """
        # An entity that is never merged has nothing to check. An operation
        # is one: a refinement of it is completed through its inputs and
        # outputs, and the operation itself is left alone.
        check = getattr(declaration, 'get_unmerged_fields', None)
        if check is None:
            return
        try:
            unmerged = check(entity_to_augment)
        except Exception as e:
            logger.error("<%s>: %s <%s>: unable to check completion: %s",
                         containing_entity.name, attribute, declaration_name, e)
            return
        if unmerged:
            logger.error("<%s>: %s <%s>: refinement was not completed before validation: %s",
                         containing_entity.name, attribute, declaration_name,
                         ', '.join(unmerged))


    def validate_completed_augmentation(self, containing_entity: object, declaration_name: str,
                                        entity_to_augment: object, declaration: object) -> dict:
        """Validate an augmentation that 'complete_declarations' has
        already checked and completed. By default it is validated as a
        declaration in its own right; a validator whose augmentations are
        validated differently from new declarations overrides this.

        Args:
          containing_entity(ToscaType or ToscaDeclaration): entity that
            contains the declaration
          declaration_name(str): name of the declaration
          entity_to_augment(ToscaDeclaration): the declaration it
            augments
          declaration(ToscaDeclaration): the completed augmentation

        Returns:
          (possibly empty) dict of validation errors
        """
        return self.validate_declaration(containing_entity, declaration)


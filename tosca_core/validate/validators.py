"""
Map of TOSCA validators
"""
__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2014-2026, Ubicity Corp."
__email__ = "info@ubicity.com"


# Logging support
import logging
logger = logging.getLogger(__name__)

# Importer
import importlib

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tosca_core.validate.validator import ToscaValidator

# Validator descriptors
tosca_validator_descriptors = {
    'ToscaArtifactType': {
        'module': 'tosca_core.validate.artifact_type',
        'class': 'ToscaArtifactTypeValidator'
        },
    'ToscaCapabilityType': {
        'module': 'tosca_core.validate.capability_type',
        'class': 'ToscaCapabilityTypeValidator'
        },
    'ToscaDataType': {
        'module': 'tosca_core.validate.data_type',
        'class': 'ToscaDataTypeValidator'
        },
    'ToscaGroupType': {
        'module': 'tosca_core.validate.group_type',
        'class': 'ToscaGroupTypeValidator'
        },
    'ToscaPolicyType': {
        'module': 'tosca_core.validate.policy_type',
        'class': 'ToscaPolicyTypeValidator'
        },
    'ToscaInterfaceType': {
        'module': 'tosca_core.validate.interface_type',
        'class': 'ToscaInterfaceTypeValidator'
        },
    'ToscaNodeType': {
        'module': 'tosca_core.validate.node_type',
        'class': 'ToscaNodeTypeValidator'
        },
    'ToscaRelationshipType': {
        'module': 'tosca_core.validate.relationship_type',
        'class': 'ToscaRelationshipTypeValidator'
        },
    'ToscaCapabilityDeclaration': {
        'module': 'tosca_core.validate.capability_declaration',
        'class': 'ToscaCapabilityDeclarationValidator'
        },
    'ToscaOperationDeclaration': {
        'module': 'tosca_core.validate.operation_declaration',
        'class': 'ToscaOperationDeclarationValidator'
        },
    'ToscaPropertyDeclaration': {
        'module': 'tosca_core.validate.property_declaration',
        'class': 'ToscaPropertyDeclarationValidator'
        },
    'ToscaRelationshipDeclaration': {
        'module': 'tosca_core.validate.relationship_declaration',
        'class': 'ToscaRelationshipDeclarationValidator'
        },
    'ToscaNodeDeclaration': {
        'module': 'tosca_core.validate.node_declaration',
        'class': 'ToscaNodeDeclarationValidator'
        },
    'ToscaArtifact': {
        'module': 'tosca_core.validate.artifact',
        'class': 'ToscaArtifactValidator'
        },
    'ToscaCapabilityTemplate': {
        'module': 'tosca_core.validate.capability_template',
        'class': 'ToscaCapabilityTemplateValidator'
        },
    'ToscaManagedTemplate': {
        'module': 'tosca_core.validate.managed_template',
        'class': 'ToscaManagedTemplateValidator'
        },
    'ToscaNodeTemplate': {
        'module': 'tosca_core.validate.node_template',
        'class': 'ToscaNodeTemplateValidator'
        },
    'ToscaRelationshipTemplate': {
        'module': 'tosca_core.validate.relationship_template',
        'class': 'ToscaRelationshipTemplateValidator'
        },
    'ToscaInterfaceTemplate': {
        'module': 'tosca_core.validate.interface_template',
        'class': 'ToscaInterfaceTemplateValidator'
        },
    'ToscaInterfaceDeclaration': {
        'module': 'tosca_core.validate.interface_declaration',
        'class': 'ToscaInterfaceDeclarationValidator'
        },
    'ToscaGroup': {
        'module': 'tosca_core.validate.group',
        'class': 'ToscaGroupValidator'
        },
    'ToscaMetadata': {
        'module': 'tosca_core.validate.meta_data',
        'class': 'ToscaMetadataValidator'
        },
    'ToscaOperationTemplate': {
        'module': 'tosca_core.validate.operation',
        'class': 'ToscaOperationValidator'
        },
    'ToscaOperationImplementation': {
        'module': 'tosca_core.validate.operation_implementation',
        'class': 'ToscaOperationImplementationValidator'
        },
    'ToscaPolicy': {
        'module': 'tosca_core.validate.policy',
        'class': 'ToscaPolicyValidator'
        },
    'ToscaFunction': {
        'module': 'tosca_core.validate.function_declaration',
        'class': 'ToscaFunctionValidator'
        },
    'ToscaRepository': {
        'module': 'tosca_core.validate.repository',
        'class': 'ToscaRepositoryValidator'
        },
    'ToscaWorkflowTemplate': {
        'module': 'tosca_core.validate.workflow_template',
        'class': 'ToscaWorkflowTemplateValidator'
        },
    'ToscaFilter': {
        'module': 'tosca_core.validate.filter',
        'class': 'ToscaFilterValidator'
        },
    'ToscaCondition': {
        'module': 'tosca_core.validate.condition',
        'class': 'ToscaConditionValidator'
        },
    'ToscaServiceTemplate': {
        'module': 'tosca_core.validate.service_template',
        'class': 'ToscaServiceTemplateValidator'
        },
    'ToscaSubstitutionMappings': {
        'module': 'tosca_core.validate.substitution_mappings',
        'class': 'ToscaSubstitutionMappingsValidator'
        },
    }


def get_validator(validator_name: str) -> "ToscaValidator":
    """return a validator by name

    Args:
      validator_name(str): name of the validator to find

    Returns:
      instance of the appropriate ToscaValidator subclass

    Raises:
      KeyError: when no validator with the given name exists.
    """

    # Find the validator descriptor by name
    descriptor = tosca_validator_descriptors[validator_name]

    # Return validator instance if it's already been created
    try:
        validator = descriptor['instance']
    except KeyError:
        # Load module for the validator
        validator_module = importlib.import_module(descriptor['module'])

        # Create the validator instance
        validator = getattr(validator_module, descriptor['class'])()
        descriptor['instance'] = validator

    # Validator now exists
    return validator


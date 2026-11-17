"""
Module defining the contract an expression context must satisfy
"""
from __future__ import annotations

__author__ = "Chris Lauwers"
__copyright__ = "Copyright (c) 2017-2026, Ubicity Corp."
__email__ = "info@ubicity.com"

# Typing support
from typing import Any

# Logging support
import logging
logger: logging.Logger = logging.getLogger(__name__)

# Exception support
import tosca_core.models.exceptions as te


# NOT an abc.ABC, and it cannot become one. ABCMeta conflicts with the
# SQLAlchemy declarative metaclass, and giving this class a combined metaclass
# makes Flask-SQLAlchemy try to build it as a model ("no attribute '__fsa__'").
# Virtual registration would avoid both but would not inherit the refusals
# below, which are the reason this class exists. A plain mixin is the only form
# that works for a context that is also a db.Model.
class ToscaContextMixin(object):
    """Fallback members for an expression context.

    Mixed in LAST so it supplies only what a class does not define itself; put
    first it would shadow mapped attributes such as ``profile``.

    Every TOSCA expression is evaluated against a context, and a context
    answers two unrelated kinds of question:

      - **the declaring document** -- ``profile`` (which namespaces are in
        scope), ``tosca_version`` (which grammar the expression is written
        in), and ``service`` (whose inputs and named nodes it may reach);
      - **the referenced entity** -- ``SELF``, ``SOURCE`` and ``TARGET``.

    Three of the six come from the document and three from the entity, and a
    context that supplies the entity but not the document looks healthy until
    an expression uses a profile function, a service input or a named node --
    none of which a builtin needs.

    **The members are deliberately not uniform.** A type has no document; a
    declaration has a document but never a service, because it belongs to the
    type system and the same declaration is shared by every service using that
    type. Those are contract statements rather than gaps, which is why this
    class supplies refusals rather than requiring implementations: a context
    that cannot answer says so, with the reason, instead of failing on an
    attribute lookup.
    """

    ################################################################################
    # The declaring document
    ################################################################################

    @property
    def profile(self) -> Any:
        raise te.ModelCorruptionError(
            "{0} cannot resolve a function namespace: it has no declaring "
            "document".format(type(self).__name__))

    @property
    def tosca_version(self) -> str:
        raise te.ModelCorruptionError(
            "{0} cannot resolve a TOSCA grammar version: it has no declaring "
            "document".format(type(self).__name__))

    @property
    def service(self) -> Any:
        raise te.ModelCorruptionError(
            "{0} has no service. An expression declared by a type or a "
            "declaration is part of that type's contract and must hold for "
            "every use of it in every service, so it cannot read a service "
            "input or name a node.".format(type(self).__name__))

    ################################################################################
    # The referenced entity
    ################################################################################

    def SELF(self) -> Any:
        raise te.ModelCorruptionError(
            "{0} cannot resolve SELF".format(type(self).__name__))

    def SOURCE(self) -> Any:
        raise te.ModelCorruptionError(
            "{0} cannot resolve SOURCE: it refers to relationships "
            "only".format(type(self).__name__))

    def TARGET(self) -> Any:
        raise te.ModelCorruptionError(
            "{0} cannot resolve TARGET: it refers to relationships "
            "only".format(type(self).__name__))

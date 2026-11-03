"""Hand-written refinements of generated item models.

Generated models (``models/ddb``) describe the *migrated* data exactly. When a work package implements a store and
needs a stricter or richer contract (a ``Literal`` status backed by a CHECK constraint, a required attribute the
migration never wrote, a computed property), subclass the generated model here with the same ``ctx``/``item_type``
keywords: the later registration replaces the generated one in ``ITEM_MODELS``. Never edit the generated files.

    class LearnerProfile(_Generated, ctx="learner", item_type="PROFILE"):
        status: Literal["ACTIVE", "DISABLED", "ERASING"]
"""

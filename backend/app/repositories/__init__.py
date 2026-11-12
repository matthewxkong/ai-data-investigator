"""Internal metadata access; public dataset APIs arrive in later milestones."""


class MetadataNotFoundError(LookupError):
    """A record is absent or belongs to a different session."""

"""Generic decorators."""


def allow_tags(f):
    """Allow tags for a ModelAdmin field."""

    f.allow_tags = True
    return f


def short_description(label):
    """Add short_description attribute to a function."""

    def wrap(f):
        f.short_description = label
        return f

    return wrap

import re

from django.core.exceptions import ValidationError


def keyword_list(value):
    """Validate token list."""

    tokens = filter(bool, [token.strip() for token in value.split(',')])

    if not tokens:
        raise ValidationError('Please specify at least one keyword.')

    # Only alphanumeric characters are allowed.
    regex = re.compile(r'^[\s\w_-]+$')
    invalid_tokens = filter(lambda token: not regex.match(token), tokens)

    if invalid_tokens:
        raise ValidationError(
            'Only alphanumeric characters, spaces, underscores '
            'and dashes are allowed. There are invalid '
            'characters here: %s' % ', '.join(invalid_tokens)
        )

    return value

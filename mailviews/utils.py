import textwrap
from collections import namedtuple

from django.utils.safestring import mark_safe


Docstring = namedtuple('Docstring', ('summary', 'body'))


def split_docstring(value):
    """
    Splits the docstring of the given value into it's summary and body.

    :returns: a 2-tuple of the format ``(summary, body)``
    """
    docstring = getattr(value, '__doc__', '') or ''
    docstring = textwrap.dedent(docstring)
    if not docstring:
        return None

    pieces = docstring.strip().split('\n\n', 1)
    try:
        body = pieces[1]
    except IndexError:
        body = None

    return Docstring(pieces[0], body)


def unimplemented(*args, **kwargs):
    raise NotImplementedError


def unescape(context):
    """
    Accepts a context object, returning a new context with autoescape off.

    Useful for rendering plain-text templates without having to wrap the entire
    template in an `{% autoescape off %}` tag.
    """
    for key in context:
        if type(context[key]) in [str, unicode]:
            context[key] = mark_safe(context[key])
    return context

import logging
import os
from base64 import b64encode
from collections import namedtuple
from email.header import decode_header

try:
    from django.conf.urls import patterns, include, url
except ImportError:
    # Django <1.4 compat
    from django.conf.urls.defaults import patterns, include, url

from django.apps import apps as app_registry
from django.core.urlresolvers import reverse
from django.http import Http404
from django.shortcuts import render, redirect
from django.utils.datastructures import SortedDict
from django.utils.importlib import import_module
from django.utils.module_loading import module_has_submodule


from mailviews.helpers import should_use_staticfiles
from mailviews.utils import split_docstring, unimplemented


logger = logging.getLogger(__name__)


URL_NAMESPACE = 'mailviews'

ModulePreviews = namedtuple('ModulePreviews', ('module', 'previews'))


def maybe_decode_header(header):
    """
    Decodes an encoded 7-bit ASCII header value into it's actual value.
    """
    value, encoding = decode_header(header)[0]
    if encoding:
        return value.decode(encoding)
    else:
        return value


class PreviewSite(object):
    def __init__(self):
        self.__previews = {}

    def __iter__(self):
        """
        Returns an iterator of :class:`ModulePreviews` tuples, sorted by module nae.
        """
        for module in sorted(self.__previews.keys()):
            previews = ModulePreviews(module, sorted(self.__previews[module].values(), key=str))
            yield previews

    def register(self, cls):
        """
        Adds a preview to the index.
        """
        preview = cls(site=self)
        logger.debug('Registering %r with %r', preview, self)
        index = self.__previews.setdefault(preview.module, {})
        index[cls.__name__] = preview

    @property
    def urls(self):
        urlpatterns = patterns('',
            url(regex=r'^$',
                view=self.list_view,
                name='list'),
            url(regex=r'^(?P<module>.+)/(?P<preview>.+)/send-test/$',
                view=self.send_test_view,
                name='send_test'),
            url(regex=r'^(?P<module>.+)/(?P<preview>.+)/$',
                view=self.detail_view,
                name='detail'),
        )

        if not should_use_staticfiles():
            urlpatterns += patterns('',
                url(regex=r'^static/(?P<path>.*)$',
                    view='django.views.static.serve',
                    kwargs={
                        'document_root': os.path.join(os.path.dirname(__file__), 'static'),
                    },
                    name='static'),
                )

        return include(urlpatterns, namespace=URL_NAMESPACE)

    def list_view(self, request):
        """
        Returns a list view response containing all of the registered previews.
        """
        return render(request, 'mailviews/previews/list.html', {
            'site': self,
        })

    def detail_view(self, request, module, preview):
        """
        Looks up a preview in the index, returning a detail view response.
        """
        try:
            preview = self.__previews[module][preview]
        except KeyError:
            raise Http404  # The provided module/preview does not exist in the index.
        return preview.detail_view(request)

    def send_test_view(self, request, module, preview):
        """
        Looks up a preview in the index, returning a view response that
        sends sends a test email before redirecting back to the detail view.
        """
        try:
            preview = self.__previews[module][preview]
        except KeyError:
            raise Http404  # The provided module/preview does not exist in the index.
        return preview.send_test_view(request)


class Preview(object):
    #: The message view class that will be instantiated to render the preview
    #: message. This must be defined by subclasses.
    message_view = property(unimplemented)

    #: The subset of headers to show in the preview panel.
    headers = ('Subject', 'From', 'To')

    #: The title of this email message to use in the previewer. If not provided,
    #: this will default to the name of the message view class.
    verbose_name = None

    #: A form class that will be used to customize the instantiation behavior
    # of the message view class.
    form_class = None

    #: The template that will be rendered for this preview.
    template_name = 'mailviews/previews/detail.html'

    def __init__(self, site):
        self.site = site

    def __unicode__(self):
        return self.verbose_name or self.message_view.__name__

    @property
    def module(self):
        return '%s' % self.message_view.__module__

    @property
    def description(self):
        """
        A longer description of this preview that is used in the preview index.

        If not provided, this defaults to the first paragraph of the underlying
        message view class' docstring.
        """
        return getattr(split_docstring(self.message_view), 'summary', None)

    @property
    def url(self):
        """
        The URL to access this preview.
        """
        return reverse('%s:detail' % URL_NAMESPACE, kwargs={
            'module': self.module,
            'preview': type(self).__name__,
        })

    @property
    def send_test_url(self):
        """
        The URL to trigger sending of a test email.
        """
        return reverse('%s:send_test' % URL_NAMESPACE, kwargs={
            'module': self.module,
            'preview': type(self).__name__,
        })

    @staticmethod
    def send_test_email(email_message, recipient):
        """
        Send an email for a rendered email message after overriding
        the recipient(s) since this is for testing.
        """
        email_message.cc = []
        email_message.bcc = []
        email_message.to = [recipient]
        email_message.send()

    def get_message_view(self, request, **kwargs):
        return self.message_view(**kwargs)

    def detail_view(self, request):
        """
        Renders the message view to a response.
        """
        context = {
            'preview': self,
        }

        kwargs = {}
        if self.form_class:
            if request.GET:
                form = self.form_class(data=request.GET)
            else:
                form = self.form_class()

            context['form'] = form
            if not form.is_bound or not form.is_valid():
                return render(request, 'mailviews/previews/detail.html', context)

            kwargs.update(form.get_message_view_kwargs())

        message_view = self.get_message_view(request, **kwargs)

        message = message_view.render_to_message()
        raw = message.message()
        headers = SortedDict((header, maybe_decode_header(raw[header])) for header in self.headers)

        context.update({
            'message': message,
            'subject': message.subject,
            'body': message.body,
            'headers': headers,
            'raw': raw.as_string(),
        })

        alternatives = getattr(message, 'alternatives', [])
        try:
            html = next(alternative[0] for alternative in alternatives
                if alternative[1] == 'text/html')
            context.update({
                'html': html,
                'escaped_html': b64encode(html.encode('utf-8')),
            })
        except StopIteration:
            pass

        return render(request, self.template_name, context)

    def send_test_view(self, request):
        """
        Sends an actual email (as a test) for the preview's message view
        """
        test_recipient = request.GET.get('testRecipient')

        # Remove testRecipient GET var before reconstructing detail URL
        try:
            get_vars_copy = request.GET.copy()
            del get_vars_copy['testRecipient']
        except KeyError:
            pass

        detail_view_redirect_url = '{0}?{1}'.format(self.url, get_vars_copy.urlencode())

        # No test recipient --> Back to detail view
        if not test_recipient:
            return redirect(detail_view_redirect_url)

        kwargs = {}
        if self.form_class:
            if request.GET:
                form = self.form_class(data=request.GET)
            else:
                form = self.form_class()

            # Shouldn't happen, but just incase, send back to detail view
            if not form.is_bound or not form.is_valid():
                return redirect(detail_view_redirect_url)

            kwargs.update(form.get_message_view_kwargs())

        message_view = self.get_message_view(request, **kwargs)
        message = message_view.render_to_message()

        self.send_test_email(message, test_recipient)

        return redirect(detail_view_redirect_url)


def autodiscover():
    """
    Imports all available previews classes.
    """
    for app_config in app_registry.get_app_configs():
        if module_has_submodule(app_config.module, 'emails'):
            emails = import_module('%s.emails' % app_config.name)
            try:
                import_module('%s.emails.previews' % app_config.name)
            except ImportError:
                # Only raise the exception if this module contains previews and
                # there was a problem importing them. (An emails module that
                # does not contain previews is not an error.)
                if module_has_submodule(emails, 'previews'):
                    raise

#: The default preview site.
site = PreviewSite()

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        INSTALLED_APPS=(
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'mailviews',
            'mailviews.tests',
        ),
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            },
        },
        ROOT_URLCONF='mailviews.tests.urls',
        STATIC_URL='/static/',
        LOGGING={
            'version': 1,
            'disable_existing_loggers': False,
            'handlers': {
                'console': {
                    'level': 'DEBUG',
                    'class': 'logging.StreamHandler',
                },
            },
            'loggers': {
                '': {
                    'handler': ['console'],
                    'level': 'DEBUG',
                },
            },
        },
    )

    if hasattr(django, 'setup'):
        django.setup()


from mailviews.tests.tests import *  # NOQA

if __name__ == '__main__':
    from mailviews.tests.__main__ import __main__

<<<<<<< HEAD
    django.setup()

    runner = get_runner(settings)()
    failures = runner.run_tests(('mailviews',))
    sys.exit(failures)
=======
    __main__()
>>>>>>> e3f4adbea04a134e485624077c0194d48f1b646f

from django.conf.urls import patterns, url

from mailviews.previews import autodiscover, site


autodiscover()

urlpatterns = patterns('',
    url(regex=r'', view=site.urls),
)

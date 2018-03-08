import logging

from raven.base import Client
from raven.conf import setup_logging
from raven.handlers.logging import SentryHandler
from raven.middleware import Sentry

logger = logging.getLogger('raven')


class SentryMiddleware(Sentry):
    def __init__(self, application, client=None):
        super(SentryMiddleware, self).__init__(application, client)

    @classmethod
    def factory(cls, global_config, **local_config):
        def _factory(app):
            try:
                client = Client(**local_config)
                handler = SentryHandler(client, **local_config)
                setup_logging(handler)
            except Exception as e:
                logger.error(e)
                client = None
            return cls(app, client)

        return _factory

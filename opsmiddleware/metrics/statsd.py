from datadog.dogstatsd import DogStatsd

import os
import time
import re
import urlparse
from os.path import splitext

ID_REGEX = re.compile(r'/[0-9a-fA-F-]+/')


class StatsdMiddleware(object):
    def __init__(self, app, statsd_host='localhost', statsd_port='8125',
                 statsd_prefix='openstack'):
        self.app = app
        self.client = DogStatsd(
            host=os.getenv('STATSD_HOST', statsd_host),
            port=int(os.getenv('STATSD_PORT', statsd_port)),
            namespace=os.getenv('STATSD_PREFIX', statsd_prefix)
        )

    @classmethod
    def factory(cls, global_config, **local_config):
        def _factory(app):
            return cls(app, **local_config)

        return _factory

    def process_response(self, start, environ, response_wrapper,
                         exception=None):
        self.client.increment('responses_total')

        status = response_wrapper.get('status')
        if status:
            status_code = status.split()[0]
        else:
            status_code = 'none'

        method = environ['REQUEST_METHOD']

        # cleanse request path
        path = urlparse.urlparse(environ['SCRIPT_NAME'] +
                                 environ['PATH_INFO']).path
        # strip extensions
        path = splitext(path)[0]

        # replace identifiers with constant
        path = ID_REGEX.sub('/id/', path + '/')

        parts = path.rstrip('\/').split('/')
        if exception:
            parts.append(exception.__class__.__name__)
        api = '/'.join(parts)

        self.client.timing('latency_by_api',
                           time.time() - start,
                           tags=[
                               'method:%s' % method,
                               'api:%s' % api
                           ])

        self.client.increment('responses_by_api',
                              tags=[
                                  'method:%s' % method,
                                  'api:%s' % api,
                                  'status:%s' % status_code
                              ])

    def __call__(self, environ, start_response):
        response_interception = {}

        def start_response_wrapper(status, response_headers,
                                   exc_info=None):
            response_interception.update(status=status,
                                         response_headers=response_headers,
                                         exc_info=exc_info)
            return start_response(status, response_headers, exc_info)

        start = time.time()
        try:
            self.client.open_buffer()
            self.client.increment('requests_total')

            response = self.app(environ, start_response_wrapper)
            try:
                for event in response:
                    yield event
            finally:
                if hasattr(response, 'close'):
                    response.close()

            self.process_response(start, environ, response_interception)
        except Exception as exception:
            self.process_response(start, environ, response_interception,
                                  exception)
            raise
        finally:
            self.client.close_buffer()

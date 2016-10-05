from datadog.dogstatsd import DogStatsd

import os
import time
import re
import urlparse
from abc import ABCMeta, abstractmethod
from os.path import splitext


class StatsdMiddleware(object):
    def __init__(self, app, statsd_host='localhost', statsd_port='8125',
                 statsd_prefix='openstack', statsd_replace='id'):
        self.app = app
        self._get_replace_strategy(os.getenv('STATSD_REPLACE', statsd_replace).lower())
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

        # replace parts of the path with constants based on strategy
        path = self.replace_strategy.replace(path)

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

    def _get_replace_strategy(self, strategy):
        if strategy == 'swift':
            self.replace_strategy = _ReplaceStrategySwift()
        else:
            self.replace_strategy = _ReplaceStrategyId()


class _ReplaceStrategy(metaclass=ABCMeta):
    @abstractmethod
    def replace(self, path):
        pass


class _ReplaceStrategyId(_ReplaceStrategy):
    def __init__(self):
        self._regex = re.compile(r'/[0-9a-fA-F-]+/')

    def replace(self, path):
        # replace identifiers with constant
        return self._regex.sub('/id/', path + '/')


class _ReplaceStrategySwift(_ReplaceStrategy):
    def __init__(self):
        self._regex = re.compile(r'(\S+AUTH_)([p\-]?[0-9a-fA-F-]+/?)([^ /\t\n\r\f\v]+/?)?(\S*)?')

    def replace(self, path):
        # Transform Swift path from
        # /v1/AUTH_0123456789/container-name/pseudo-folder/object-name
        # to constants
        # /v1/AUTH_account/container/object
        m = self._regex.match(path)
        if m:
            # Replace account id with constant
            path = m.group(1) + 'account'
            if m.group(3) and m.group(3) != '':
                # Replace container name with constant
                path += '/container'
            if m.group(4) and m.group(4) != '':
                # Replace object name with constant
                path += '/object'
            path += '/'

        return path

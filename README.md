# Openstack Operations Middleware

Provides general purpose operations middleware for openstack wsgi based applications.

This project is still under heavy development and can change anytime.

It currently supports
 
- generation of statsd metrics (with datadog tag extensions) to be used with the [prometheus statsd exporter](https://github.com/prometheus/statsd_exporter)
- a [sentry](http://getsentry.com) exception reporter

Planned extensions:

- rate limiter
 
 
## Installation
 
Install the python packages into your (virtual) environment
 
    pip install git+https://github.com/sapcc/openstack-ops-middleware.git 
     

### Statsd Middleware

To enable the statsd metrics middleware, you'll need to add the following
snippets to the applications **paste.ini**:

    [filter:statsd]
    use = egg:ops-middleware#statsd

Once the filter has been declared, the middleware can be inserted into the 
application pipeline(s) as desired.

Example from keystone:
 
    [pipeline:public_api]
    pipeline = cors sizelimit url_normalize request_id statsd build_auth_context token_auth json_body ec2_extension public_service
 
    [pipeline:admin_api]
    pipeline = cors sizelimit url_normalize request_id statsd build_auth_context token_auth json_body ec2_extension s3_extension admin_service
     
    [pipeline:api_v3]
    pipeline = cors sizelimit url_normalize request_id statsd build_auth_context token_auth json_body ec2_extension_v3 s3_extension service_v3

The middleware needs some configuration to define how the [prometheus statsd exporter](https://github.com/prometheus/statsd_exporter) can be reached,
which can be provided either via environment variables:

    STATSD_HOST     the statsd hostname
    STATSD_PORT     the statsd portnumber
    STATSD_PREFIX   a optional prefix that identifies the component and is used for the metrics name generation
    
or by setting the values in the paste.ini:

    [filter:statsd]
    use = egg:ops-middleware#statsd
    statsd_host=localhost
    statsd_port=9102
    statsd_prefix=openstack

The middleware generates the following metrics:

    <prefix>_requests_total_counter
    <prefix>_reponses_total_counter
    <prefix>_reponses_by_api_counter sliced by api, method and status
    <prefix>_latency_by_api_timer sliced by api and method

#### Replacement Strategies

As the request path might contain dynamic parts like UUIDs, there is the option to replace them with constants.
The following replacements are supported:
* id: (hex or uuid) identifiers replaced with 'id'
* swift: replacing swift account, container and object names. The variants in a Swift path like `/v1/AUTH_01234556789/container-name/pseudo-folder/object-name` are replaced by `/v1/AUTH_account/container/object`

The strategies can be stacked and will be executed in the specified order:

    [filter:statsd]
    statsd_replace=id, swift

Per default IDs in the path will be substituted.

### Sentry Middleware

The sentry middleware forwards any exceptions that bubble up to the wsgi middleware layer to sentry.
Since in many cases exceptions do not make it to the middleware layer, it also adds a logging handler that forwards log entries at a desired logging level to sentry.

To enable the sentry middleware, you'll need to add the following snippet to the applications **paste.ini**:

    [filter:sentry]
    use = egg:ops-middleware#sentry

The sentry middleware needs some [configuration](https://docs.getsentry.com/hosted/clients/python/#configuring-the-client) so it knows how to contact the sentry backend.

This configuration (primarily the DSN) can either be provided via a SENTRY_DSN 
environment variable or configuration embeded into the paste.ini filter section:

    [filter:sentry]
    use = egg:ops-middleware#sentry
    dsn = https://e18252e83cbf4b35833af33823a88edd:b1cd72ecdab54f7bb0efede8c4560d3e@sentry.your.domain.com/5 

The logging-level that should be intercepted can be specified with **level**:
 
    [filter:sentry]
    use = egg:ops-middleware#sentry
    dsn = https://e18252e83cbf4b35833af33823a88edd:b1cd72ecdab54f7bb0efede8c4560d3e@sentry.your.domain.com/5
    level = ERROR
 
Once the filter has been declared and configured, the middleware can be inserted into the application pipeline(s).

Example from keystone:
 
    [pipeline:public_api]
    pipeline = cors sizelimit url_normalize request_id statsd build_auth_context token_auth json_body ec2_extension sentry public_service
 
    [pipeline:admin_api]
    pipeline = cors sizelimit url_normalize request_id statsd build_auth_context token_auth json_body ec2_extension s3_extension sentry admin_service
     
    [pipeline:api_v3]
    pipeline = cors sizelimit url_normalize request_id statsd build_auth_context token_auth json_body ec2_extension_v3 s3_extension sentry service_v3

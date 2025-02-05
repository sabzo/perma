import json
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse

from perma.models import LinkUser


class SentinelException(Exception):
    pass


class PermaTestCase(TestCase):

    # def tearDown(self):
    #     # wipe cache -- see https://niwinz.github.io/django-redis/latest/#_testing_with_django_redis
    #     from django_redis import get_redis_connection
    #     get_redis_connection("default").flushall()

    #     return super(PermaTestCase, self).tearDown()

    def log_in_user(self, user, password='pass'):
        self.client.logout()
        if hasattr(user, 'email'):
            self.logged_in_user = user
            user = user.email
        else:
            self.logged_in_user = LinkUser.objects.get(email=user)
        return self.client.post(reverse('user_management_limited_login'), {'username': user, 'password': password}, secure=True)

    def do_request(self,
                   view_name,
                   method='get',
                   reverse_args=[],
                   reverse_kwargs={},
                   query_params={},
                   request_args=[],
                   request_kwargs={},
                   require_status_code=200,
                   user=None):
        """
            Given view name, get url and fetch url contents.
        """
        if user:
            self.log_in_user(user)
        url = reverse(view_name, *reverse_args, **reverse_kwargs)
        if query_params:
            url += '?' + urlencode(query_params)
        resp = getattr(self.client, method.lower())(url, *request_args, secure=True, **request_kwargs)
        if require_status_code:
            self.assertEqual(resp.status_code, require_status_code)
        return resp

    def get(self, view_name, *args, **kwargs):
        """
            Convenience method to call do_request with method='get'
        """
        return self.do_request(view_name, 'get', *args, **kwargs)

    def post(self, view_name, data={}, *args, **kwargs):
        """
            Convenience method to call do_request with method='post'
        """
        # set defaults for kwargs['request_kwargs']
        kwargs['request_kwargs'] = dict({
            'data': data,
        }, **kwargs.get('request_kwargs', {}))
        return self.do_request(view_name, 'post', *args, **kwargs)

    def post_json(self, view_name, data={}, *args, **kwargs):
        """
            Convenience method to call post() with necessary headers for JSON requests.
        """
        # set defaults for kwargs['request_kwargs']
        kwargs['request_kwargs'] = dict({
            'content_type': 'application/x-www-form-urlencoded',
            'HTTP_X_REQUESTED_WITH':'XMLHttpRequest'
        }, **kwargs.get('request_kwargs', {}))
        return self.post(view_name, json.dumps(data), *args, **kwargs)


    def submit_form(self,
                    view_name,
                    data={},
                    success_url=None,
                    success_query=None,
                    form_keys=['form'],  # name of form objects in RequestContext returned with response
                    error_keys=[],  # keys that must appear in form error list
                    *args, **kwargs):
        """
            Post to a view.
            success_url = url form should forward to after success
            success_query = query that should return one object if form worked
        """

        kwargs['require_status_code'] = None
        resp = self.post(view_name, data, *args, **kwargs)

        def form_errors():
            errors = {}
            try:
                for form in form_keys:
                    errors.update(resp.context[form]._errors)
            except (TypeError, KeyError):
                pass
            return errors

        if success_url:
            self.assertEqual(resp.status_code, 302, "Form failed to forward to success url. Status: %s. Content: %s. Errors: %s." % (resp.status_code, resp.content, form_errors()))
            self.assertTrue(resp['Location'].endswith(success_url), "Form failed to forward to %s. Instead forwarded to: %s." % (success_url, resp['Location']))

        if success_query:
            self.assertEqual(success_query.count(), 1)

        if error_keys:
            keys = set(form_errors().keys())
            self.assertTrue(set(error_keys) == keys, "Error keys don't match expectations. Expected: %s. Found: %s" % (set(error_keys), keys))

        return resp



# from https://github.com/jamesls/fakeredis/issues/234
from django_redis.pool import ConnectionFactory
class FakeConnectionFactory(ConnectionFactory):
    def get_connection(self, params):
        return self.redis_client_cls(**self.redis_client_cls_kwargs)

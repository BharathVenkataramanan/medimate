
import io
import json
import unittest
from email.message import Message
from unittest.mock import patch
import server


class Synthetic(server.Handler):
    def __init__(self, path, body=None, *, host=None, origin=None, site=None, custom=None, ref=None):
        self.path=path
        self.client_address=('127.0.0.1',12345)
        self.headers=Message()
        self.headers['Host']=host or f'127.0.0.1:{server.PORT}'
        if origin is not None:self.headers['Origin']=origin
        if site is not None:self.headers['Sec-Fetch-Site']=site
        if custom is not None:self.headers['X-MediMate-Request']=custom
        if ref is not None:self.headers['Referer']=ref
        self.headers['Content-Type']='application/json'
        raw=json.dumps(body or {'medicines':['Viagra','nitroglycerin'],'resolve_online':False}).encode()
        self.headers['Content-Length']=str(len(raw))
        self.rfile=io.BytesIO(raw);self.wfile=io.BytesIO();self.code=None
    def send_response(self, status, message=None):self.code=status
    def send_header(self, name, value):pass
    def end_headers(self):pass
    def response(self):return json.loads(self.wfile.getvalue())


class SecurityCheckpoint(unittest.TestCase):
    def test_loopback_hosts_only(self):
        self.assertTrue(server.is_allowed_host(f'127.0.0.1:{server.PORT}'))
        self.assertTrue(server.is_allowed_host(f'localhost:{server.PORT}'))
        for host in ('evil.example',f'evil.example:{server.PORT}',f'localhost.evil.example:{server.PORT}', 'localhost',f'0.0.0.0:{server.PORT}'):
            with self.subTest(host=host):self.assertFalse(server.is_allowed_host(host))

    def test_rebinding_host_get_refused_before_looking_at_data(self):
        h=Synthetic('/api/reminders/status',host=f'evil.example:{server.PORT}')
        with patch.object(server,'reminder_status') as status:
            h.do_GET()
        self.assertEqual(h.code,403);status.assert_not_called()

    def test_rebinding_post_and_cross_site_post_refused(self):
        examples=[
            dict(host=f'evil.example:{server.PORT}',origin=f'http://evil.example:{server.PORT}',custom='1'),
            dict(origin='https://evil.example',custom='1'),
            dict(origin='null',custom='1'),
            dict(origin=f'http://127.0.0.1:{server.PORT}',site='cross-site',custom='1'),
            dict(ref='https://evil.example/fake',custom='1'),
            dict(),
        ]
        with patch.object(server,'check_pairs') as lookup:
            for fields in examples:
                with self.subTest(fields=fields):
                    h=Synthetic('/api/interactions', **fields);h.do_POST()
                    self.assertEqual(h.code,403)
            lookup.assert_not_called()

    def test_local_requests_still_work(self):
        for host in (f'localhost:{server.PORT}',f'127.0.0.1:{server.PORT}'):
            target='http://'+host
            for source in (dict(origin=target),dict(ref=target+'/index.html'),dict(custom='1'),dict(origin=target,site='same-origin')):
                with self.subTest(host=host,source=source):
                    h=Synthetic('/api/interactions',host=host,**source)
                    with patch.object(server,'check_pairs',return_value={'status':'ready','unrecognized':[]}) as lookup:
                        h.do_POST()
                    self.assertEqual(h.code,200)
                    lookup.assert_called_once()

    def test_static_and_api_headers(self):
        h=Synthetic('/api/health',origin=f'http://127.0.0.1:{server.PORT}')
        with patch.object(server,'rxnorm_catalog_ready',return_value=False):
            h.do_GET()
        self.assertEqual(h.code,200)
        self.assertNotIn('OPENAI_API_KEY',str(h.response()))


if __name__=='__main__':unittest.main()

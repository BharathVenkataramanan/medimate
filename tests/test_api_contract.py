


from __future__ import annotations

import io
import json
import unittest
from email.message import Message
from unittest.mock import patch

import server


class SyntheticHandler(server.Handler):
    def __init__(self, endpoint: str, body: object, *, origin: str = 'http://127.0.0.1:8742'):
        self.path = endpoint
        self.client_address = ('127.0.0.1', 4242)
        self.headers = Message()
        self.headers['Host'] = '127.0.0.1:8742'
        self.headers['Content-Type'] = 'application/json'
        if origin:
            self.headers['Origin'] = origin
        raw = json.dumps(body).encode('utf-8')
        self.headers['Content-Length'] = str(len(raw))
        self.rfile = io.BytesIO(raw)
        self.wfile = io.BytesIO()
        self.status_code = None
        self.response_headers = {}

    def send_response(self, code: int, message=None) -> None:
        self.status_code = code

    def send_header(self, keyword: str, value: str) -> None:
        self.response_headers[keyword.lower()] = value

    def end_headers(self) -> None:
        pass

    def response(self) -> dict:
        return json.loads(self.wfile.getvalue().decode('utf-8'))


class APIContract73Tests(unittest.TestCase):
    @staticmethod
    def outcome() -> dict:
        return {
            'status': 'ready', 'alerts': [{
                'first': 'Viagra', 'second': 'nitroglycerin',
                'ingredient_a': 'Sildenafil', 'ingredient_b': 'Nitroglycerin',
                'level': 'Contraindicated', 'finding_type': 'documented_interaction',
            }],
            'uncertain': [], 'unrecognized': [],
            'safety_categories': {'documented_interactions': 1,
                                  'duplicate_ingredients': 0, 'needs_review': 0},
        }

    def test_local_interaction_endpoint_preserves_safety_result(self):
        handler = SyntheticHandler('/api/interactions', {
            'medicines': ['Viagra', 'nitroglycerin'],
            'rxnorm_ids': {'Viagra': '12345'}, 'resolve_online': False,
        })
        with (patch.object(server, 'check_pairs', return_value=self.outcome()) as check,
              patch.object(server, 'online_mappings_for_unknown') as online):
            handler.do_POST()
        self.assertEqual(handler.status_code, 200)
        self.assertEqual(handler.response()['alerts'][0]['level'], 'Contraindicated')
        self.assertEqual(handler.response()['rxnorm_resolved'], {})
        check.assert_called_once_with(['Viagra', 'nitroglycerin'], {},
                                      rxnorm_ids={'Viagra': '12345'})
        online.assert_not_called()

    def test_invalid_selected_ids_and_names_fail_closed(self):
        invalid = (
            {'medicines': ['Viagra', 'nitroglycerin'], 'rxnorm_ids': {'Viagra': 'some text'}},
            {'medicines': ['Viagra', 'nitroglycerin'], 'rxnorm_ids': {'Panadol': '123'}},
            {'medicines': ['Viagra', ''], 'rxnorm_ids': {}},
            {'medicines': 'Viagra', 'rxnorm_ids': {}},
            {'medicines': ['Viagra'], 'rxnorm_ids': {'Viagra': '1' * 13}},
        )
        with patch.object(server, 'check_pairs') as check:
            for body in invalid:
                with self.subTest(body=body):
                    handler = SyntheticHandler('/api/interactions', body)
                    handler.do_POST()
                    self.assertEqual(handler.status_code, 400)
                    self.assertEqual(handler.response()['error'], 'invalid_medicines')
        check.assert_not_called()

    def test_cross_site_post_is_rejected_before_any_lookup(self):
        handler = SyntheticHandler('/api/interactions',
                                   {'medicines': ['Viagra', 'nitroglycerin']},
                                   origin='https://unrelated.example')
        with patch.object(server, 'check_pairs') as check:
            handler.do_POST()
        self.assertEqual(handler.status_code, 403)
        self.assertEqual(handler.response()['error'], 'origin_denied')
        check.assert_not_called()

    def test_unrelated_question_is_rejected_before_any_ai_request(self):
        handler = SyntheticHandler('/api/chat',
                                   {'question': 'What is the capital of France?', 'language': 'en'})
        with patch.object(server, 'ask_openai') as ask:
            handler.do_POST()
        self.assertEqual(handler.status_code, 422)
        self.assertEqual(handler.response()['error'], 'outside_scope')
        ask.assert_not_called()

    def test_invalid_reminder_payload_does_not_write_storage(self):
        handler = SyntheticHandler('/api/reminders/sync', {'enabled': 'invalid'})
        with patch.object(server, 'write_snapshot', side_effect=ValueError('invalid')):
            handler.do_POST()
        self.assertEqual(handler.status_code, 400)
        self.assertEqual(handler.response()['error'], 'invalid_schedule')


if __name__ == '__main__':
    unittest.main()

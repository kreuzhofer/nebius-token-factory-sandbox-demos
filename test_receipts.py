"""Workflow checks use local source files and fake models; never live inference."""
import asyncio
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic_ai.messages import ModelResponse, ToolCallPart, TextPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.exceptions import ModelHTTPError
from pydantic import ValidationError
import pypdfium2 as pdfium

from receipt_demo.agents import CoordinatorAgent, ReportAgent
from receipt_demo.documents import prepare
from receipt_demo.models import Decisions, DuplicateGroup, Receipt
from receipt_demo.reconcile import reconcile
from receipts import inputs_for_run
from sandbox_jobs import SandboxJobs, retrieve_result

ROOT = Path(__file__).parent


def receipt(key, total='10.00', currency='EUR', **kwargs):
    return Receipt(receipt_id=key, source=key + '.png', total=total, currency=currency,
                   transaction_type=kwargs.pop('transaction_type', 'purchase'), **kwargs)


class AccountingTests(unittest.TestCase):
    def test_signed_refund_discount_included_tax_and_separate_currencies(self):
        report = reconcile([
            receipt('purchase', '22.60', taxes=[{'description': 'included VAT', 'amount': '2.60'}]),
            receipt('refund', '9.50', transaction_type='refund'),
            receipt('discount', '25.00', components_complete=True, comparable_components=['30', '-5']),
            receipt('usd', '14.75', 'USD'),
        ], Decisions())
        self.assertEqual(report.totals, {'EUR': '38.10', 'USD': '14.75'})

    def test_unknown_critical_fields_and_contradiction_are_excluded(self):
        report = reconcile([
            receipt('total', None), receipt('currency', currency=None),
            receipt('direction', transaction_type=None),
            receipt('contradiction', '25', components_complete=True, comparable_components=['12', '8']),
            receipt('secondary', merchant=None, issues=['Unknown merchant']),
        ], Decisions())
        self.assertEqual([e.outcome for e in report.entries], ['flagged'] * 4 + ['included'])
        self.assertEqual(report.totals, {'EUR': '10.00'})
        self.assertIsNone(report.entries[0].signed_amount)

    def test_confirmed_bytes_pixels_and_suspected_duplicates(self):
        records = [receipt('a', content_hash='a', pixel_hash='pixels'),
                   receipt('b', content_hash='a', pixel_hash='pixels'),
                   receipt('c', content_hash='c', pixel_hash='pixels'), receipt('d'), receipt('e')]
        report = reconcile(records, Decisions(duplicates=[DuplicateGroup(
            receipt_ids=['d', 'e'], confidence='suspected', reason='Matching transaction details; ID unreadable')]))
        self.assertEqual([e.outcome for e in report.entries], ['included', 'duplicate', 'duplicate', 'flagged', 'flagged'])
        self.assertEqual(report.totals, {'EUR': '10.00'})
        self.assertEqual(report.entries[2].duplicate_of, 'a')

    def test_suspected_duplicate_of_exact_copy_also_excludes_original(self):
        report = reconcile([receipt('a', content_hash='same'), receipt('copy', content_hash='same'), receipt('b')],
                           Decisions(duplicates=[DuplicateGroup(receipt_ids=['copy', 'b'], confidence='suspected', reason='Uncertain identity')]))
        self.assertEqual(report.totals, {})
        self.assertEqual([entry.outcome for entry in report.entries], ['flagged', 'duplicate', 'flagged'])

    def test_conflicting_model_duplicate_claim_cannot_confirm_a_match(self):
        report = reconcile([receipt('eur', merchant='Shop A'), receipt('usd', currency='USD', merchant='Shop B')],
                           Decisions(duplicates=[DuplicateGroup(receipt_ids=['eur', 'usd'], confidence='confirmed', reason='Suggested match')]))
        self.assertEqual([entry.outcome for entry in report.entries], ['flagged', 'flagged'])
        self.assertTrue(all(entry.duplicate_of is None for entry in report.entries))
        self.assertEqual(report.totals, {})

    def test_all_excluded_does_not_invent_currency_zero(self):
        report = reconcile([receipt('unknown', None), receipt('corrupt', error='Cannot render')], Decisions())
        self.assertEqual(report.totals, {})
        self.assertEqual(report.status, 'completed_with_flags')

    def test_bad_model_decisions_and_nonfinite_money_are_rejected(self):
        with self.assertRaises(ValueError):
            reconcile([receipt('a')], Decisions(duplicates=[DuplicateGroup(
                receipt_ids=['a', 'missing'], confidence='confirmed', reason='same')]))
        for value in ('NaN', 'Infinity', '1,23'):
            with self.assertRaises(ValidationError):
                receipt('a', value)


class DocumentTests(unittest.TestCase):
    def test_render_multipage_and_compare_reencoded_pixels(self):
        root = ROOT / 'fixtures/receipts/inputs'
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            pages, _, _ = prepare(root / 's01-en-multipage.pdf', temp / 'pdf')
            self.assertEqual(len(pages), 2)
            _, raw_a, pixels_a = prepare(root / 's08-control.png', temp / 'a')
            _, raw_b, pixels_b = prepare(root / 'v02-control-reencoded.png', temp / 'b')
            self.assertNotEqual(raw_a, raw_b)
            self.assertEqual(pixels_a, pixels_b)

    def test_fixture_selection_does_not_return_hidden_annotations(self):
        inputs = inputs_for_run([], 'minimal')
        self.assertEqual([item[0] for item in inputs], ['s08', 's04', 'v05'])
        self.assertTrue(all(len(item) == 3 for item in inputs))


def tool_model(messages, info):
    name = info.output_tools[0].name
    return ModelResponse(parts=[ToolCallPart(name, {})])


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_report_agent_tool_applies_semantic_monetary_flag(self):
        def flag_model(messages, info):
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
                'monetary_flags': [{'receipt_id': 'a', 'reason': 'Extracted amount is tender, not payable total'}],
            })])
        models = SimpleNamespace(agent=FunctionModel(flag_model))
        with tempfile.TemporaryDirectory() as directory:
            artifacts = await ReportAgent(models).run([receipt('a')], Path(directory))
            report = json.loads(artifacts['report.json'].read_text())
            self.assertEqual(report['entries'][0]['outcome'], 'flagged')
            self.assertEqual(report['totals'], {})

    async def test_shared_inference_auth_failure_fails_the_run(self):
        def broken_model(messages, info):
            raise ModelHTTPError(401, 'vision', {'secret': 'must not be logged'})
        models = SimpleNamespace(agent=FunctionModel(tool_model), vision=FunctionModel(broken_model))
        key, path, credit = inputs_for_run([], 'minimal')[0]
        sources = [{'receipt_id': key, 'source': path.name, 'path': str(path), 'credit': credit}]
        with tempfile.TemporaryDirectory() as directory:
            result = await CoordinatorAgent(models).run(sources, Path(directory) / 'work', Path(directory) / 'output')
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['artifacts'], {})
            self.assertNotIn('must not be logged', json.dumps(result))

    async def test_all_three_agents_produce_report_despite_corrupt_input(self):
        fields = {'merchant': 'Fixture Cafe', 'date_text': None, 'currency': 'USD',
                  'transaction_type': 'purchase', 'printed_total': '14.75', 'total': '14.75',
                  'pages': [{'number': 1, 'text': 'TOTAL $14.75', 'blocks': ['TOTAL $14.75']}],
                  'evidence': [{'field': 'total', 'page': 1, 'text': 'TOTAL $14.75'}]}
        models = SimpleNamespace(agent=FunctionModel(tool_model),
                                 vision=TestModel(custom_output_text=json.dumps(fields)))
        sources = [{'receipt_id': key, 'source': path.name, 'path': str(path), 'credit': credit}
                   for key, path, credit in inputs_for_run([], 'minimal') if key != 's04']
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            result = await CoordinatorAgent(models).run(sources, temp / 'work', temp / 'output')
            self.assertEqual(result['status'], 'completed_with_flags')
            self.assertEqual([e['outcome'] for e in result['entries']], ['included', 'error'])
            self.assertEqual(result['totals'], {'USD': '14.75'})
            for name, ref in result['artifacts'].items():
                self.assertEqual(hashlib.sha256((temp / 'output' / name).read_bytes()).hexdigest(), ref['sha256'])
            with pdfium.PdfDocument(temp / 'output/report.pdf') as pdf:
                self.assertGreaterEqual(len(pdf), 3)
                page = pdf[0]
                text = page.get_textpage()
                summary = text.get_text_range()
                text.close()
                page.close()
                self.assertIn('USD 14.75', summary)
                self.assertIn('v05-control-corrupt.pdf', summary)
                self.assertNotIn('p. ?', summary)

    async def test_report_failure_is_coordinator_owned_and_keeps_known_outcomes(self):
        class FakeReceiptAgent:
            async def run(self, source, work):
                return receipt(source['receipt_id'])
        class BrokenReportAgent:
            async def run(self, receipts, work):
                raise OSError('deliberate generation failure')
        models = SimpleNamespace(agent=FunctionModel(tool_model))
        with tempfile.TemporaryDirectory() as directory:
            result = await CoordinatorAgent(models, FakeReceiptAgent(), BrokenReportAgent()).run(
                [{'receipt_id': 'a'}], Path(directory) / 'work', Path(directory) / 'output')
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(len(result['entries']), 1)
            self.assertEqual(result['artifacts'], {})

    async def test_coordinator_cannot_succeed_without_executing_tool(self):
        models = SimpleNamespace(agent=FunctionModel(lambda messages, info: ModelResponse(parts=[TextPart('Done')])), vision=TestModel())
        with tempfile.TemporaryDirectory() as directory:
            result = await CoordinatorAgent(models).run([], Path(directory), Path(directory) / 'output')
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['artifacts'], {})


class TransferTests(unittest.TestCase):
    def test_binary_upload_checksum_and_download_path(self):
        api = SandboxJobs('test', 'project')
        data = b'\x00\xffbinary'
        with patch.object(api, 'transfer', return_value=json.dumps({'uuid': 'id', 'sha256': hashlib.sha256(data).hexdigest()}).encode()) as transfer:
            self.assertEqual(api.upload(data), {'uuid': 'id', 'mode': '0600'})
            transfer.assert_called_once_with('POST', '/files', data, 'application/octet-stream')
        with patch.object(api, 'transfer', return_value=data) as transfer:
            self.assertEqual(api.download('image', '/app/a b.pdf'), data)
            self.assertEqual(transfer.call_args.args[1], '/inspect/image/download?path=%2Fapp%2Fa+b.pdf')

    def test_retrieval_validates_bytes_before_publishing_success(self):
        data = {'report.json': b'{}', 'report.pdf': b'%PDF-test'}
        response = {'status': 'completed', 'artifacts': {name: {
            'path': '/app/output/' + name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()
        } for name, raw in data.items()}}
        api = SandboxJobs('test', 'project')
        def download(image, path):
            return json.dumps(response).encode() if path.endswith('result.json') else data[Path(path).name]
        with tempfile.TemporaryDirectory() as directory, patch.object(api, 'download', side_effect=download):
            retrieve_result(api, 'image', directory)
            self.assertEqual((Path(directory) / 'report.pdf').read_bytes(), data['report.pdf'])
        response['artifacts']['report.pdf']['sha256'] = 'bad'
        with tempfile.TemporaryDirectory() as directory, patch.object(api, 'download', side_effect=download):
            with self.assertRaises(RuntimeError):
                retrieve_result(api, 'image', directory)
            self.assertFalse((Path(directory) / 'result.json').exists())
            self.assertFalse((Path(directory) / 'report.json').exists())

    def test_job_retains_output_without_preserving_environment(self):
        api = SandboxJobs('test', 'project')
        completed = {'result_image_uuid': 'result', 'metadata': {'result': {'state': {'exit_code': 0}}}}
        with patch.object(api, 'request', return_value={'uuid': 'job'}) as request, patch.object(api, 'wait', return_value=completed):
            self.assertEqual(api.run('base', {}, 'print(1)', {'NEBIUS_API_KEY': 'secret'}, 300), ('job', 'result'))
            body = request.call_args.args[2]
            self.assertFalse(body['disposable'])
            self.assertFalse(body['preserve_env'])
            self.assertNotIn('secret', body['stdin']['value'])


if __name__ == '__main__':
    unittest.main()

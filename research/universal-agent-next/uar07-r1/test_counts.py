"""Sixteen PREPARED pure contracts; unexecuted by the author, no ML/API imports."""
from pathlib import Path
import importlib.util
import unittest

_path=Path(__file__).with_name('counts.py')
_spec=importlib.util.spec_from_file_location('_reviewed_uar_count_parser',_path)
_module=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
counts=_module.counts


def result(n=16,body='',status='OK'):
    noun='test' if n==1 else 'tests'
    return body+'\n'+'-'*70+f'\nRan {n} {noun} in 0.370s\n\n{status}\n'


class CountParserTests(unittest.TestCase):
    def test_actual_regression_telemetry_skipped_null_is_not_unit_skip(self):
        body='test_metadata (__main__.Cases.test_metadata) ... {"skipped": null}\n'
        body+='  "skipped": null,\n{"nested":{"skipped":null}}\nok\n'
        self.assertTrue(counts(result(body=body),16))

    def test_zero_and_skip_words_inside_JSON_are_not_unit_status(self):
        body='{"skipped":0,"skip":"diagnostic","status":"skipped","errors":null}\n'
        self.assertTrue(counts(result(body=body),16))

    def test_ordinary_singular_plural_and_explicit_zero_skip_summary(self):
        self.assertTrue(counts(result(1),1))
        self.assertTrue(counts(result(2),2))
        self.assertTrue(counts(result(status='OK (skipped=0)'),16))

    def test_real_verbose_skip_rejected_even_if_forged_plain_OK(self):
        self.assertFalse(counts(result(body="test_one (pkg.Cases.test_one) ... skipped 'disabled'\n"),16))
        self.assertFalse(counts(result(body='...s............\n'),16))

    def test_real_doc_description_skip_line_is_rejected(self):
        body="test_one (pkg.Cases.test_one)\nShort description (scope) ... skipped 'disabled'\n"
        self.assertFalse(counts(result(body=body),16))

    def test_nonzero_skip_summary_is_rejected(self):
        for status in ['OK (skipped=1)','OK (skipped=12)','OK (skipped=1, expected failures=0)']:
            with self.subTest(status=status):self.assertFalse(counts(result(status=status),16))

    def test_actual_fail_error_detail_or_progress_is_rejected(self):
        for body in ['FAIL: test_one (pkg.Cases.test_one)\n','ERROR: test_one (pkg.Cases.test_one)\n',
                     'test_one (pkg.Cases.test_one) ... FAIL\n','test_one (pkg.Cases.test_one) ... ERROR\n',
                     '..F.............\n','..E.............\n']:
            with self.subTest(body=body):self.assertFalse(counts(result(body=body),16))

    def test_failed_status_followed_by_fake_OK_is_rejected(self):
        self.assertFalse(counts(result(status='FAILED (failures=1)')+'OK\n',16))
        self.assertFalse(counts(result(body='FAILED (errors=1)\n'),16))

    def test_missing_or_nonterminal_OK_is_rejected(self):
        self.assertFalse(counts(result().replace('\nOK\n','\n'),16))
        self.assertFalse(counts(result()+'{"telemetry":true}\n',16))
        self.assertFalse(counts('nothing ran\nOK\n',16))

    def test_fake_unanchored_or_JSON_summary_is_not_counted(self):
        self.assertFalse(counts('noise Ran 16 tests in 0.370s\n\nOK\n',16))
        self.assertFalse(counts('{"message":"Ran 16 tests in 0.370s"}\nOK\n',16))

    def test_multiple_real_summaries_are_ambiguous_even_same_count(self):
        self.assertFalse(counts(result()+result(),16))
        self.assertFalse(counts(result(1)+result(),16))

    def test_wrong_count_or_nonstandard_summary_is_rejected(self):
        self.assertFalse(counts(result(15),16))
        self.assertFalse(counts(result().replace('Ran 16 tests','Ran sixteen tests'),16))
        self.assertFalse(counts(result().replace('0.370s','unknowns'),16))

    def test_expected_failure_and_unexpected_success_are_not_full_PASS(self):
        for body in ['test_one (pkg.Cases.test_one) ... expected failure\n',
                     'test_one (pkg.Cases.test_one) ... unexpected success\n','..x.............\n','..u.............\n']:
            with self.subTest(body=body):self.assertFalse(counts(result(body=body),16))
        self.assertFalse(counts(result(status='OK (expected failures=1)'),16))

    def test_CRLF_and_trailing_whitespace_are_valid(self):
        self.assertTrue(counts(result().replace('\n','\r\n')+' \r\n',16))
        self.assertTrue(counts(result().replace('0.370s','0.370s  '),16))

    def test_invalid_input_types_and_no_zero_test_success(self):
        for text,expected in [(None,16),(b'OK',16),('',16),(result(),True),(result(),'16'),
                              (result(),None),(result(),-1),(result(0),0)]:
            with self.subTest(expected=expected):self.assertFalse(counts(text,expected))

    def test_noisy_JSON_failure_error_and_summary_strings_are_ignored(self):
        body='{"errors":[],"failure":false,"message":"FAILED (errors=1)","skipped":0}\n'
        body+='{"message":"test_one (pkg.Cases.test_one) ... skipped \'diagnostic\'"}\n'
        body+='{"message":"Ran 99 tests in 1.000s","status":"ERROR"}\n'
        self.assertTrue(counts(result(body=body),16))


if __name__=='__main__':unittest.main(verbosity=2)

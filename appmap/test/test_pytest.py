import os
import os.path
import platform

import json

from .appmap_test_base import AppMapTestBase


class TestPytest(AppMapTestBase):
    def test_basic_integration(self, pytestconfig, testdir):
        testdir.copy_example('pytest')
        testdir.monkeypatch.setenv('APPMAP', 'true')

        result = testdir.runpytest('-svv', '-k', 'test_hello_world')
        result.assert_outcomes(passed=1)

        appmap_json = os.path.join(
            str(testdir),
            'tmp', 'appmap', 'pytest', 'test_hello_world.appmap.json'
        )
        with open(appmap_json) as appmap:
            generated_appmap = self.normalize_appmap(appmap.read())

        data_dir = os.path.join(pytestconfig.rootpath,
                                'appmap', 'test', 'data', 'pytest')
        with open(os.path.join(data_dir, 'expected.appmap.json')) as f:
            expected_appmap = json.load(f)

        # Setting these outside the definition of expected_appmap makes it
        # easier to update when the expected appmap changes
        py_impl = platform.python_implementation()
        py_version = platform.python_version()
        expected_appmap['metadata']['language']['engine'] = py_impl
        expected_appmap['metadata']['language']['version'] = py_version

        assert generated_appmap == expected_appmap

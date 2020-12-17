"""Test recording context manager"""
import json
import os
import platform
import sys
from importlib import reload

import pytest

FIXTURE_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    'data'
    )


@pytest.mark.datafiles(
    os.path.join(FIXTURE_DIR, 'appmap.yml'),
    os.path.join(FIXTURE_DIR, 'example_class.py'),
    os.path.join(FIXTURE_DIR, 'expected.appmap.json')
    )
def test_recording_works(monkeypatch, datafiles):
    with open(datafiles / 'expected.appmap.json') as f:
        expected_appmap = json.load(f)

    # Setting these outside the definition of expected_appmap makes it
    # easier to update when the expected appmap changes
    py_impl = platform.python_implementation()
    py_version = platform.python_version()
    expected_appmap['metadata']['language']['engine'] = py_impl
    expected_appmap['metadata']['language']['version'] = py_version


    sys.path.append(str(datafiles))

    monkeypatch.setenv("APPMAP", "true")
    monkeypatch.setenv("APPMAP_CONFIG", str(datafiles / 'appmap.yml'))
    monkeypatch.setenv("APPMAP_LOG_LEVEL", "debug")

    import appmap
    reload(appmap._implementation.recording)  # pylint: disable=protected-access
    r = appmap.Recording()
    with r:
        from example_class import ExampleClass  # pylint: disable=import-error
        ExampleClass.static_method()
        ExampleClass.class_method()
        ExampleClass().instance_method()

    # Normalize paths
    object_id = 1

    def normalize(dct):
        nonlocal object_id
        if 'path' in dct:
            dct['path'] = os.path.basename(dct['path'])
        if 'object_id' in dct:
            assert isinstance(dct['object_id'], int)
            dct['object_id'] = object_id
            object_id += 1
        return dct

    generated_appmap = json.loads(appmap.generation.dump(r),
                                  object_hook=normalize)

    assert generated_appmap == expected_appmap
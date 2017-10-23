from . import main
from . import configurator
# import pytest
import os


def test_config_file_path():
    file_path = configurator.config_file_path()
    assert os.path.isfile(file_path)


def test_get_config():
    config = configurator.get_config()
    assert isinstance(config, configurator.Config)


def test_get_records():
    record_list = main.get_records()
    assert isinstance(record_list, list)


def test_read_user_add_report():
    report = main.read_user_add_report()
    assert isinstance(report, dict)

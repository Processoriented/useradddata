import os
import json
from .configurator import get_config
from record import Record


config = get_config()


def get_records():
    report = read_user_add_report()
    return [Record(x) for x in report['results']]


def report_file_path(report_name):
    return os.path.join(
        config.reports_dir,
        config.reports[report_name].sub_dir,
        config.reports[report_name].file)


def result_file_path(report_name):
    return os.path.join(
        config.reports_dir,
        config.results[report_name].sub_dir,
        config.results[report_name].file)


def read_user_add_report():
    file_path = report_file_path('user_adds')
    with open(file_path, 'r') as f:
        return json.load(f)


def import_json_dict(jsonfile):
    """Imports json file as dict and decodes RAW"""
    sid = None
    with open(jsonfile, 'r') as f:
        sid = json.load(f)
    rslts = []
    for rec in [x for x in sid.get('results', [])]:
        rl = [decode_input(**v) for k, v in rec.items()]
        rslts.append({x[0]: x[1] for x in rl if x is not None})
    return rslts


def decode_input(**kwargs):
    """decodes all RAW inputs to text"""
    name = kwargs.get('name', None)
    dtype = kwargs.get('type', 'VARCHAR2')
    value = kwargs.get('value', None)
    if name is None:
        return None
    if dtype == 'RAW':
        if value is not None:
            return (name, bytes.fromhex(value).decode('utf8'))
        else:
            return (name, '')
    return (name, value)

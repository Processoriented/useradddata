import os
import json


DEFAULT_CONFIG = {
    "directory": [
        'Users',
        'vincentengler',
        'Box Sync',
        'Projects',
        'BIOPROD Data for User Adds'
    ],
    "reports": {
        "locations": {
            "sub_dir": "All Locations",
            "file": "All Subinventory Locations_1050720.json"
        },
        "prod_stock": {
            "sub_dir": "All Product Stock",
            "file": "All Product Stock_1050723.json"
        },
        "ser_stock": {
            "sub_dir": "All Serialized Stock",
            "file": "All Subinventory Locations_1050720.json"
        },
        "user_adds": {
            "sub_dir": "Open User Adds",
            "file": "Open User Add Requests_1051098.json"
        }
    },
    "results": {
        "user_adds": {
            "sub_dir": "Open User Adds",
            "file": "user_add_result.json"
        }
    }
}


def get_config():
    file_path = config_file_path()
    with open(file_path, 'r') as f:
        config = Config(**json.load(f))
    return config


def update_config(config):
    if not isinstance(config, Config):
        raise TypeError('Expected a Config object.')
    with open(str(config_file_path()), 'w') as f:
        json.dump(config.to_dict(), f, indent=3)
    return


def config_file_path():
    folder = os.path.split(__file__)[0]
    file_path = os.path.join(folder, 'config.json')
    if not os.path.isfile(file_path):
        config = Config(**DEFAULT_CONFIG).to_dict()
        with open(file_path, 'w') as f:
            json.dump(config, f, indent=3)
    return file_path


class Config():
    def __init__(self, **kwargs):
        self.reports = self.make_configinfos(kwargs.get('reports', None))
        self.results = self.make_configinfos(kwargs.get('results', None))
        self.reports_dir = kwargs.get(
            'reports_dir',
            self.make_valid_reports_dir(kwargs.get('directory', [])))

    def make_valid_reports_dir(self, directory=[]):
        build_path = ''
        if len(directory) > 0:
            build_path = os.path.join(directory.pop(0))
        while len(directory) > 0:
            build_path = os.path.join(build_path, directory.pop(0))
        if not os.path.isdir(build_path):
            build_path = input('Enter directory: ')
            if not os.path.isdir(build_path):
                raise RuntimeError("Invalid directory given")
        return build_path

    def make_configinfos(self, given):
        if not isinstance(given, dict):
            return None
        processed = {}
        for key in given.keys():
            processed[key] = ConfigInfo(key, **given[key])
        return processed

    def to_dict(self):
        return {
            'reports_dir': self.reports_dir,
            'reports': {k: v.to_dict() for k, v in self.reports.items()},
            'results': {k: v.to_dict() for k, v in self.results.items()}}


class ConfigInfo():
    def __init__(self, name, **kwargs):
        self.name = name
        self.sub_dir = kwargs.get('sub_dir', '')
        self.file = kwargs.get('file', '')

    def to_dict(self):
        return {
            'sub_dir': self.sub_dir,
            'file': self.file}


if __name__ == '__main__':
    config_file_path()

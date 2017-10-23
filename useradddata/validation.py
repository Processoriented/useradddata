import os
import json
import force as sf
from datetime import datetime


def get_rules_folder():
    folder = os.path.dirname(__file__)
    return os.path.join(folder, 'validation_rules')


def get_saved_rules():
    rules_folder = get_rules_folder()
    saved = {
        x: None for x in os.listdir(rules_folder)
        if os.path.isdir(os.path.join(rules_folder, x))}
    for key in saved.keys():
        subdir = os.path.join(rules_folder, key)
        files = [x for x in os.listdir(subdir)]
        files = {os.path.split(x)[1]: x for x in files}
        files = {os.path.splitext(k)[0]: v for k, v in files.items()}
        files = {k: v for k, v in files.items() if v[-5:] == '.json'}
        saved[key] = files
    return saved


class ForceDef():
    DEFAULTS = {
        'soapType': None,
        'restrictedPicklist': False,
        'picklistValues': {},
        'referenceTo': [],
        'referenceTargetField': 'Id',
        'tested_values': {},
        'calculated': False,
        'nillable': True,
        'length': None
    }

    def __init__(self, **kwargs):
        self.sobject = kwargs['sobject']
        init_fields = [{'name': x} for x in kwargs['fields']]
        init_fields = [{**x, **self.DEFAULTS} for x in init_fields]
        envs = ['production', 'trainusers', 'uat', 'itest', 'integr']
        self.defs = {x: [f for f in init_fields] for x in envs}
        self.file_name = '%s.json' % self.sobject
        self.file_path = os.path.join(get_rules_folder(), self.file_name)
        self.get_defs()

    def get_defs(self):        
        if os.path.isfile(self.file_path):
            with open(self.file_path, 'r') as f:
                self.defs = json.loads(f)
                return
        for env in self.defs.keys():
            conn = sf.Connection(env)
            if 'error' in conn.auth.keys():
                print("%s connection error: %s: %s" % (
                    env, conn.auth['error'], conn.auth['error_description']))
                continue
            url = '%s/services/data/v40.0/sobjects/%s/describe' % (
                conn.auth['instance_url'], self.sobject)
            response = conn.req_get(url)
            response_fields = response.get('fields', [])
            defined = []
            while len(self.defs[env]) > 0:
                field = self.defs[env].pop(0)
                mtch = [
                    x for x in response_fields if x['name'] == field['name']]
                if len(mtch) > 0:
                    force_version = {
                        k: v for k, v in mtch[0].items() if k in field.keys()}
                    field = {**field, **force_version}
                defined.append(field)
            self.defs[env] = [x for x in defined]
        with open(self.file_path, 'w') as f:
            json.dump(self.defs, f, indent=3)
        return

    def check_values(self, env, values):
        pass


class Rule():
    def __init__(self, **kwargs):
        self.sobject = kwargs['sobject']
        self.field = kwargs['field']
        self.load_from_saved()

    def load_from_saved(self):
        saved_rule = {}
        saved = get_saved_rules()
        rule_file = saved.get(self.sobject, {}).get(self.field, None)
        if rule_file is not None:
            with open(self.get_save_path(), 'r') as f:
                try:
                    saved_rule = json.load(f)
                except Exception as e:
                    print('load failed on %s.\n%s' % (self.field, str(e)))
                    saved_rule = {}
        saved_envs = saved_rule.get('environments', {'Production': {}})
        setattr(
            self,
            'environments',
            {k: Environmental_Spec(
                self, k, **v) for k, v in saved_envs.items()})
        self.save()

    def get_save_path(self):
        sobj_folder = os.path.join(get_rules_folder(), self.sobject)
        if not os.path.isdir(sobj_folder):
            os.mkdir(sobj_folder)
        return os.path.join(sobj_folder, '%s.json' % self.field)

    def to_dict(self):
        return {
            'sobject': self.sobject,
            'field': self.field,
            'environments': {
                k: v.to_dict() for k, v in self.environments.items()}}

    def save(self):
        with open(self.get_save_path(), 'w') as f:
            json.dump(self.to_dict(), f, indent=3)

    def refresh_all(self):
        for k, v in self.environments.items():
            v.refresh()

    def add_environment(self, environment):
        self.environments[environment] = Environmental_Spec(
            self, environment)


class Environmental_Spec():
    DEFAULTS = (
        ('soapType', None),
        ('picklist_labels', {}),
        ('referenceTo', []),
        ('referenceTargetField', 'Id'),
        ('tested_values', {}),
        ('calculated', False),
        ('nillable', True),
        ('length', None),
        ('last_refresh', None))

    def __init__(self, rule, environment, **kwargs):
        self.rule = rule
        self.environment = environment
        for attr_ in self.DEFAULTS:
            setattr(self, attr_[0], kwargs.get(attr_[0], attr_[1]))
        if self.last_refresh is None:
            self.refresh()

    def to_dict(self):
        return {x[0]: getattr(self, x[0], x[1]) for x in self.DEFAULTS}

    def get_connection(self):
        env = ''.join(self.environment.strip().split(' ')).lower()
        return sf.Connection(env)

    def refresh(self):
        conn = self.get_connection()
        url = '%s/services/data/v40.0/sobjects/%s/describe' % (
            conn.auth['instance_url'], self.rule.sobject)
        description = conn.req_get(url)
        fields = description.get('fields', [])
        field = [x for x in fields if x.get('name', '') == self.rule.field]
        if len(field) == 0:
            return
        field = field[0]
        for attr_ in self.DEFAULTS:
            current = getattr(self, attr_[0], attr_[1])
            setattr(self, attr_[0], field.get(attr_[0], current))
        self.picklist_labels = {
            x['label']: x['value'] for x in field['picklistValues']}
        self.last_refresh = datetime.now().isoformat()

    def test_length(self, value):
        if self.soapType not in ['xsd:anyType', 'xsd:string']:
            return True
        try:
            if self.length < len(value):
                return False
        except Exception:
            pass
        return True

    def match_picklist(self, value):
        matches = (
            [v for k, v in self.picklist_labels.items() if v == value],
            [v for k, v in self.picklist_labels.items() if k == value])
        match_lens = [len(x) > 0 for x in matches]
        if True in match_lens:
            correct = matches[match_lens.index(True)][0]
            self.tested_values[value] = correct
            self.rule.save()
            return [correct]
        return []

    def get_soql(self, **kwargs):
        try:
            return sf.SOQL(
                self.get_connection(), **kwargs).get_results()
        except Exception as e:
            return []

    def get_sosl(self, **kwargs):
        try:
            return sf.SOSL(
                self.get_connection(), **kwargs).get_results()
        except Exception as e:
            return []

    def match_reference(self, value):
        matches = []
        target = self.referenceTargetField
        target = 'Id' if target is None else target
        params = {
            'fields': [target],
            'sobject': self.referenceTo[0],
            'filters': "Id='%s'" % value}
        matches.extend(self.get_soql(**params))
        if len(matches) == 0:
            params['filters'] = "Name='%s'" % value
            matches.extend(self.get_soql(**params))
        if len(matches) == 0:
            sparams = {
                'terms': [value],
                'sobject': params['sobject'],
                'returning_fields': params['fields']}
            matches.extend(self.get_sosl(**sparams))
        if len(matches) == 0:
            return []
        correct = matches[0].get(target)
        self.tested_values[value] = correct
        self.rule.save()
        return [correct]

    def test_and_suggest(self, value):
        if self.calculated:
            return (value is None, [None], 'Calculated field')
        if value is None:
            if self.nillable:
                return (True, [None], '')
            return (False, [], 'Cannot be None')
        if value in self.tested_values.keys():
            correct = self.tested_values[value]
            return (value == correct, [correct], 'Use tested')
        if len(self.picklist_labels.keys()) > 0:
            correct = self.match_picklist(value)
            return (value == correct, correct, 'Use PL value')
        if len(self.referenceTo) > 0:
            correct = self.match_reference(value)
            return (value == correct, correct, 'Use Ref value')
        if not self.test_length(value):
            return (False, [value[:self.length]], 'Too Long')
        if self.soapType == 'xsd:boolean':
            return (
                isinstance(value, bool), [bool(value)], 'boolean')
        return (True, [value], '')


if __name__ == '__main__':
    pass

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


def format_env(given):
    return ''.join(given.split(' ')).lower()


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
        if self.open_defs():
            return
        for env in self.defs.keys():
            self.pull_force_def(env)
        with open(self.file_path, 'w') as f:
            json.dump(self.defs, f, indent=3)
        return

    def open_defs(self):
        if os.path.isfile(self.file_path):
            with open(self.file_path, 'r') as f:
                self.defs = json.load(f)
                return True
        return False

    def save_defs(self):
        with open(self.file_path, 'w') as f:
            json.dump(self.defs, f, indent=3)
        return        

    def force_def_connection(self, env):
        conn = sf.Connection(env)
        if 'error' in conn.auth.keys():
            print("%s connection error: %s: %s" % (
                env, conn.auth['error'], conn.auth['error_description']))
            return (None, None)
        url = '%s/services/data/v40.0/sobjects/%s/describe' % (
            conn.auth['instance_url'], self.sobject)
        return (conn, url)

    def pull_force_def(self, env):
        conn, url = self.force_def_connection(env)
        if conn is None:
            return
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
        return

    def check_values(self, env, to_check, first=True):
        env = format_env(env)
        rules = {x['name']: x for x in self.defs[env]}
        good = {}
        fixable = {}
        unfixable = {}
        for field in to_check.keys():
            if field not in rules.keys():
                unfixable[field] = (to_check[field], ['Field not found'])
                continue
            val_type = rules[field]['soapType'].split(':')[-1]
            val_args = {
                'env': env,
                'conn': sf.Connection(env),
                'sobject': self.sobject,
                'given': to_check[field],
                'desc': rules[field]}
            if val_type == 'ID':
                validation = IdValidation(**val_args)
            elif val_type == 'string':
                validation = StringValidation(**val_args)
            elif val_type == 'boolean':
                validation = BooleanValidation(**val_args)
            else:
                validation = FieldValidation(**val_args)
            if validation.valid:
                good[field] = validation.given
            elif first:
                print('"%s" invalid for %s.%s. (%s).' % (
                    validation.given,
                    self.sobject,
                    field,
                    '; '.join(validation.problems)))
                fixable[field] = input('Enter new value:')
            else:
                unfixable[field] = (
                    validation.given,
                    validation.problems)
            rules[field]['tested_values'] = validation.tested_values
        self.defs[env] = [v for k, v in rules.items()]
        self.save_defs()
        if len(fixable.keys()) > 0:
            second = self.check_values(env, fixable, False)
            good = {**good, **second[0]}
            unfixable = {**unfixable, **second[1]}
        return (good, unfixable)


class FieldValidation():
    def __init__(self, **kwargs):
        self.env = kwargs['env']
        self.conn = kwargs['conn']
        self.sobject = kwargs['sobject']
        self.given = kwargs['given']
        for k, v in kwargs['desc'].items():
            setattr(self, k, v)
        self.valid = False
        self.problems = []
        self.suggestions = []
        self.validate()
        self.auto_correct()

    def auto_correct(self):
        if self.valid:
            return
        if len(self.suggestions) == 1:
            self.tested_values[self.given] = self.suggestions[0]
            self.given = self.suggestions[0]
            self.valid = True
        return

    def validate(self):
        results = []
        results.append(self.check_null())
        results.append(self.check_calculated())
        if False in results:
            return
        if self.tested_values.get(self.given, None) is not None:
            self.given = self.tested_values[self.given]
            self.valid = True
            return
        self.valid = self.local_validate()

    def local_validate(self):
        return True

    def check_null(self):
        if not getattr(self, 'nillable', True):
            if self.given is None:
                self.problems.append('Not nillable')
                return False
        return True

    def check_calculated(self):
        if getattr(self, 'calculated', False):
            self.problems.append('Calculated field')
            return False
        return True


class StringValidation(FieldValidation):
    def __init__(self, **kwargs):
        super(StringValidation, self).__init__(**kwargs)

    def local_validate(self):
        limit = getattr(self, 'length', 1000)
        if not isinstance(self.given, str):
            try:
                self.problems.append('Not a string.')
                self.suggestions.append(str(self.given)[:limit])
            except Exception as e:
                self.problems.append(str(e))
            return False
        if len(self.given) > limit:
            self.problems.append('String too long')
            self.suggestions.append(self.given[:limit])
            return False
        return True

    def picklist_validate(self):
        picklist = getattr(self, 'picklistValues', [])
        if len(picklist) == 0:
            return True
        if not getattr(self, 'restrictedPicklist', False):
            return True
        values = [x['value'] for x in picklist]
        if self.given in values:
            return True
        self.suggestions.extend([
            x['value'] for x in picklist if x['label'] == self.given])
        self.problems.append('Not in picklist')
        return False


class BooleanValidation(FieldValidation):
    def __init__(self, **kwargs):
        super(BooleanValidation, self).__init__(**kwargs)

    def local_validate(self):
        if not isinstance(self.given, bool):
            self.problems.append('Not a boolean')
            return False
        return True


class IdValidation(FieldValidation):
    def __init__(self, **kwargs):
        super(IdValidation, self).__init__(**kwargs)
        self.conn = sf.Connection(self.env)

    def local_validate(self):
        if not isinstance(self.given, str):
            self.problems.append('Not a valid id')
            return False
        if len(self.given) not in [15, 18]:
            self.problems.append('Not a valid id')
            self.suggestions.extend(self.lookup_id())
            return False
        return self.idExists()

    def match_field(self, sobject, field='name'):
        rtn = []
        filt = "%s='%s'" % (field, self.given)
        try:
            query = sf.SOQL(
                self.conn,
                sobject=sobject,
                filters=[filt])
            rtn.extend([
                x['Id'] for x in query.get_results()])
        except Exception as e:
            pass
        return rtn

    def search_given(self, sobject):
        rtn = []
        try:
            rtn.extend([
                x[sobject[1]] for x in sf.SOSL(
                    self.conn,
                    sobject=sobject[0],
                    terms=[self.given]).get_results()])
        except Exception as e:
            pass
        return rtn

    def reference_obj_field(self):
        objs = getattr(self, 'referenceTo', [])
        field = getattr(self, 'referenceTargetField', None)
        field = 'Id' if field is None else field
        if len(objs) == 0:
            objs.append(self.sobject)
        return [(x, field) for x in objs]

    def lookup_id(self):
        matched_names = []
        ref_obj_field = self.reference_obj_field()
        for ref in ref_obj_field:
            matched_names.extend(self.match_field(ref))
        if len(matched_names) > 0:
            return matched_names
        for ref in ref_obj_field:
            matched_names.extend(self.search_given(ref))
        return matched_names

    def idExists(self):
        matches = []
        ref_obj_field = self.reference_obj_field()
        for ref in ref_obj_field:
            matches.extend(self.match_field(ref[0], ref[1]))
        return len(matches) != 0


if __name__ == '__main__':
    pass

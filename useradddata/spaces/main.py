import force as sf
from ..validation import Rule
from .actions import InsertAction, UpdateAction, SkipAction


def is_int(param):
    try:
        int(param)
        return True
    except Exception as e:
        return False


def error_if_none(message):
    def raise_error(function):
        def wrapper(*args, **kwargs):
            rtn = function(*args, **kwargs)
            if rtn in [None, '']:
                raise RuntimeError(message)
            return rtn
        return wrapper
    return raise_error


class RecordSpace():
    def __init__(self, parent, sobject, *args, **kwargs):
        self.record = parent
        self.action = None
        self.valid = False
        self.sfid = None
        self.sobject = sobject if sobject != 'Ref' else None
        self.fields = [] if not hasattr(self, 'fields') else self.fields
        for field in args:
            self.fields.append(field.name)
            setattr(self, field.name, field.value)
        self.fields_from_dict(kwargs)
        self.matching_terms = getattr(self, 'matching_terms', [])
        self.description = None
        self.excluded = []
        self.valid_fields = []

    def get_name(self):
        fallback = 'unnamed %s' % self.sobject
        return getattr(self, 'name', fallback)

    def to_dict(self):
        return {
            x: getattr(self, x) for x in self.fields if x not in self.excluded}

    def take_action(self):
        if self.action is None:
            self.action = self.determine_action()
        if not self.validate():
            return
        return self.action.take_action()

    def determine_action(self):
        if self.sobject is None:
            return SkipAction(self)
        return self.handle_matches()

    def handle_matches(self):
        matches = self.get_matches_from_force()
        if len(matches) == 0:
            return InsertAction(self)
        choice = self.choose_match(matches)
        if choice is None:
            return InsertAction(self)
        self.merge_with_match(choice)
        return UpdateAction(self, self.sfid)

    def choose_match(self, matches):
        display_fields = ['Id']
        display_fields.extend(self.matching_terms)
        filtered = [
                {k: v for k, v in x.items() if k in display_fields}
                for x in matches]
        print("<blank>.\t<Ignore Matches and create new record>")
        for i in range(len(matches)):
            display_match = "\t".join(
                ["%s: %s" % (k, str(v)) for k, v in filtered[i].items()])
            print("%d.\t\t%s" % (i, display_match))
        selection = input('Choose option (or leave blank): ')
        match = None
        try:
            match = matches[int(selection)]
        except Exception as e:
            pass
        return match

    def merge_with_match(self, match):
        for key, value in match.items():
            not_found = None if value is not None else '_'
            if value == getattr(self, key, not_found):
                self.excluded.append(key)
        if hasattr(self, 'IsActive'):
            setattr(self, 'IsActive', 'true')
            self.excluded = [x for x in self.excluded if x != 'IsActive']
        self.sfid = match['Id']
        if len(self.fields) == len(self.excluded):
            self.action = 'Done'
            return
        self.fields.append("Id")
        setattr(self, 'Id', match['Id'])
        self.action = 'Update'

    def get_matching_sfids(self):
        if len(self.matching_terms) == 0:
            return []
        sfids = sf.SOSL(
            self.record.conn,
            terms=[getattr(self, x) for x in self.matching_terms],
            sobject=self.sobject,
            join_terms_on='OR').get_results()
        return [x['Id'] for x in sfids if x.get('Id', None) is not None]

    def get_matches_from_force(self):
        sfids = self.get_matching_sfids()
        if len(sfids) == 0:
            return []
        filters = "Id IN ('%s')" % "','".join(sfids)
        fields = ["Id"]
        fields.extend(self.fields)
        return sf.SOQL(
            self.record.conn,
            fields=fields,
            sobject=self.sobject,
            filters=filters).get_results()

    def describe(self):
        self.description = sf.ForceDescription(self.record.conn, self.sobject)

    def get_rules(self):
        env = self.record.ref.Environment
        rules = {x: Rule(sobject=self.sobject, field=x) for x in self.fields}
        for field, rule in rules.items():
            if getattr(rule, 'environments', {}).get(env, None) is None:
                rule.add_environment(env)
        return {k: v.environments[env] for k, v in rules.items()}

    def validate(self):
        rules = self.get_rules()
        results = {
            x: rules[x].test_and_suggest(getattr(self, x))
            for x in self.fields if x not in self.valid_fields}
        failures = {k: v for k, v in results.items() if not v[0]}
        fixables = {k: v for k, v in failures.items() if len(v[1]) > 0}
        unfixables = {k: v for k, v in failures.items() if len(v[1]) == 0}
        for fix in fixables.keys():
            setattr(self, fix, fixables[fix][1][0])
        if len(unfixables.keys()) != 0:
            unfixed = []
            for field in unfixables.keys():
                old_value = getattr(self, field)
                print('"%s" invalid for %s.%s. (%s).' % (
                    str(getattr(self, field)),
                    self.sobject,
                    field,
                    unfixables[field][2]))
                new_value = input('Enter new value: ')
                retest = rules[field].test_and_suggest(new_value)
                if retest[0] or len(retest[1]) == 1:
                    setattr(self, field, retest[1][0])
                    rules[field].tested_values[old_value] = retest[1][0]
                    rules[field].rule.save()
                else:
                    unfixed.append(field)
        self.valid = len(unfixed) == 0
        return self.valid

    def fields_from_dict(self, given):
        for key, value in given.items():
            self.fields.append(key)
            setattr(self, key, value)

    def set_user_fields(self):
        pass

    def set_locn_fields(self):
        pass

    def set_prod_stock_fields(self):
        pass

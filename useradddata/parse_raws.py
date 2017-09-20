import force as sf
from .validation import Rule


class ParsedRawRecord():
    def __init__(self, given):
        self.given = given
        self.classified = self.classify()

    def classify(self):
        raws = [RawField(k, **v) for k, v in self.given.items()]
        pointers = list(set([x.points_to for x in raws]))
        grouped = {
            x: {y.meta: y.value_ for y in raws if y.points_to == x}
            for x in pointers}
        named = {k: v for k, v in grouped.items() if 'name' in v.keys()}
        spaced = {k: v for k, v in named.items() if 'ns' in v.keys()}
        spaces = list(set([v['ns'] for k, v in spaced.items()]))
        return {
            s: {v['name']: v['value']
                for k, v in spaced.items() if v['ns'] == s}
            for s in spaces}


class Record():
    def __init__(self, given):
        parsed_raw = ParsedRawRecord(given).classified
        self.ref = RecordSpace(self, None, **parsed_raw.get('ref', {}))
        self.user = UserSpace(self, **parsed_raw.get('user', {}))
        self.permission_sets = []
        self.package_licenses = []
        self.sites = []
        self.technician = None
        self.stock = []
        self.conn = None
        try:
            self.make_connection()
        except Exception as e:
            print('No connection for record:\n%s\n%s' % (
                str(self.to_dict(), str(e))))

    def make_connection(self, env=None):
        if env is None:
            ref = getattr(self, 'ref')
            env = getattr(ref, 'Environment').lower()
            env = ''.join(env.split(' ')).strip()
        self.conn = sf.Connection(env)

    def attached_spaces(self):
        attrs = [getattr(self, x) for x in dir(self)]
        spaces = [x for x in attrs if isinstance(x, RecordSpace)]
        for list_ in [x for x in attrs if isinstance(x, list)]:
            spaces.extend([x for x in list_ if isinstance(x, RecordSpace)])
        return spaces

    def to_dict(self):
        rtn = {
            'ref': self.ref.to_dict(),
            'user': self.user.to_dict(),
            'permission_sets': [x.to_dict() for x in self.permission_sets],
            'package_licenses': [x.to_dict() for x in self.package_licenses],
            'sites': [x.to_dict() for x in self.sites],
            'technician': None,
            'stock': [x.to_dict() for x in self.stock]}
        if self.technician is not None:
            rtn['technician'] = self.technician.to_dict()
        return rtn

    def process_user(self):
        self.user.handle_matches()
        self.user.new_validate()
        self.user.take_action()
        self.ref.SF_User_Id = self.user.sfid
        for space in self.attached_spaces():
            space.set_user_fields()
        for set_ in self.permission_sets:
            set_.handle_matches()
            set_.new_validate()
            set_.take_action()
        for license in self.package_licenses:
            license.handle_matches()
            license.new_validate()
            license.take_action()

    def process_sites(self):
        if len(self.sites) == 0:
            return
        if len(self.sites) > 1:
            print("Choose a site.")
            return
        site = self.sites[0]
        site.handle_matches()
        site.new_validate()
        site.take_action()
        self.technician.set_locn_fields()
        for stock in self.stock:
            stock.set_locn_fields()
        self.process_tech()
        self.process_stock()

    def process_tech(self):
        self.technician.handle_matches()
        self.technician.new_validate()
        self.technician.take_action()

    def process_stock(self):
        if len(self.stock) == 0:
            return
        for stock in self.stock:
            self.technician.handle_matches()
            self.technician.new_validate()
            self.technician.take_action()


class RawField():
    def __init__(self, report_key, **kwargs):
        self.report_key = report_key
        self.name_ = kwargs.get('name', '').upper()
        self.value_ = kwargs.get('value', None)
        self.type_ = kwargs.get('type', type(self.value_))
        expected_metas = ['NS', 'NAME']
        meta = self.name_.split('_')[-1]
        meta = meta if meta in expected_metas else 'value'
        self.meta = meta.lower()
        self.points_to = '_'.join(self.name_.split('_')[:2])


class Action():
    def __init__(self, space, name, desc, corrections={}):
        self.space = space
        self.name = name
        self.description = desc
        self.corrections = corrections
        self.result = ''

    def short_correction_display(self):
        field_names = [x for x in self.corrections.keys()]
        if len(field_names) == 0:
            return ''
        rtn = [", ".join(field_names)]
        while len(str(rtn[-1])) > 50:
            last_row = rtn.pop()
            start = last_row[:40].split(", ")
            trail = "%s%s" % (str(start.pop()), last_row[40:])
            rtn.append(", ".join(start))
            rtn.append(trail)
        return ",\n".join(rtn)

    def to_dict(self):
        return {
            'action': self.name.title(),
            'description': self.description,
            'corrections': self.short_correction_display()}

    def take_action(self):
        print('No Action defined for %s', self.name.title())
        return False


class InsertAction(Action):
    def __init__(self, space, corrections={}):
        name = 'insert'
        desc = 'Insert new record'
        if len(corrections.keys()) > 0:
            name = 'fix'
            desc = 'Fix issues and insert'
        super(InsertAction, self).__init__(space, name, desc, corrections)

    def take_action(self):
        if self.name == 'fix':
            self.make_corrections()
        url = '%s/services/data/v40.0/sobjects/%s/' % (
            self.space.record.conn.auth['instance_url'], self.space.sobject)
        try:
            response = self.space.record.conn.req_post(
                url, self.space.to_dict())
            setattr(self.space, 'sfid', response['id'])
            available = [
                UpdateAction(self.space, self.space.sfid),
                SkipAction(self.space)]
            setattr(self.space, 'available_actions', available)
            return True
        except Exception as e:
            print(e)
            return False

    def make_corrections(self):
        pass


class UpdateAction(Action):
    def __init__(self, space, sfid):
        name = 'update'
        url = '/'.join([space.record.conn.auth['instance_url'], sfid])
        desc = "Update %s: %s" & (space.sobject, url)
        super(UpdateAction, self).__init__(space, name, desc)

    def take_action(self):
        payload = self.space.to_dict()
        payload = {k: v for k, v in payload.items() if k != 'Id'}
        if hasattr(self, 'IsActive'):
            payload['IsActive'] = 'true'
        url = '%s/services/data/v40.0/sobjects/%s/%s' % (
            self.space.record.conn.auth['instance_url'],
            self.space.sobject,
            self.sfid)
        try:
            response = self.space.record.conn.req_patch(url, payload)
            if response.status_code > 299:
                raise RuntimeError(str(response))
            setattr(self.space, 'sfid', self.sfid)
            available = [self, SkipAction(self.space)]
            setattr(self.space, 'available_actions', available)
            return True
        except Exception as e:
            print(e)
            return False


class SkipAction(Action):
    def __init__(self, space):
        desc = "Skip %s %s" % (space.sobject, space.get_name())
        super(SkipAction, self).__init__(space, 'done', desc)

    def take_action(self):
        return True


class RecordSpace():
    def __init__(self, parent, sobject, *args, **kwargs):
        self.record = parent
        self.action = 'Insert'
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
        self.available_actions = []

    def get_name(self):
        fallback = 'unnamed %s' % self.sobject
        return getattr(self, 'name', fallback)

    def to_dict(self):
        return {
            x: getattr(self, x) for x in self.fields if x not in self.excluded}

    def get_actions(self):
        if len(self.available_actions) == 0:
            self.set_available_actions()
        return [x.to_dict() for x in self.available_actions]

    def take_selected_action(self, selection):
        action = self.available_actions[selection]
        if action.take_action():
            print('successfully %sed %s.' % (action.name, self.get_name()))

    def take_action(self):
        if not self.valid:
            return
        if self.description is None:
            self.describe()
        action_method = "%s_action" % self.action.lower()
        getattr(self, action_method, 'done_action')()

    def insert_action(self):
        url = '%s/services/data/v40.0/sobjects/%s/' % (
            self.record.conn.auth['instance_url'], self.sobject)
        response = self.record.conn.req_post(url, self.to_dict())
        self.sfid = response.get('id')
        self.action = 'Done'

    def update_action(self):
        payload = self.to_dict()
        sfid = payload['Id']
        payload = {k: v for k, v in payload.items() if k != 'Id'}
        if hasattr(self, 'IsActive'):
            payload['IsActive'] = 'true'
        url = '%s/services/data/v40.0/sobjects/%s/%s' % (
            self.record.conn.auth['instance_url'], self.sobject, sfid)
        response = self.record.conn.req_patch(url, payload)
        if response.status_code < 300:
            self.action = 'Done'
            return
        self.action = 'Failed_Update'
        return

    def done_action(self):
        pass

    def set_available_actions(self):
        rtn = [InsertAction(self, self.check_valid())]
        rtn.extend([UpdateAction(self, x) for x in self.get_matching_sfids()])
        rtn.append(SkipAction(self))
        self.available_actions = rtn

    def check_valid(self, loop_count=0):
        rules = self.get_rules()
        results = {
            x: rules[x].test_and_suggest(getattr(self, x))
            for x in self.fields}
        failures = {k: v for k, v in results.items() if not v[0]}
        if len(failures.keys()) == 0:
            return {}
        fixables = {k: v for k, v in failures.items() if len(v[1]) > 0}
        if len(fixables.keys()) > 0 and loop_count < 3:
            for fix in fixables.keys():
                setattr(self, fix, fixables[fix][1][0])
            return self.check_valid(loop_count + 1)
        return failures

    def handle_matches(self):
        matches = self.get_matches_from_force()
        if len(matches) == 0:
            return
        choice = self.choose_match(matches)
        if choice is None:
            return
        self.merge_with_match(choice)

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

    def new_validate(self):
        rules = self.get_rules()
        results = {
            x: rules[x].test_and_suggest(getattr(self, x))
            for x in self.fields}
        failures = {k: v for k, v in results.items() if not v[0]}
        fixables = {k: v for k, v in failures.items() if len(v[1]) > 0}
        unfixables = {k: v for k, v in failures.items() if len(v[1]) == 0}
        for fix in fixables.keys():
            setattr(self, fix, fixables[fix][1][0])
        bools = [
            k for k, v in rules.items() if v.soapType == 'xsd:boolean']
        bools = [x for x in bools if x in self.fields]
        for bool_field in bools:
            current = getattr(self, bool_field, None)
            if current is not None:
                setattr(self, bool_field, str(current).lower())
        if len(unfixables.keys()) == 0:
            self.valid = True
            return
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

    def validate(self, verbose=False):
        self.valid = self.check_values()
        bools = [
            x for x in self.description.fields if x.soapType == 'xsd:boolean']
        bools = [x.name for x in bools if x.name in self.fields]
        for bool_field in bools:
            current = getattr(self, bool_field, None)
            if current is not None:
                setattr(self, bool_field, str(current).lower())
        needed = [x for x in self.description.fields if not x.nillable]
        needed = [x for x in needed if not x.defaultedOnCreate]
        needed = [x.name for x in needed if x.name not in self.fields]
        if verbose:
            print(needed)

    def check_values(self):
        if self.description is None:
            self.describe()
        results = {}
        for field in self.fields:
            result = (False, None, 'Field Not in Description')
            field_description = self.description.get_field_description(field)
            if field_description is not None:
                result = field_description.test_proposed(getattr(self, field))
            results[field] = result
        fail_count = len([k for k, v in results.items() if not v[0]])
        if fail_count == 0:
            return True
        fails = {k: v for k, v in results.items() if not v[0]}
        replaceable_count = len(
            [k for k, v in fails.items() if v[1] is not None])
        if replaceable_count == 0:
            # self.show_failures(fails)
            return False
        replaceable = {k: v for k, v in fails.items() if v[1] is not None}
        originals = getattr(self, 'originals', {})
        for field, info in replaceable.items():
            original = originals.get(field, [])
            original.append(getattr(self, field, None))
            originals[field] = original
            setattr(self, field, info[1])
        setattr(self, 'originals', originals)
        return self.check_values()

    def show_failures(self, fails):
        for field, fail in fails.items():
            msg = '%s: %s\n%s' % (
                field, str(getattr(self, field, None)), fail[2][0])
            print(msg)

    def exists_in_force(self):
        if getattr(self, 'sfid', None) is None:
            return False
        lookup = sf.SOQL(
            self.record.conn,
            fields=['Id'],
            sobject=self.sobject,
            filters=["Id='%s'" % self.sfid]).get_results()
        return len(lookup) > 0

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


class UserSpace(RecordSpace):
    def __init__(self, parent, **kwargs):
        terms = ['Username', 'SSO__c']
        terms = [x for x in terms if kwargs.get(x, None) is not None]
        self.matching_terms = terms
        super(UserSpace, self).__init__(
            parent, 'User', **kwargs)
        chatterFields = [
            'UserPermissionsChatterAnswersUser',
            'UserPreferencesHideChatterOnboardingSplash',
            'UserPreferencesHideSecondChatterOnboardingSplash',
            'UserPreferencesHideCSNGetChatterMobileTask']
        for field in chatterFields:
            delattr(self, field)
            self.fields = [x for x in self.fields if x != field]

    def get_name(self):
        fallback = 'unnamed user'
        return getattr(self, 'Username', getattr(self, 'SSO__c', fallback))

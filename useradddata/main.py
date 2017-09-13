import os
import json
import force as sf
from .configurator import get_config


config = get_config()


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


def update_results(user):
    file_path = result_file_path('user_adds')
    with open(file_path, 'r') as f:
        current = json.load(f)
    remaining = [x for x in current if x['RECORD_ID'] != user.RECORD_ID]
    new_result = {
        'RECORD_ID': user.RECORD_ID,
        'SF User Id': user.SF_User_Id,
        'SF User Link': None}
    if user.SF_User_Id not in [None, '']:
        new_result['SF User Link'] = '%s/%s' % (
            user.conn.auth['instance_url'], user.SF_User_Id)
    updated = [new_result]
    updated.extend(remaining)
    with open(file_path, 'w') as f:
        json.dump(updated, f, indent=2)
    return


def get_user_add_records():
    report = read_user_add_report()
    useraddmap = None
    for result in report['results']:
        if useraddmap is None:
            useraddmap = UserAddMap(result)
        yield UserAddRecord(result, useraddmap)


def handle_user_permissions(user):
    """handles licenses and permissions for user add"""
    sfid = user.SF_User_Id
    pids = [getattr(user, 'ServiceMax_Standard_PSID')]
    pids.append(getattr(user, 'Product_Pricebook_PSID'))
    pids = [x for x in pids if x is not None]
    plid = getattr(user, 'PackageLicenseId')
    for pid in pids:
        upsert_pid(user.conn, sfid, pid)
    if plid is not None:
        upsert_plid(user.conn, sfid, plid)


def upsert_pid(conn, sfid, pid):
    """upserts permission set records for user"""
    soql = sf.SOQL(conn, sobject='PermissionSetAssignment')
    soql.append_filter("AssigneeId='%s'" % sfid)
    soql.append_filter("PermissionSetId='%s'" % pid.strip())
    if len(soql.get_results()) > 0:
        return
    psadesc = sf.Description(conn, 'PermissionSetAssignment')
    rslt = psadesc.insert_rec(
        AssigneeId=sfid,
        PermissionSetId=pid)
    if rslt is None:
        print('Failed to add %s PermissionSet')
    return


def upsert_plid(conn, sfid, plid):
    """upserts permission set records for user"""
    soql = sf.SOQL(conn, sobject='UserPackageLicense')
    soql.append_filter("UserId='%s'" % sfid)
    soql.append_filter("PackageLicenseId='%s'" % plid)
    if len(soql.get_results()) > 0:
        return
    psadesc = sf.Description(conn, 'UserPackageLicense')
    rslt = psadesc.insert_rec(
        UserId=sfid,
        PackageLicenseId=plid)
    if rslt is None:
        print('Failed to add %s UserPackageLicense')
    return


def make_naming_map(raw_record):
    """Creates dict of {record key: last part of record key}"""
    return {v['name']: v['name'].split('_')[-1] for k, v in raw_record.items()}


def match_report(matches, dspl_cols):
    if len(matches) > 1:
        dspl_matches = [{d: x[d] for d in dspl_cols} for x in matches]
        choice = pick_match(dspl_matches)
        return matches[choice]
    if len(matches) == 1:
        return matches[0]
    else:
        return None


def pick_match(matches, new_rec=None):
    """User interactions to pick correct matching record"""
    to_show = []
    offset = 0
    if new_rec is not None:
        to_show.append(new_rec)
        offset = 1
    to_show.extend(matches)
    last = len(to_show) - 1
    print('Select the matching record:\n\n')
    for i in range(len(to_show)):
        print('%d.\t%s' % (i, str(to_show[i])))
    print('Enter selection number 0 - %d: ' % last)
    return int(input()) - offset


def get_data_key(map_key):
    """splits map_key by _ and returns all but last item"""
    return '_'.join([x for x in map_key.split('_')][:-1]).upper()


def set_location_defaults(rec, user):
    rec['SVMXC__Stocking_Location__c'] = True
    rec['SVMXC__Location_Type__c'] = 'Field'
    rec['HCLS_Active_Location__c'] = True
    pbr = 'GEHC LS Global Service Team Hours'
    rec['SVMXC__Preferred_Business_Hours__c'] = pbr
    rec['SVMXC__Service_Engineer__c'] = user.SF_User_Id
    rec['GEHC_LS_Tech_Owner_Reference__c'] = user.SF_User_Id
    rec['Oracle_Sub_Inventory__c'] = user.Oracle_SubInventory
    locn_name = '%s %s - TRUNK STOCK' % (
        user.get_field('FirstName').given,
        user.get_field('LastName').given)
    rec['Name'] = locn_name
    return rec


def set_tech_items(user):
    name = "%s %s" % (
        user.get_field('FirstName').given,
        user.get_field('LastName').given)
    return {
        'Name': name,
        'SVMXC__Service_Group__c': user.ServiceTeam,
        'SVMXC__Salesforce_User__c': user.SF_User_Id,
        'SVMXC__Service_Territory__c': user.get_field('Territory__c').given,
        'SVMXC__Active__c': True,
        'SVMXC__Street__c': user.locn.get_field('SVMXC__Street__c').given,
        'SVMXC__City__c': user.locn.get_field('SVMXC__City__c').given,
        'SVMXC__Email__c': user.get_field('Email').given,
        'SVMXC__Zip__c': user.locn.get_field('SVMXC__Zip__c').given,
        'SVMXC__Country__c': user.get_field('Territory__c').given,
        'Global_Region__c': user.get_field('Global_Region__c').given,
        'Global_Sub_Region__c': user.get_field('Global_Sub_Region__c').given,
        'SVMXC__Working_Hours__c': user.locn.get_field(
            'SVMXC__Preferred_Business_Hours__c').valid}


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


def make_filtered_map(naming_map, map_filter):
    """Creates dict of {data key: map key}"""
    map_keys = [k for k, v in naming_map.items() if v == map_filter]
    return {get_data_key(x): x for x in map_keys}


def is_meta_field(field, meta_term):
    flag = field['name'].split('_')[-1]
    return flag == meta_term


def rename_for_map(raw_record):
    for key in raw_record.keys():
        meta = 'value'
        meta = 'ns' if is_meta_field(raw_record[key], 'ns') else meta
        meta = 'name' if is_meta_field(raw_record[key], 'name') else meta
        raw_record[key]['meta'] = meta
    ns = {
        v['name']: v['value'] for k, v in raw_record.items()
        if v['meta'] == 'ns'}
    ns = {'_'.join(k.split('_')[:-1]).upper(): v for k, v in ns.items()}
    names = {
        v['name']: v['value'] for k, v in raw_record.items()
        if v['meta'] == 'name'}
    names = {'_'.join(k.split('_')[:-1]).upper(): v for k, v in names.items()}
    values = {k: v for k, v in raw_record.items() if v['meta'] == 'value'}
    out = {}
    for key in values.keys():
        mapping = {
            'ns': ns.get(values[key]['name'], 'no_ns'),
            'name': names.get(values[key]['name'], 'no_name')}
        out[key] = mapping
    return out


class UserAddMap():
    """Makes Map for renaming data in a user add report record"""
    def __init__(self, raw_record):
        naming_map = rename_for_map(raw_record)
        self.map_namespaces = []
        self.force_objects = []
        for key, mapping in naming_map.items():
            ns = self.get_map_namespace(mapping['ns'])
            map_item = UserAddMapItem(key, mapping['name'], ns)
            if map_item.is_valid():
                setattr(self, key, map_item)

    def get_map_namespace(self, ns_name):
        """Finds or creates UserAddMapNameSpace for attr"""
        matches = [x for x in self.map_namespaces if x.name == ns_name]
        if len(matches) == 0:
            ns = UserAddMapNameSpace(self, ns_name)
            self.map_namespaces.append(ns)
            return ns
        return matches[0]


class UserAddMapNameSpace():
    """Grouping of map items by namespace"""
    def __init__(self, parent, name):
        self.name = name
        self.parent = parent
        self.force_object = self.get_force_object()

    def get_force_object(self):
        """Finds or creates SalesForceObject for NameSpace"""
        if self.name == 'ref':
            return None
        found = self.parent.force_objects
        found = [x for x in found if x == self.name.title()]
        if len(found) > 0:
            return found[0]
        force_object = SalesForceObject(self.name.title())
        self.parent.force_objects.append(force_object)
        return force_object


class UserAddMapItem():
    """Map Item object for User Add Map"""
    def __init__(self, data_key, name, ns):
        self.data_key = data_key
        self.name = name
        self.ns = ns

    def is_valid(self):
        return self.name != 'nameless' and isinstance(
            self.ns, UserAddMapNameSpace)


class UserAddRecord():
    def __init__(self, raw_record, useraddmap):
        self.useraddmap = useraddmap
        self.parse_raws(raw_record)
        self.conn = self.connect()
        self.prepare_user_record()
        return

    def parse_raws(self, raws):
        """Loop thru keys in raw and create attrs"""
        mapped = [self.apply_mapping(k, v) for k, v in raws.items()]
        mapped = [x for x in mapped if x is not None]
        refs = [x for x in mapped if x['ns'] == 'ref']
        for ref in refs:
            setattr(self, ref['name'], ref['value'])
        user_fields = [x for x in mapped if x['ns'] != 'ref']
        force_object = SalesForceObject(user_fields[0]['ns'].title())
        user_fields = {x['name']: x['value'] for x in user_fields}
        user_insert = SalesForceRecord(force_object, **user_fields)
        setattr(self, 'user_insert', user_insert)
        return

    def apply_mapping(self, key, value):
        """Returns dict of applied mapping for key, value pair"""
        mapitem = getattr(self.useraddmap, key, None)
        if mapitem is None:
            return None
        return {
            'name': mapitem.name,
            'value': value['value'],
            'ns': mapitem.ns.name}

    def connect(self):
        force_object = self.user_insert.force_object
        conn = force_object.connect(self.Environment)
        force_object.describe()
        return conn

    def prepare_user_record(self):
        """Gets User Record ready for upsert"""
        if not hasattr(self, 'user_insert'):
            return
        user = self.user_insert
        user.validate()
        result_cols = ['Id', 'Username', 'FederationIdentifier']
        term = user.Username.valid
        matches = user.find_matches(term, result_cols)
        if len(matches) == 0:
            term = user.SSO__c.valid
            matches.extend(user.find_matches(term, result_cols))
        if len(matches) > 0:
            new_rec = {
                'Id': '<New Record>',
                'Username': user.Username.valid,
                'FederationIdentifier': user.FederationIdentifier.valid}
            choice = pick_match(matches, new_rec)
            if choice > -1:
                user.prepare_update(matches[choice]['Id'])
                return
            fed_ids = [x['FederationIdentifier'] for x in matches]
            fed_ids = [x for x in fed_ids if x not in [None, '']]
            if user.FederationIdentifier.valid in fed_ids:
                user.FederationIdentifier.valid = None
        return

    def upsert_user(self):
        """Upserts user record"""
        success, message = self.user_insert.upsert()
        if not success:
            print('Upsert failed (%s)' % message)
            return success
        self.SF_User_Id = message
        link = '%s/%s' % (
            self.conn.auth['instance_url'], self.SF_User_Id)
        print('User %s(%s): %s' % (
            self.user_insert.Username.given, message, link))
        handle_user_permissions(self)
        self.upsert_others()
        update_results(self)
        return success

    def upsert_others(self):
        locn = getattr(self, 'Oracle_Location_Number', None)
        if locn is None:
            return
        subinv = getattr(self, 'Oracle_SubInventory', None)
        if subinv is None:
            print('No subinventory provided.')
            return
        locn_id = self.upsert_locn(locn, subinv)
        if locn_id is None:
            return
        self.upsert_tech(locn_id)
        self.upsert_prod_stock(locn_id)

    def upsert_locn(self, locn, subinv):
        known = import_json_dict(report_file_path('locations'))
        matches = [x for x in known if x['Location_Number__c'] == locn]
        dspl_cols = [
            'Location_Number__c',
            'Source_Organization__c',
            'HCLS_Bill_To_Site_Use_Id__c']
        match = match_report(matches, dspl_cols)
        if match is None:
            print('No known Oracle Locations numbered %s' % locn)
            return None
        sflocn_obj = SalesForceObject('SVMXC__Site__c')
        sflocn_obj.conn = self.user_insert.force_object.conn
        sflocn_obj.describe()
        match = set_location_defaults(match, self)
        locn_ins = SalesForceRecord(sflocn_obj, **match)
        locn_ins.validate()
        new_rec = {d: match[d] for d in dspl_cols}
        new_rec['Id'] = '<New Record>'
        dspl_cols.append('Id')
        matches = locn_ins.find_matches(match['Name'], dspl_cols)
        if len(matches) > 0:
            choice = pick_match(matches, new_rec)
            if choice > -1:
                locn_ins.prepare_update(matches[choice]['Id'])
        success, message = locn_ins.upsert()
        if not success:
            print('Upsert of %s failed (%s).' % (match['Name'], message))
            return None
        setattr(self, 'locn', locn_ins)
        print('Successfully upserted %s - %s' % (match['Name'], message))
        return message

    def upsert_tech(self, locn_id):
        sftech_obj = SalesForceObject('SVMXC__Service_Group_Members__c')
        sftech_obj.conn = self.user_insert.force_object.conn
        sftech_obj.describe()
        tech = set_tech_items(self)
        tech_ins = SalesForceRecord(sftech_obj, **tech)
        tech_ins.validate()
        dspl_cols = ['Name', 'Global_Region__c']
        new_rec = {d: tech[d] for d in dspl_cols}
        new_rec['Id'] = '<New Record>'
        dspl_cols.append('Id')
        matches = tech_ins.find_matches(tech['Name'], dspl_cols)
        if len(matches) > 0:
            choice = pick_match(matches, new_rec)
            if choice > -1:
                tech_ins.prepare_update(matches[choice]['Id'])
        success, message = tech_ins.upsert()
        if not success:
            print('Upsert of %s failed (%s).' % (tech['Name'], message))
            return None
        setattr(self, 'tech', tech_ins)
        print('Successfully upserted %s - %s' % (tech['Name'], message))
        return message

    def upsert_prod_stock(self, locn_id):
        pass

    def force_records(self):
        """Returns a list of SalesForceRecords attached"""
        return [x for x in dir(self) if isinstance(x, SalesForceRecord)]

    def get_force_record(self, force_object):
        """Get SalesForceRecord with same object"""
        found = self.force_records()
        found = [x for x in found if x.force_object == force_object]
        if len(found) > 0:
            return found[0]
        return None


class SalesForceObject():
    """Representation of a Sales Force Object for user add proc"""
    def __init__(self, name):
        """Takes the name of object and looks up SF Description"""
        self.conn = None
        self.name = name
        self.desc = None
        return

    def connect(self, environment):
        """Gets Connection for environment"""
        formatted_env = ''.join(environment.split(' ')).lower()
        self.conn = sf.Connection(formatted_env)
        return self.conn

    def describe(self):
        """Gets Description for object"""
        if self.conn is None:
            raise RuntimeError(
                '%s is not connected to sales force.' % self.name)
        self.desc = sf.Description(self.conn, self.name)
        return self.desc


class SalesForceRecord():
    """Representation of a single record to manipulate"""
    def __init__(self, force_object, **kwargs):
        self.force_object = force_object
        self.sfid = SalesForceField(self, 'Id', None)
        for key, value in kwargs.items():
            setattr(self, key, SalesForceField(self, key, value))

    def add_fields(self, **kwargs):
        """Adds fields to Record"""
        for key, value in kwargs.items():
            print(self.get_field(key))
            if self.get_field(key) is None:
                attr_name = 'sfid' if key == 'Id' else key
                setattr(self, attr_name, SalesForceField(self, key, value))

    def validate(self):
        """Runs pre-insert validation on all fields"""
        checked = self.force_object.desc.pre_insert_check(
            **self.given_values())
        for key, value in checked.items():
            rec_field = self.get_field(key)
            if rec_field is not None:
                setattr(rec_field, 'valid', value)
            else:
                setattr(self, key, SalesForceField(self, key, value, True))

    def fields(self):
        """Returns a list of SalesForceFields in record"""
        all_attrs = [getattr(self, x) for x in dir(self)]
        return [x for x in all_attrs if isinstance(x, SalesForceField)]

    def get_field(self, field_name):
        """Returns SalesForceField given name"""
        found = [x for x in self.fields() if x.name == field_name]
        if len(found) > 0:
            return found[0]
        return None

    def given_values(self):
        """Returns record dict with given values"""
        return {x.name: x.given for x in self.fields() if x.given is not None}

    def valid_values(self):
        """Returns record dict with given values"""
        return {x.name: x.valid for x in self.fields() if x.valid is not None}

    def prepare_update(self, sfid):
        """Adds Id attribute to record, and removes non-changing attributes"""
        current = sf.SOQL(
            self.force_object.conn,
            sobject=self.force_object.desc.name,
            filters=["Id='%s'" % sfid]).get_results()[0]
        for key, value in current.items():
            field = self.get_field(key)
            if field is not None:
                proposed = field.valid
                if proposed == value:
                    field.valid = None
        self.add_sfid(sfid)
        return

    def add_sfid(self, sfid):
        self.sfid.given = sfid
        self.sfid.valid = sfid
        return

    def upsert(self):
        if self.sfid.valid is not None:
            success = self.force_object.desc.update_rec(
                self.sfid.given,
                **self.valid_values())
            if success:
                self.sfid.valid = self.sfid.given
            return (success, self.sfid.given)
        sfid = self.force_object.desc.insert_rec(**self.valid_values())
        if sfid is None:
            return (False, self.force_object.desc.api_responses[-1])
        self.add_sfid(sfid)
        return (True, sfid)

    def find_matches(self, term, result_cols=None):
        """Generates matching record Ids already in SalesForce"""
        default_cols = ['Id', 'Name']
        result_cols = default_cols if result_cols is None else result_cols
        results = sf.SOSL(
            self.force_object.conn,
            terms=[term],
            sobject=self.force_object.desc.name,
            returning_fields=result_cols).get_results()
        return [x for x in results if 'Id' in x.keys()]


class SalesForceField():
    """Representation of a single field in a SalesForceRecord"""
    def __init__(self, parent, name, given, pre_validated=False):
        """If pre_validated, set both valid and given to given"""
        self.parent = parent
        self.name = name
        self.given = given
        self.valid = given if pre_validated else None


# class ReportLocations():
#     def __init__(self, config_file=None):
#         module_dir = os.path.split(__file__)[0]
#         default_loc = os.path.join(module_dir, 'config.json')
#         config_file = config_file if config_file is not None else default_loc
#         self.config_path = config_file
#         self.reports = []
#         self.read_config_file()

#     def create_default_config(self):
#         """Creates default configuration file"""
#         with open(self.config_path, 'w') as f:
#             json.dump(DEFAULT_CONFIG, f, indent=3)

#     def read_config_file(self):
#         if not os.path.isfile(self.config_path):
#             self.create_default_config()
#         with open(self.config_path, 'r') as f:
#             config = json.load(f)
#         reports_dir = config['reports_dir']
#         for name, report in config['reports'].items():
#             report_obj = Report(name)
#             report_path = os.path.join(reports_dir,report.get('sub_dir', ''))
#             report_path = os.path.join(report_path, report['file'])
#             report_obj.set_path(report_path)
#             setattr(self, name, report_obj)
#             self.reports.append(name)


# class Report():
#     def __init__(self, name):
#         self.name = name

#     def set_path(self, path):
#         self.path = path


# class FileLocations():
#     """Provides file locations for data used in package"""
#     def __init__(self):
#         """Parses config.json object and creates PathLike objects"""
#         module_dir = os.path.split(__file__)[0]
#         self.config_path = os.path.join(module_dir, 'config.json')
#         if not os.path.isfile(self.config_path):
#             self.create_default_config()
#         self.report_names = []
#         self.load_config()

#     def create_default_config(self):
#         """Creates default configuration file"""
#         with open(self.config_path, 'w') as f:
#             json.dump(DEFAULT_CONFIG, f, indent=3)

#     def load_config(self):
#         """loads configuration from file at config_path"""
#         with open(self.config_path, 'r') as f:
#             loaded = json.load(f)
#         reports_dir = loaded['reports_dir']
#         self.reports_dir = reports_dir
#         reports = loaded['reports']
#         for name, report in reports.items():
#             sub_dir = os.path.join(reports_dir, report.get('sub_dir', ''))
#             report_path = os.path.join(sub_dir, report['file'])
#             setattr(self, report, report_path)
#             self.report_names.append(report)

#     def valid_report(self, report_name):
#         """Returns Boolean if report name is attr and valid file path"""
#         if not hasattr(self, report_name):
#             return False
#         return os.path.isfile(getattr(self, report_name))

#     def update_config(self):
#         """Sets config file to current config data"""
#         reports = {x: self.make_report_dict(x) for x in self.report_names}
#         new_config = {'reports_dir': self.reports_dir, 'reports': reports}
#         with open(self.config_path, 'w') as f:
#             json.dump(new_config, f, indent=3)

#     def make_report_dict(self, report_name):
#         """Returns dictionary entry for given report name"""
#         if not self.valid_report(report_name):
#             raise RuntimeError("%s is not a valid report." % report_name)
#         r_dir, r_file = os.path.split(getattr(self, report_name))
#         r_sub_dir = r_dir.replace(self.reports_dir + os.sep, '')
#         return {'sub_dir': r_sub_dir, 'file': r_file}

#     def add_report(self, name, new_report_path):
#         """Adds given report and updates config"""
#         if hasattr(self, name):
#             if not getattr(self, name) == new_report_path:
#                 raise RuntimeError('%s already exists.')
#         else:
#             setattr(self, name, new_report_path)
#             self.report_names.append(name)
#         self.update_config()

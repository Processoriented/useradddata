from .parse_raws import RecordSpace
from .main import import_json_dict, report_file_path
import force as sf


LOCN_DEFAULTS = {
    'SVMXC__Stocking_Location__c': True,
    'SVMXC__Location_Type__c': 'Field',
    'HCLS_Active_Location__c': True,
    'SVMXC__Preferred_Business_Hours__c': 'GEHC LS Global Service Team Hours',
    'SVMXC__Service_Engineer__c': None,
    'GEHC_LS_Tech_Owner_Reference__c': None}


TECH_DEFAULTS = {
    'SVMXC__Salesforce_User__c': None,
    'SVMXC__Inventory_Location__c': None,
    'SVMXC__Active__c': True,
    'SVMXC__Street__c': None,
    'SVMXC__City__c': None,
    'SVMXC__Zip__c': None,
    'SVMXC__Country__c': None,
    'SVMXC__Working_Hours__c': None}


STOCK_DEFAULTS = {
    'SVMXC__Status__c': 'Available',
    'SVMXC__Location__c': None}


SER_STOCK_DEFAULTS = {
    'SVMXC__Active__c': True,
    'SVMXC__Product_Stock__c': None,
    'SVMXC__Product__c': None}


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


class PermissionSetSpace(RecordSpace):
    def __init__(self, record, permission_set_id):
        self.fields = ['AssigneeId', 'PermissionSetId']
        self.PermissionSetId = permission_set_id.strip()
        self.AssigneeId = None
        self.stored_permission_label = 'unknown permission set'
        super(PermissionSetSpace, self).__init__(
            record, 'PermissionSetAssignment')

    def get_name(self):
        return "%s permission for %s" % (
            self.stored_permission_label, self.record.user.get_name())

    def set_user_fields(self):
        user_id = self.record.ref.SF_User_Id
        self.AssigneeId = user_id
        self.validate()

    def handle_matches(self):
        filters = ["%s='%s'" % (x, getattr(self, x, '')) for x in self.fields]
        matches = sf.SOQL(
            self.record.conn,
            fields=['Id'],
            sobject=self.sobject,
            filters=filters).get_results()
        if len(matches) > 0:
            self.action = 'Done'

    def validate(self):
        self.valid = self.validate_permissionset() and self.validate_user()

    def user_lookup(self):
        user_id = getattr(self, 'AssigneeId', '')
        return sf.SOQL(
            self.record.conn,
            fields=['Id', 'Username'],
            sobject='User',
            filters=["Id='%s'" % user_id]).get_results()

    def validate_user(self):
        user = self.user_lookup()
        return len(user) > 0

    def validate_permissionset(self):
        permission = self.permissionset_lookup()
        if len(permission) > 0:
            self.stored_permission_label = permission[0]['Label']
            return True
        return False

    def permissionset_lookup(self):
        permission_set_id = getattr(self, 'PermissionSetId', '')
        return sf.SOQL(
            self.record.conn,
            fields=['Id', 'Label'],
            sobject='PermissionSet',
            filters=["Id='%s'" % permission_set_id]).get_results()


class PackageLicenseSpace(RecordSpace):
    def __init__(self, record, package_license_id):
        self.fields = ['UserId', 'PackageLicenseId']
        self.PackageLicenseId = package_license_id
        self.stored_license_namespace = "license %s" % package_license_id
        self.UserId = None
        super(PackageLicenseSpace, self).__init__(
            record, 'UserPackageLicense')

    def get_name(self):
        return "%s license for %s" % (
            self.stored_license_namespace, self.record.user.get_name())

    def set_user_fields(self):
        user_id = self.record.ref.SF_User_Id
        self.UserId = user_id
        self.validate()

    def handle_matches(self):
        filters = ["%s='%s'" % (x, getattr(self, x, '')) for x in self.fields]
        matches = sf.SOQL(
            self.record.conn,
            fields=['Id'],
            sobject=self.sobject,
            filters=filters).get_results()
        if len(matches) > 0:
            self.action = 'Done'

    def validate(self):
        self.valid = self.validate_license() and self.validate_user()

    def validate_user(self):
        return self.record.user.exists_in_force()

    def lookup_license(self):
        package_license_id = getattr(self, 'PackageLicenseId', '')
        return sf.SOQL(
            self.record.conn,
            fields=['Id', 'NamespacePrefix'],
            sobject='PackageLicense',
            filters=["Id='%s'" % package_license_id]).get_results()

    def validate_license(self):
        lookup = self.lookup_license()
        if len(lookup) > 0:
            self.stored_license_namespace = lookup[0]['NamespacePrefix']
            return True
        return False


class LocationSpace(RecordSpace):
    def __init__(self, record, match=None):
        self.matching_terms = ['Name']
        super(LocationSpace, self).__init__(
            record, 'SVMXC__Site__c')
        match = self._get_match() if match is None else match
        self.fields_from_dict(match)
        self.fields_from_dict(LOCN_DEFAULTS)
        self.fields_from_dict(self._get_context_fields())
        self.fields = [x for x in self.fields if x != 'SITE_USE_ID']

    def get_name(self):
        suid = getattr(self, 'SITE_USE_ID', None)
        suid = '' if suid is None else ' (%s)' % suid
        return "%s%s" % (self.Name, suid)

    def validate(self):
        self.fields = [x for x in self.fields if x != 'SITE_USE_ID']
        super(LocationSpace, self).validate()

    @error_if_none('No Location Given')
    def _get_location(self):
        return self.record.ref.Oracle_Location_Number

    @error_if_none('No SubInventory Given')
    def _get_subInventory(self):
        return self.record.ref.Oracle_SubInventory

    def _get_location_name(self):
        return '%s %s - TRUNK STOCK' % (
            self.record.user.FirstName, self.record.user.LastName)

    def _get_context_fields(self):
        return {
            'Oracle_Sub_Inventory__c': self._get_subInventory(),
            'Name': self._get_location_name()}

    def _get_match(self):
        known = import_json_dict(report_file_path('locations'))
        matches = [
            x for x in known
            if x['Location_Number__c'] == self._get_location()]
        if len(matches) == 0:
            matches.extend([
                x for x in known
                if x['Oracle_Ship_to_Number__c'] == self._get_location()])
        match = matches.pop(0)
        for alt in matches:
            self.make_alt_match(alt)
        return match

    def make_alt_match(self, alt):
        try:
            space = LocationSpace(self.record, alt)
            self.record.spaces.append(space)
        except Exception as e:
            pass

    def set_user_fields(self):
        user_id = self.record.ref.SF_User_Id
        self.SVMXC__Service_Engineer__c = user_id
        self.GEHC_LS_Tech_Owner_Reference__c = user_id
        self.validate()


class TechSpace(RecordSpace):
    def __init__(self, record):
        self.matching_terms = ['Name']
        super(TechSpace, self).__init__(
            record, 'SVMXC__Service_Group_Members__c')
        self.fields_from_dict(self._get_context_fields())
        self.fields_from_dict(TECH_DEFAULTS)

    def _get_tech_name(self):
        return "%s %s" % (
            self.record.user.FirstName, self.record.user.LastName)

    def get_name(self):
        return self._get_tech_name()

    def _get_context_fields(self):
        return {
            'Name': self._get_tech_name(),
            'SVMXC__Service_Group__c': self.record.ref.ServiceTeam,
            'SVMXC__Service_Territory__c': self.record.user.Territory__c,
            'SVMXC__Email__c': self.record.user.Email,
            'Global_Region__c': self.record.user.Global_Region__c,
            'Global_Sub_Region__c': self.record.user.Global_Sub_Region__c}

    def set_locn_fields(self):
        locn = self.record.sites[0]
        self.SVMXC__Inventory_Location__c = locn.sfid
        self.SVMXC__Street__c = locn.SVMXC__Street__c
        self.SVMXC__City__c = locn.SVMXC__City__c
        self.SVMXC__Zip__c = locn.SVMXC__Zip__c
        self.SVMXC__Country__c = locn.SVMXC__Country__c
        self.SVMXC__Working_Hours__c = locn.SVMXC__Preferred_Business_Hours__c

    def set_user_fields(self):
        user_id = self.record.ref.SF_User_Id
        self.SVMXC__Salesforce_User__c = user_id


class ProductStockSpace(RecordSpace):
    def __init__(self, record, stock):
        super(ProductStockSpace, self).__init__(
            record, 'SVMXC__Product_Stock__c')
        self.fields_from_dict(STOCK_DEFAULTS)
        self.key = stock.get('key')
        self.ser_stock = []
        self.fields_from_dict({
            k: v for k, v in stock.items()
            if k in ['SVMXC__Product__c', 'SVMXC__Quantity2__c']
            })

    def get_name(self):
        return self.key

    def take_action(self):
        super(ProductStockSpace, self).take_action()
        self.get_ser_stock()
        for ser in self.ser_stock:
            ser.SVMXC__Product_Stock__c = self.sfid
            ser.SVMXC__Product__c = self.SVMXC__Product__c
            ser.validate()
            ser.take_action()

    def get_ser_stock(self):
        sers = list(filter(
            (lambda x: x.get('Key', 'not_a_key') == self.key),
            import_json_dict(report_file_path('ser_stock'))))
        sers = list(filter(
            (lambda x: is_int(x.get('OnHand', None))), sers))
        for ser in sers:
            ser['OnHand'] = int(ser['OnHand']) - self.existing_ser_count()
        sers = list(filter((lambda x: x['OnHand'] > 0), sers))
        for ser in sers:
            self.ser_stock.extend(
                [SerializedStockSpace(self.record, ser)] * ser['OnHand'])

    def existing_ser_count(self):
        filters = "SVMXC__Product_Stock__c='%s'" % self.sfid
        try:
            existing = sf.SOQL(
                self.record.conn,
                fields=["Id"],
                sobject='SVMXC__Product_Serial__c',
                filters=filters).get_results()
            return len(existing)
        except Exception as e:
            print('Error looking up existing stock:\n', str(e))
            print('Please check SF record and enter number found:\n')
            print('%s/%s' % (
                self.record.conn.auth['instance_url'], self.sfid))
            return int(input('Serailized Stock records: '))

    def set_locn_fields(self):
        locn = self.record.sites[0]
        self.SVMXC__Location__c = locn.sfid


class SerializedStockSpace(RecordSpace):
    def __init__(self, record, ser_stock):
        super(SerializedStockSpace, self).__init__(
            record, 'SVMXC__Product_Serial__c')
        self.fields_from_dict(SER_STOCK_DEFAULTS)
        self.fields_from_dict({
            k: v for k, v in ser_stock.items()
            if k in ['Name']
            })

    def get_name(self):
        return self.Name

import force as sf
from .. import main as util
from .main import RecordSpace, error_if_none


LOCN_DEFAULTS = {
    'SVMXC__Stocking_Location__c': True,
    'SVMXC__Location_Type__c': 'Field',
    'HCLS_Active_Location__c': True,
    'SVMXC__Preferred_Business_Hours__c': 'GEHC LS Global Service Team Hours',
    'SVMXC__Service_Engineer__c': None,
    'GEHC_LS_Tech_Owner_Reference__c': None}


def matching_locations(record):
    search_for = record.ref.Oracle_Location_Number
    if search_for in ['', None]:
        return []
    search_fields = ['Location_Number__c', 'Oracle_Ship_to_Number__c']
    known = util.import_json_dict(util.report_file_path('locations'))
    search_fields.extend(
        [k for k in known[0].keys() if k not in search_fields])
    matches = []
    while len(matches) == 0 and len(search_fields) > 0:
        search_field = search_fields.pop(0)
        matches.extend([x for x in known if x[search_field] == search_for])
    return [LocationSpace(record, x) for x in matches]


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
        self.valid_fields.extend(
            [k for k, v in LOCN_DEFAULTS.items() if v is not None])

    def get_name(self):
        suid = getattr(self, 'SITE_USE_ID', None)
        suid = '' if suid is None else ' (%s)' % suid
        return "%s%s" % (self.Name, suid)

    def lookup_biz_hrs(self):
        field_name = 'SVMXC__Preferred_Business_Hours__c'
        findings = sf.SOQL(
            self.record.conn,
            filters=["name = '%s'" % getattr(self, field_name)],
            sobject='BusinessHours').get_results()
        if len(findings) == 0:
            self.valid_fields = [
                x for x in self.valid_fields if x != field_name]
            return
        setattr(self, field_name, findings[0]['Id'])

    def validate(self):
        self.lookup_biz_hrs()
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
        known = util.import_json_dict(util.report_file_path('locations'))
        matches = [
            x for x in known
            if x['Location_Number__c'] == self._get_location()]
        if len(matches) == 0:
            matches.extend([
                x for x in known
                if x['Oracle_Ship_to_Number__c'] == self._get_location()])
        if len(matches) == 0:
            return None
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

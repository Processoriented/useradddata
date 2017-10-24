from .main import RecordSpace


TECH_DEFAULTS = {
    'SVMXC__Salesforce_User__c': None,
    'SVMXC__Inventory_Location__c': None,
    'SVMXC__Role__c': 'Service Engineer',
    'SVMXC__Active__c': True,
    'SVMXC__Street__c': None,
    'SVMXC__City__c': None,
    'SVMXC__Zip__c': None,
    'SVMXC__Country__c': None,
    'SVMXC__Working_Hours__c': None}


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

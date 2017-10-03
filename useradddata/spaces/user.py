from .main import RecordSpace


USER_DEFAULTS = {
    'Business_P_L__c': 'LS Service',
    'Bypass_Custom_Validation__c': False,
    'DefaultGroupNotificationFrequency': 'N',
    'DigestFrequency': 'D',
    'EmailEncodingKey': 'ISO-8859-1',
    'EmailPreferencesAutoBcc': True,
    'EmailPreferencesAutoBccStayInTouch': False,
    'EmailPreferencesStayInTouchReminder': True,
    'ForecastEnabled': False,
    'IsActive': True,
    'ReceivesAdminInfoEmails': False,
    'ReceivesInfoEmails': False,
    'SVMXC__Is_Super_Dispatcher__c': False,
    'SVMXC__ServiceMax_User__c': False,
    'UserPermissionsSupportUser': True,
    'UserPreferencesActivityRemindersPopup': True,
    'UserPreferencesDisableLikeEmail': True,
    'UserPreferencesEventRemindersCheckboxDefault': True,
    'UserPreferencesHideS1BrowserUI': True,
    'UserPreferencesHideSecondChatterOnboardingSplash': True,
    'UserPreferencesSortFeedByComment': True,
    'UserPreferencesTaskRemindersCheckboxDefault': True,
    'UserRoleId': '00E80000001SQpuEAG'
}


FIELDS_FROM_REF = [
    'Username',
    'Alias',
    'CommunityNickname',
    'CurrencyIsoCode',
    'Email',
    'FederationIdentifier',
    'FirstName',
    'Global_Region__c',
    'Global_Sub_Region__c',
    'LanguageLocaleKey',
    'LastName',
    'LocaleSidKey',
    'ManagerId',
    'ProfileId',
    'SSO__c',
    'Territory__c',
    'TimeZoneSidKey'
]


class UserSpace(RecordSpace):
    def __init__(self, parent):
        if not isinstance(getattr(parent, 'ref', None), RecordSpace):
            raise RuntimeError('Record has no reference space.')
        super(UserSpace, self).__init__(
            parent, 'User', **USER_DEFAULTS)
        self.fields_from_dict(
            {x: getattr(self.record.ref, x) for x in FIELDS_FROM_REF})
        expected_terms = ['Username', 'SSO__c']
        self.matching_terms.extend(
            [x for x in expected_terms if getattr(self, x) is not None])
        self.valid_fields.extend([x for x in USER_DEFAULTS.keys()])

    def get_name(self):
        fallback = 'unnamed user'
        return getattr(self, 'Username', getattr(self, 'SSO__c', fallback))

import force as sf
from .main import RecordSpace


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

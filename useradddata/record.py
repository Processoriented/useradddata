import force as sf
from .spaces import (
    RecordSpace,
    UserSpace,
    PermissionSetSpace,
    LocationSpace,
    TechSpace,
    add_stock,
    matching_locations)


def inspect_record(record):
    print('-' * 40)
    print('User Add for %s %s (%s):' % (
        record.ref.FirstName,
        record.ref.LastName,
        record.ref.SSO__c))
    if record.ref.Oracle_Location_Number in ['', None]:
        print('No Oracle Location given.')
    else:
        print('Found %d Oracle recrds matching "%s".' % (
            len(record.sites),
            record.ref.Oracle_Location_Number))
    tech = 0 if record.technician is None else 1
    print('Technician records to add: %d' % tech)
    print('Stock records to add: %d' % len(record.stock))
    print('\n')
    print('-' * 40)


class Record():
    def __init__(self, given):
        parsed_raw = {v['name']: v['value'] for k, v in given.items()}
        self.ref = RecordSpace(self, None, **parsed_raw)
        self.user = UserSpace(self)
        self.permission_sets = self.set_permissionsets()
        self.sites = matching_locations(self)
        self.technician = None
        self.stock = []
        self.conn = self.make_connection()
        if len(self.sites) > 0:
            self.technician = TechSpace(self)
            add_stock(self)
        inspect_record(self)

    def set_permissionsets(self):
        psids = [
            v for k, v in self.ref.to_dict().items() if k[-4:] == 'PSID']
        return [PermissionSetSpace(self, x) for x in psids]

    def make_connection(self):
        env = getattr(self.ref, 'Environment').lower()
        env = ''.join(env.split(' ')).strip()
        return sf.Connection(env)

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
            'sites': [x.to_dict() for x in self.sites],
            'technician': None,
            'stock': [x.to_dict() for x in self.stock]}
        if self.technician is not None:
            rtn['technician'] = self.technician.to_dict()
        return rtn

    def process_user(self):
        self.user.take_action()
        self.ref.SF_User_Id = self.user.sfid
        for space in self.attached_spaces():
            space.set_user_fields()
        for set_ in self.permission_sets:
            set_.take_action()

    def process_sites(self):
        if len(self.sites) == 0:
            return
        selection = 0
        if len(self.sites) > 1:
            print("Choose a site:")
            for idx, site in enumerate(self.sites):
                print("%d.\t%s\t%s\t%s\t%s" % (
                    idx,
                    site.Oracle_Ship_to_Number__c,
                    site.Oracle_Location_ID__c,
                    site.Operating_Unit__c,
                    site.Source_Organization__c))
            selection = int(input())
        site = self.sites[selection]
        self.sites = [site]
        site.take_action()
        self.technician.set_locn_fields()
        for stock in self.stock:
            stock.set_locn_fields()
        self.technician.take_action()
        self.process_stock()

    def process_stock(self):
        if len(self.stock) == 0:
            return
        for stock in self.stock:
            self.technician.take_action()

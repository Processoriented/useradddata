class Action():
    def __init__(self, space, name, desc):
        self.space = space
        self.name = name
        self.description = desc
        self.result = ''

    def to_dict(self):
        return {
            'action': self.name.title(),
            'description': self.description}

    def take_action(self):
        print('No Action defined for %s', self.name.title())
        return False


class InsertAction(Action):
    def __init__(self, space):
        name = 'insert'
        desc = 'Insert new record'
        super(InsertAction, self).__init__(space, name, desc)

    def take_action(self):
        url = '%s/services/data/v40.0/sobjects/%s/' % (
            self.space.record.conn.auth['instance_url'],
            self.space.sobject)
        try:
            response = self.space.record.conn.req_post(
                url, self.space.to_dict())
            setattr(self.space, 'sfid', response['id'])
            setattr(
                self.space,
                'action',
                DoneAction(self.space, 'inserted', True))
            return True
        except Exception as e:
            print(e)
            setattr(
                self.space,
                'action',
                DoneAction(self.space, 'inserted'))
            return False


class UpdateAction(Action):
    def __init__(self, space, sfid):
        name = 'update'
        url = '/'.join([space.record.conn.auth['instance_url'], sfid])
        desc = "Update %s: %s" % (space.sobject, url)
        self.sfid = sfid
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
            setattr(
                self.space,
                'action',
                DoneAction(self.space, 'updated', True))
            return True
        except Exception as e:
            print(e)
            setattr(
                self.space,
                'action',
                DoneAction(self.space, 'updated'))
            return False


class SkipAction(Action):
    def __init__(self, space):
        desc = "Skip %s %s" % (space.sobject, space.get_name())
        super(SkipAction, self).__init__(space, 'skip', desc)

    def take_action(self):
        setattr(
            self.space,
            'action',
            DoneAction(self.space, 'skipped', True))
        return True


class DoneAction(Action):
    def __init__(self, space, previous, success=False):
        desc = 'Successfully' if success else 'Unsuccessfully'
        desc = '%s %s %s: %s' % (
            desc, previous, space.sobject, getattr(space, 'sfid', ''))
        super(DoneAction, self).__init__(space, 'done', desc)

    def take_action(self):
        setattr(self.space, 'action', self)
        return True

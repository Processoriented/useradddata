import force as sf
from .main import RecordSpace, is_int
from ..main import import_json_dict, report_file_path


STOCK_DEFAULTS = {
    'SVMXC__Status__c': 'Available',
    'SVMXC__Location__c': None}


SER_STOCK_DEFAULTS = {
    'SVMXC__Active__c': True,
    'SVMXC__Product_Stock__c': None,
    'SVMXC__Product__c': None}


def add_stock(record):
    subInv = getattr(record.ref, 'Oracle_SubInventory', None)
    if subInv is None:
        return
    known = import_json_dict(report_file_path('prod_stock'))
    record.stock = [
        ProductStockSpace(record, x) for x in known
        if x['Subinventory'] == subInv]


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
        self.valid_fields.append('SVMXC__Status__c')

    def get_name(self):
        return self.key

    def take_action(self):
        super(ProductStockSpace, self).take_action()
        self.get_ser_stock()
        for ser in self.ser_stock:
            ser.SVMXC__Product_Stock__c = self.sfid
            ser.SVMXC__Product__c = self.SVMXC__Product__c
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
        self.valid_fields.append('SVMXC__Active__c')

    def get_name(self):
        return self.Name

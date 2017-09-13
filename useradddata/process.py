from .main import (
    read_user_add_report, import_json_dict, report_file_path)
from .parse_raws import Record
from .sobject_spaces import (
    PermissionSetSpace, PackageLicenseSpace, LocationSpace,
    TechSpace, ProductStockSpace)


def make_records_from_report():
    report = read_user_add_report()
    for result in report['results']:
        record = Record(result)
        add_permissionset_spaces(record)
        add_packagelicense_space(record)
        add_location_space(record)
        add_tech_space(record)
        add_stock(record)
        yield record


def get_reference_value(record, field):
    ref = getattr(record, 'ref', None)
    if ref is None:
        return None
    return getattr(ref, field, None)


def add_permissionset_spaces(record):
    permission_set_ids = [
        get_reference_value(record, 'ServiceMax_Standard_PSID'),
        get_reference_value(record, 'Product_Pricebook_PSID')]
    record.permission_sets.extend([
            PermissionSetSpace(record, x) for x in permission_set_ids
            if x is not None])


def add_packagelicense_space(record):
    license_id = get_reference_value(record, 'PackageLicenseId')
    if license_id is None:
        return
    record.package_licenses.append(
        PackageLicenseSpace(record, license_id))


def add_location_space(record):
    try:
        record.sites.append(LocationSpace(record))
    except Exception as e:
        pass
    return


def add_tech_space(record):
    record.technician = TechSpace(record)


def add_stock(record):
    known = import_json_dict(report_file_path('prod_stock'))
    subInv = get_reference_value(record, 'Oracle_SubInventory')
    record.stock = [
        ProductStockSpace(record, x) for x in known
        if x['Subinventory'] == subInv]


if __name__ == '__main__':
    pass

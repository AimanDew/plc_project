"""Doctype dict-builders for the fabricated/demo ERPNext data.

Each function returns a plain dict shaped for ERPClient.insert_doc /
update_doc - centralizing the field literals that used to be copy-pasted
inline in each fabrication script, so a schema tweak (a new field, a
renamed one) happens in one place.
"""


def bom(item, company, component_item, operation, workstation, time_in_mins,
        component_qty=1.0, uom="Unit", currency="MYR"):

    return {
        "doctype": "BOM",
        "company": company,
        "item": item,
        "quantity": 1.0,
        "uom": uom,
        "currency": currency,
        "buying_price_list": "Standard Buying",
        "rm_cost_as_per": "Valuation Rate",
        "transfer_material_against": "Work Order",
        "with_operations": 1,
        "is_active": 1,
        "is_default": 0,
        "items": [
            {"item_code": component_item, "qty": component_qty, "uom": uom},
        ],
        "operations": [
            {"operation": operation, "workstation": workstation, "time_in_mins": time_in_mins},
        ],
    }


def work_order(company, production_item, bom_no, qty, source_warehouse,
               fg_warehouse, operation, workstation, time_in_mins,
               skip_transfer=True, expected_delivery_date=None, priority=None):

    doc = {
        "doctype": "Work Order",
        "company": company,
        "production_item": production_item,
        "bom_no": bom_no,
        "qty": qty,
        "source_warehouse": source_warehouse,
        "fg_warehouse": fg_warehouse,
        "transfer_material_against": "Work Order",
        "use_multi_level_bom": 1,
        "skip_transfer": 1 if skip_transfer else 0,
        "operations": [
            {"operation": operation, "workstation": workstation, "time_in_mins": time_in_mins},
        ],
    }
    if expected_delivery_date:
        doc["expected_delivery_date"] = expected_delivery_date
    # custom_priority - Custom Field on Work Order (erp_schema/custom_fields/),
    # not a native ERPNext field. See its own description for why it exists.
    if priority:
        doc["custom_priority"] = priority
    return doc


def stock_reconciliation(company, item_code, warehouse, qty, valuation_rate):

    return {
        "doctype": "Stock Reconciliation",
        "company": company,
        "purpose": "Stock Reconciliation",
        "items": [
            {
                "item_code": item_code,
                "warehouse": warehouse,
                "qty": qty,
                "valuation_rate": valuation_rate,
            },
        ],
    }


def workstation(name):

    return {
        "doctype": "Workstation",
        "workstation_name": name,
        "__newname": name,
    }


def plc_tag(tag_name, protocol, address, data_type, workstation, comment="", active=True):

    return {
        "doctype": "PLC Tag",
        "tag_name": tag_name,
        "protocol": protocol,
        "address": address,
        "data_type": data_type,
        "workstation": workstation,
        "comment": comment,
        "active": 1 if active else 0,
    }


def stock_entry_fg_row(item_code, qty, warehouse, rate, uom="Unit"):

    return {
        "item_code": item_code,
        "qty": qty,
        "t_warehouse": warehouse,
        "is_finished_item": 1,
        "basic_rate": rate,
        "uom": uom,
        "stock_uom": uom,
        "conversion_factor": 1.0,
    }

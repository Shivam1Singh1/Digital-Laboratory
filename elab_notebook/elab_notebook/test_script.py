import frappe

def test():
    meta = frappe.get_meta("Employee")
    df = meta.get_field("custom_function_code")
    print("custom_function_code options:", df.options)
    meta_child = frappe.get_meta(df.options)
    print("child fields:", [f.fieldname for f in meta_child.fields])




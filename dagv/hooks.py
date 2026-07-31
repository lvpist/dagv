app_name = "dagv"
app_title = "DAGV"
app_publisher = "DAGV"
app_description = "DAGV — member registration, areas, ranks & provisioning"
app_email = "ti@dagv.local"
app_license = "mit"

# ---------------------------------------------------------------------------
# Document Events — real, reliable app hooks.
# These REPLACE the flaky config-style Server Scripts: as app code they always
# fire (no sandbox, no cache-map issues) and are version-controlled.
# ---------------------------------------------------------------------------
doc_events = {
    "DAGV Registration Request": {
        "before_insert": "dagv.provisioning.validate_fgv_email",
        "on_update": "dagv.provisioning.provision_on_approval",
    }
}

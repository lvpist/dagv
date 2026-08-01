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
    },
    # Raven auto-adds system users but leaves them disabled, which silently
    # breaks workspace/channel membership. Enable them on creation.
    "Raven User": {
        "after_insert": "dagv.provisioning.force_enable_raven_user",
    },
}

# Standard workspaces are rewritten on migrate, so our Home pins and the DAGV
# workspace are re-applied afterwards instead of silently disappearing.
after_migrate = "dagv.setup.after_migrate"

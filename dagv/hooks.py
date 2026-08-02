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
    "DAGV Membership": {
        # A member may ask to join an area; nobody may grant it to themselves.
        "before_insert": "dagv.permissions.guard_membership",
    },
    "Task": {
        # Someone in a single area never has to pick one.
        "before_insert": "dagv.work.set_task_defaults",
        # ...and nobody files work into an area they are not in.
        "validate": "dagv.work.guard_task_area",
    },
    # Raven auto-adds system users but leaves them disabled, which silently
    # breaks workspace/channel membership. Enable them on creation.
    "Raven User": {
        "after_insert": "dagv.provisioning.force_enable_raven_user",
    },
}

# ---------------------------------------------------------------------------
# Row-level access. "Your area is your boundary."
# ---------------------------------------------------------------------------
# Frappe asks two separate questions — which rows go in a list, and may this one
# document be opened — so both have to be answered or the rule has a hole. The
# implementations live together in dagv/permissions.py for exactly that reason.

# The Área picker on a Task offers only the áreas you belong to.
doctype_js = {"Task": "public/js/task.js"}

permission_query_conditions = {
    "DAGV Membership": "dagv.permissions.membership_query",
    "Task": "dagv.permissions.task_query",
    "Project": "dagv.permissions.project_query",
}

has_permission = {
    "DAGV Membership": "dagv.permissions.membership_permission",
    "Task": "dagv.permissions.work_permission",
    "Project": "dagv.permissions.work_permission",
}

# Standard workspaces are rewritten on migrate, so our Home pins and the DAGV
# workspace are re-applied afterwards instead of silently disappearing.
after_migrate = "dagv.setup.after_migrate"

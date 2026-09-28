"""A tiny in-memory user directory used for Demo Bug 1 (None handling)."""

USERS = {
    1: {"name": "Ada Lovelace"},
    2: {"name": "Grace Hopper"},
}


def find_user(user_id):
    """Returns the user dict for user_id, or None if not found."""
    return USERS.get(user_id)


def get_user_name(user_id):
    """Returns the uppercase display name for a user.

    BUG: find_user() can legitimately return None for an unknown user_id,
    but this function accesses user["name"] without checking for that,
    causing an unhandled AttributeError/TypeError for unknown users.
    """
    user = find_user(user_id)
    return user["name"].upper()

# Demo Bug 1 — Null / None Handling Error

**Reported bug:** Looking up an unknown user crashes the application instead of
failing gracefully. `get_user_name()` raises an unhandled error when the user
id does not exist.

**Stack trace:**
```
Traceback (most recent call last):
  File "app/users.py", line 19, in get_user_name
    return user["name"].upper()
TypeError: 'NoneType' object is not subscriptable
```

**Expected root cause:** `find_user()` returns `None` for an unknown id, and
`get_user_name()` does not check for that before indexing into it.

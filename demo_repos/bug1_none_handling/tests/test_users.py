import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.users import get_user_name


def test_get_user_name_known_user():
    assert get_user_name(1) == "ADA LOVELACE"


def test_get_user_name_unknown_user_does_not_crash():
    # An unknown user id must not raise; it should degrade gracefully.
    assert get_user_name(999) == "UNKNOWN"


if __name__ == "__main__":
    # Minimal self-runner so this file is executable even without pytest installed.
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASSED: {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAILED: {t.__name__}: {e}")
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.pricing import apply_discount


def test_ten_percent_discount():
    assert apply_discount(100, 10) == 90


def test_zero_percent_discount():
    assert apply_discount(50, 0) == 50


def test_hundred_percent_discount():
    assert apply_discount(80, 100) == 0


def test_twenty_five_percent_discount():
    assert apply_discount(200, 25) == 150


if __name__ == "__main__":
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

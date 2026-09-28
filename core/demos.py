"""Bundled demo repositories (SRS Section 30)."""
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_ROOT = os.path.join(HERE, "demo_repos")

DEMOS = {
    "bug1": {
        "label": "🧩 Demo 1 · None handling",
        "dir": "bug1_none_handling",
        "blurb": "Unknown user lookup crashes with a NoneType error.",
        "description": "Looking up an unknown user crashes the application instead of failing "
                       "gracefully. get_user_name() raises an unhandled error when the user id does not exist.",
        "stack_trace": 'Traceback (most recent call last):\n  File "app/users.py", line 19, in get_user_name\n'
                       '    return user["name"].upper()\nTypeError: \'NoneType\' object is not subscriptable',
    },
    "bug2": {
        "label": "🧮 Demo 2 · Wrong calculation",
        "dir": "bug2_calc_error",
        "blurb": "Discounts are applied 100× too large (includes a failed first attempt).",
        "description": "Discounted prices are wildly wrong: a 10% discount on a $100 item returns a "
                       "negative price instead of $90.",
        "stack_trace": "",
    },
    "bug3": {
        "label": "🌐 Demo 3 · API error handling",
        "dir": "bug3_api_error",
        "blurb": "Network/HTTP failures leak raw exceptions. README contains a prompt-injection trap.",
        "description": "When the status endpoint is unreachable or returns an error, fetch_status() "
                       "crashes with a raw, confusing exception instead of a clear, handled error.",
        "stack_trace": 'Traceback (most recent call last):\n  File "app/api_client.py", line 15, in fetch_status\n'
                       '    return response.json()["status"]\nKeyError: \'status\'',
    },
}

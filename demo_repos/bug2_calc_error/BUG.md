# Demo Bug 2 — Incorrect Business Logic / Calculation

**Reported bug:** Discounted prices are wildly wrong — a 10% discount on a
$100 item returns a negative price instead of $90.

**Stack trace:** _(none — this is a silent logic error, not a crash)_

**Expected root cause:** `apply_discount()` does not divide the percentage by
100 before applying it, so it treats "10" as "1000%" instead of "10%".

"""Pricing helpers used for Demo Bug 2 (incorrect business logic)."""


def apply_discount(price, percent):
    """Applies a percentage discount to a price.

    BUG: `percent` is a whole number (e.g. 10 means 10%), but this
    implementation treats it as an already-normalized fraction, so a 10%
    discount ends up subtracting 10x the price instead of one tenth of it.
    """
    return price - (price * percent)

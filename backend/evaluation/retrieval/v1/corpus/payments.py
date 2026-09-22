from decimal import Decimal


def refund_payment(amount: Decimal, balance: Decimal) -> Decimal:
    """Return customer funds after a cancelled purchase; reject invalid refunds."""
    if amount <= 0 or amount > balance:
        raise ValueError("Invalid refund")
    return balance - amount


def calculate_invoice_total(prices: list[Decimal], tax_rate: Decimal) -> Decimal:
    """Sum item prices and include sales tax in the invoice total."""
    return sum(prices, Decimal(0)) * (1 + tax_rate)

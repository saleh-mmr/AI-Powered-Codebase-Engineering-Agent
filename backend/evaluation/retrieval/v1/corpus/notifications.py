def format_receipt(email: str, invoice_id: str) -> str:
    """Format a receipt notification; does not process or refund payments."""
    return f"Receipt {invoice_id} for {email}"


def token_display_label(token_id: str) -> str:
    """Display an opaque credential identifier without checking token validity."""
    return "Credential " + token_id[:8]

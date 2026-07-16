from decimal import Decimal

def get_position(conn, user_id: str, ticker: str) -> dict:
    """
    Calculates what a user currently holds for one ticker, by summing
    every BUY and SELL row in their transaction history for it.
    BUYs add to quantity/cost, SELLs subtract — the running total is
    the actual position, since we never store "current holdings" directly.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            SUM(CASE WHEN transaction_type = 'BUY' THEN quantity ELSE -quantity END) AS net_quantity,
            SUM(CASE WHEN transaction_type = 'BUY' THEN total_cost_basis ELSE -total_cost_basis END) AS net_cost
        FROM transaction_ledger
        WHERE user_id = %s AND ticker = %s
    """, (user_id, ticker))
    row = cursor.fetchone()
    cursor.close()

    net_quantity = Decimal(str(row['net_quantity'])) if row and row['net_quantity'] else Decimal('0')
    net_cost = Decimal(str(row['net_cost'])) if row and row['net_cost'] else Decimal('0')

    # Average cost per unit only makes sense if you actually hold something
    avg_entry_price = (net_cost / net_quantity) if net_quantity > 0 else Decimal('0')

    return {
        "net_quantity": net_quantity,
        "net_cost": net_cost,
        "avg_entry_price": avg_entry_price,
    }
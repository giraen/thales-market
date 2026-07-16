from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from decimal import Decimal

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.rules import get_rules
from app.ledger.service import get_position

router = APIRouter(prefix="/api/v1/ledger", tags=["Ledger"])


class BuyOrderRequest(BaseModel):
    ticker: str
    amount_usd: float = Field(gt=0)
    execution_price: float = Field(gt=0)
    fee_applied: float = Field(ge=0)
    asset_class: str = "STOCK"


class SellOrderRequest(BaseModel):
    ticker: str
    quantity: float = Field(gt=0)
    execution_price: float = Field(gt=0)
    fee_applied: float = Field(ge=0)
    asset_class: str = "STOCK"


@router.get("/balance")
def get_balance(user_id: str = Depends(get_current_user), conn = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT unallocated_cash FROM account_balances WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()

    balance = float(row['unallocated_cash']) if row else 0.00
    return {"unallocated_cash": balance}


@router.get("/positions")
def get_positions(user_id: str = Depends(get_current_user), conn = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ticker, asset_class FROM transaction_ledger WHERE user_id = %s", (user_id,))
    tickers = cursor.fetchall()
    cursor.close()

    positions = []
    for row in tickers:
        pos = get_position(conn, user_id, row['ticker'])

        # skip anything fully sold off
        if pos["net_quantity"] > 0:  
            positions.append({
                "ticker": row['ticker'],
                "asset_class": row['asset_class'],
                "quantity_held": float(pos["net_quantity"]),
                "avg_entry_price": float(pos["avg_entry_price"]),
                "total_cost_basis": float(pos["net_cost"]),
            })

    return {"positions": positions}


def _resolve_asset(asset_class: str, ticker: str) -> tuple:
    try:
        rules = get_rules(asset_class)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ticker = ticker.upper()
    if not rules.validate_ticker(ticker):
        raise HTTPException(status_code=400, detail=f"Invalid ticker format for {asset_class}: {ticker}")

    return rules, ticker


@router.post("/buy")
def log_buy(
    order: BuyOrderRequest,
    user_id: str = Depends(get_current_user),
    conn = Depends(get_db)
):
    rules, ticker = _resolve_asset(order.asset_class, order.ticker)

    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO account_balances (user_id, unallocated_cash)
            VALUES (%s, 0.00)
            ON CONFLICT (user_id) DO NOTHING;
        """, (user_id,))

        cursor.execute("""
            SELECT unallocated_cash FROM account_balances
            WHERE user_id = %s FOR UPDATE
        """, (user_id,))
        wallet = cursor.fetchone()
        current_cash = Decimal(str(wallet['unallocated_cash']))

        fee = Decimal(str(order.fee_applied))
        order_cost = Decimal(str(order.amount_usd))
        net_investment = order_cost - fee

        if net_investment <= 0:
            raise HTTPException(status_code=400, detail=f"Amount must cover the ${fee} fee.")

        execution_price = rules.quantize_price(Decimal(str(order.execution_price)))
        if execution_price <= 0:
            raise HTTPException(status_code=400, detail="Execution price rounds to zero at this precision.")

        quantity = rules.quantize_quantity(net_investment / execution_price)
        if quantity <= 0:
            raise HTTPException(status_code=400, detail="Order amount too small to buy a nonzero quantity.")

        new_balance = current_cash - order_cost

        cursor.execute("""
            INSERT INTO transaction_ledger
            (user_id, asset_class, ticker, transaction_type, execution_price, quantity, fee_applied, total_cost_basis)
            VALUES (%s, %s, %s, 'BUY', %s, %s, %s, %s)
            RETURNING id;
        """, (user_id, order.asset_class, ticker, execution_price, quantity, fee, order_cost))
        receipt = cursor.fetchone()

        cursor.execute("""
            UPDATE account_balances
            SET unallocated_cash = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """, (new_balance, user_id))

        # Auto-track this ticker on the watchlist if it isn't already there
        cursor.execute("""
            INSERT INTO watchlist (user_id, ticker, asset_class)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, ticker) DO NOTHING;
        """, (user_id, ticker, order.asset_class))

        conn.commit()

        return {
            "status": "success",
            "receipt_id": receipt['id'],
            "ticker": ticker,
            "quantity_bought": float(quantity),
            "remaining_cash": float(new_balance)
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")
    finally:
        cursor.close()


@router.post("/sell")
def log_sell (
    order: SellOrderRequest,
    user_id: str = Depends(get_current_user),
    conn = Depends(get_db)
):
    rules, ticker = _resolve_asset(order.asset_class, order.ticker)
    
    cursor = conn.cursor()
    try:
        position = get_position(conn, user_id, ticker)
        held_quantity = position["net_quantity"]
        avg_entry_price = position["avg_entry_price"]

        sell_quantity = rules.quantize_quantity(Decimal(str(order.quantity)))
        if sell_quantity <= 0:
            raise HTTPException(status_code=400, detail="Sell quantity rounds to zero at this precision.")

        if sell_quantity > held_quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot sell {sell_quantity} {ticker} — only {held_quantity} held."
            )

        execution_price = rules.quantize_price(Decimal(str(order.execution_price)))
        if execution_price <= 0:
            raise HTTPException(status_code=400, detail="Execution price rounds to zero at this precision.")

        fee = Decimal(str(order.fee_applied))
        gross_proceeds = sell_quantity * execution_price
        net_proceeds = gross_proceeds - fee

        if net_proceeds <= 0:
            raise HTTPException(status_code=400, detail=f"Proceeds must cover the ${fee} fee.")
        
        cost_basis_removed = (avg_entry_price * sell_quantity).quantize(Decimal("0.01"))

        cursor.execute("""
            INSERT INTO account_balances (user_id, unallocated_cash)
            VALUES (%s, 0.00)
            ON CONFLICT (user_id) DO NOTHING;
        """, (user_id,))

        cursor.execute("""
            SELECT unallocated_cash FROM account_balances
            WHERE user_id = %s FOR UPDATE
        """, (user_id,))
        wallet = cursor.fetchone()
        current_cash = Decimal(str(wallet['unallocated_cash']))
        new_balance = current_cash + net_proceeds

        cursor.execute("""
            INSERT INTO transaction_ledger
            (user_id, asset_class, ticker, transaction_type, execution_price, quantity, fee_applied, total_cost_basis)
            VALUES (%s, %s, %s, 'SELL', %s, %s, %s, %s)
            RETURNING id;
        """, (user_id, order.asset_class, ticker, execution_price, sell_quantity, fee, cost_basis_removed))
        receipt = cursor.fetchone()

        cursor.execute("""
            UPDATE account_balances
            SET unallocated_cash = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """, (new_balance, user_id))

        conn.commit()

        return {
            "status": "success",
            "receipt_id": receipt['id'],
            "ticker": ticker,
            "quantity_sold": float(sell_quantity),
            "remaining_held": float(held_quantity - sell_quantity),
            "net_proceeds": float(net_proceeds),
            "realized_pl": float(net_proceeds - cost_basis_removed),
            "new_balance": float(new_balance)
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")
    finally:
        cursor.close()
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
    # create a connection with db
    cursor = conn.cursor()

    # get the remaining cash from the user
    cursor.execute("SELECT unallocated_cash FROM account_balances WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()

    # close the connection with db
    cursor.close()

    # return the remaining balance
    balance = float(row['unallocated_cash']) if row else 0.00
    return {"unallocated_cash": balance}


@router.get("/positions")
def get_positions(user_id: str = Depends(get_current_user), conn = Depends(get_db)):
    # create a connection with db
    cursor = conn.cursor()

    # get all the tickers of stocks you currently owned
    cursor.execute("SELECT DISTINCT ticker, asset_class FROM transaction_ledger WHERE user_id = %s", (user_id,))
    tickers = cursor.fetchall()

    # close the connection with db
    cursor.close()


    positions = []
    for row in tickers:
        # get how many you own
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
    # get the rules for that asset (if stock, options, or crypto)
    # and ticker if it is a valid ticker
    rules, ticker = _resolve_asset(order.asset_class, order.ticker)

    # create a connection with db
    cursor = conn.cursor()
    try:
        # create a new row for user at current cash of 0
        # if user already exists, then skip
        cursor.execute("""
            INSERT INTO account_balances (user_id, unallocated_cash)
            VALUES (%s, 0.00)
            ON CONFLICT (user_id) DO NOTHING;
        """, (user_id,))

        # read user's current cash
        cursor.execute("""
            SELECT unallocated_cash FROM account_balances
            WHERE user_id = %s FOR UPDATE
        """, (user_id,))
        wallet = cursor.fetchone()
        current_cash = Decimal(str(wallet['unallocated_cash']))

        # get the net investment 
        fee = Decimal(str(order.fee_applied))
        order_cost = Decimal(str(order.amount_usd))
        net_investment = order_cost - fee
        if net_investment <= 0:
            raise HTTPException(status_code=400, detail=f"Amount must cover the ${fee} fee.")

        # fixes the decimal precision according to asset rules
        execution_price = rules.quantize_price(Decimal(str(order.execution_price)))
        if execution_price <= 0:
            raise HTTPException(status_code=400, detail="Execution price rounds to zero at this precision.")

        # the actual quantity (shares) you own
        quantity = rules.quantize_quantity(net_investment / execution_price)
        if quantity <= 0:
            raise HTTPException(status_code=400, detail="Order amount too small to buy a nonzero quantity.")

        # new balance after the order
        new_balance = current_cash - order_cost

        # logs the purchase of this asset
        cursor.execute("""
            INSERT INTO transaction_ledger
            (user_id, asset_class, ticker, transaction_type, execution_price, quantity, fee_applied, total_cost_basis)
            VALUES (%s, %s, %s, 'BUY', %s, %s, %s, %s)
            RETURNING id;
        """, (user_id, order.asset_class, ticker, execution_price, quantity, fee, order_cost))
        receipt = cursor.fetchone()

        # update the user's wallet
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

        # like a save point to anything that has happened
        conn.commit()

        return {
            "status": "success",
            "receipt_id": receipt['id'],
            "ticker": ticker,
            "quantity_bought": float(quantity),
            "remaining_cash": float(new_balance)
        }

    except HTTPException:
        # reverts back before any of the changes
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")
    finally:
        # close the connection with db
        cursor.close()


@router.post("/sell")
def log_sell (
    order: SellOrderRequest,
    user_id: str = Depends(get_current_user),
    conn = Depends(get_db)
):
    # get the rules for that asset (if stock, options, or crypto)
    # and ticker if it is a valid ticker
    rules, ticker = _resolve_asset(order.asset_class, order.ticker)
    
    # create a connection with db
    cursor = conn.cursor()
    try:
        # get how many you own
        position = get_position(conn, user_id, ticker)
        held_quantity = position["net_quantity"]
        avg_entry_price = position["avg_entry_price"]

        # checks how many do you want to sell
        sell_quantity = rules.quantize_quantity(Decimal(str(order.quantity)))
        if sell_quantity <= 0:
            raise HTTPException(status_code=400, detail="Sell quantity rounds to zero at this precision.")

        # can't oversell
        if sell_quantity > held_quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot sell {sell_quantity} {ticker} — only {held_quantity} held."
            )

        execution_price = rules.quantize_price(Decimal(str(order.execution_price)))
        if execution_price <= 0:
            raise HTTPException(status_code=400, detail="Execution price rounds to zero at this precision.")

        # checks the profit
        fee = Decimal(str(order.fee_applied))
        gross_proceeds = sell_quantity * execution_price
        net_proceeds = gross_proceeds - fee
        if net_proceeds <= 0:
            raise HTTPException(status_code=400, detail=f"Proceeds must cover the ${fee} fee.")
        
        # for partial sell
        cost_basis_removed = (avg_entry_price * sell_quantity).quantize(Decimal("0.01"))

        cursor.execute("""
            INSERT INTO account_balances (user_id, unallocated_cash)
            VALUES (%s, 0.00)
            ON CONFLICT (user_id) DO NOTHING;
        """, (user_id,))

        # get's the user's current cash and add the profit
        cursor.execute("""
            SELECT unallocated_cash FROM account_balances
            WHERE user_id = %s FOR UPDATE
        """, (user_id,))
        wallet = cursor.fetchone()
        current_cash = Decimal(str(wallet['unallocated_cash']))
        new_balance = current_cash + net_proceeds

        # log the transaction
        cursor.execute("""
            INSERT INTO transaction_ledger
            (user_id, asset_class, ticker, transaction_type, execution_price, quantity, fee_applied, total_cost_basis)
            VALUES (%s, %s, %s, 'SELL', %s, %s, %s, %s)
            RETURNING id;
        """, (user_id, order.asset_class, ticker, execution_price, sell_quantity, fee, cost_basis_removed))
        receipt = cursor.fetchone()

        # update the current user's cash
        cursor.execute("""
            UPDATE account_balances
            SET unallocated_cash = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """, (new_balance, user_id))

        # save point for the db commands
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
        # close the connection with db
        cursor.close()
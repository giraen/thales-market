from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from decimal import Decimal

from app.core.database import get_db
from app.core.security import get_current_user

router = APIRouter(prefix="/api/v1/ledger", tags=["Ledger"])

class BuyOrderRequest(BaseModel):
    ticker: str
    amount_usd: float = Field(gt=0)
    execution_price: float = Field(gt=0)
    fee_applied: float = Field(ge=0)
    asset_class: str = "STOCK"

@router.get("/balance")
def get_balance():
    return {"message": "This will return the $150 balance"}

@router.get("/positions")
def get_positions():
    return {"message": "This will return existing stocks"}

@router.post("/buy")
def log_buy(
    order: BuyOrderRequest,
    user_id: str = Depends(get_current_user),
    conn = Depends(get_db)
):
    cursor = None
    fee = Decimal('0.99')

    try:
        cursor.execute("""
            SELECT unallocated_cash FROM account_balances 
            WHERE user_id = %s FOR UPDATE
        """, (user_id,))

        wallet = cursor.fetchone()

        if not wallet:
            cursor.execute("""
                INSERT INTO account_balances (user_id, unallocated_cash)
                VALUES (%s, 0.00) RETURNING unallocated_cash;
            """, (user_id,))
            current_cash = Decimal('0.00')
        else:
            current_cash = Decimal(str(wallet['unallocated_cash']))

        order_cost = Decimal(str(order.amount_usd))
        net_investment = order_cost - fee

        if net_investment <= 0:
             raise HTTPException(status_code=400, detail="Amount must cover $0.99 fee.")
             
        execution_price = Decimal(str(order.execution_price))
        quantity = net_investment / execution_price
        
        # Calculate new cash (We allow it to go negative for tracking purposes)
        new_balance = current_cash - order_cost
        
        # Write the receipt to the ledger
        cursor.execute("""
            INSERT INTO transaction_ledger 
            (user_id, asset_class, ticker, transaction_type, execution_price, quantity, fee_applied, total_cost_basis)
            VALUES (%s, %s, %s, 'BUY', %s, %s, %s, %s)
            RETURNING id;
        """, (user_id, order.asset_class, order.ticker.upper(), execution_price, quantity, fee, order_cost))
        
        receipt = cursor.fetchone()
        
        # Update the wallet
        cursor.execute("""
            UPDATE account_balances 
            SET unallocated_cash = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """, (new_balance, user_id))
        
        conn.commit()
        
        return {
            "status": "success",
            "receipt_id": receipt['id'],
            "ticker": order.ticker.upper(),
            "quantity_bought": float(quantity),
            "remaining_cash": float(new_balance)
        }
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")
    finally:
        if cursor is not None:
            cursor.close()
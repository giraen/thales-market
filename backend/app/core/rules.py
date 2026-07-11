from decimal import Decimal, ROUND_DOWN
import re

class AssetRules:
    def __init__(self, price_step: Decimal, quantity_step: Decimal, ticker_pattern: str):
        self.price_step = price_step
        self.quantity_step = quantity_step
        self.ticker_pattern = re.compile(ticker_pattern)

    def quantize_price(self, value: Decimal) -> Decimal:
        return value.quantize(self.price_step, rounding=ROUND_DOWN)

    def quantize_quantity(self, value: Decimal) -> Decimal:
        return value.quantize(self.quantity_step, rounding=ROUND_DOWN)

    def validate_ticker(self, ticker: str) -> bool:
        return bool(self.ticker_pattern.match(ticker))


ASSET_RULES = {
    "STOCK": AssetRules(
        price_step=Decimal("0.0001"),
        quantity_step=Decimal("0.000001"),
        ticker_pattern=r"^[A-Z]{1,5}$",
    ),
    "OPTION": AssetRules(
        price_step=Decimal("0.01"),
        quantity_step=Decimal("1"),
        ticker_pattern=r"^[A-Z]{1,5}\d{6}[CP]\d{8}$",
    ),
    "CRYPTO": AssetRules(
        price_step=Decimal("0.00000001"),
        quantity_step=Decimal("0.00000001"),
        ticker_pattern=r"^[A-Z]{2,10}(/[A-Z]{3,4})?$",
    ),
}

def get_rules(asset_class: str) -> AssetRules:
    if asset_class not in ASSET_RULES:
        raise ValueError(f"Unknown asset class: {asset_class}")
    return ASSET_RULES[asset_class]
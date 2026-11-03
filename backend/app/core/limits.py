from decimal import Decimal

# PostgreSQL NUMERIC(18,2) and signed INTEGER storage contracts.
MAX_MONEY = Decimal("9999999999999999.99")
MAX_INTEGER = 2_147_483_647

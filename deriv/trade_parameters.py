from deriv.connect import Connection

market = {
    'derived': {'continuous_indices': ['volatility_10_1s', 'volatility_10']},
    'forex': {},
    'stock_indices': {},
    'commodities': {}
}

trade_type = {
    'up_down': ['rise_fall', 'rise_equals_fall_equals', 'higher_lower']
}

contract_type = ['both', 'rise', 'fall']

class TradeParameters:
    def __init__(self):
        self.conn = Connection()

    async def is_valid_combination(self, market_type, trade_type):
        response = await self.conn.send_request({"available_contracts": 1, "market": market_type})
        valid_types = response.get("available_contracts", {}).get(market_type, [])
        return trade_type in valid_types
class Request:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def balance(self):
        return {"balance": 1}
    
    @property
    def asset_index(self):
        return {"asset_index": 1}
    
    @property
    def active_symbols(self):
        return   {"active_symbols": "full", "product_type": "basic"}
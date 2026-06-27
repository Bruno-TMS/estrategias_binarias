import os


class Settings:
    def __init__(self):
        self.deriv_app_id: str | None = os.getenv("DERIV_APP_ID")
        self.deriv_token: str | None = os.getenv("DERIV_TOKEN")

        if not self.deriv_app_id or not self.deriv_token:
            raise ValueError("DERIV_APP_ID / DERIV_TOKEN não definidos no ENV")


settings = Settings()
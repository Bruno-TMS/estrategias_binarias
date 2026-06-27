from app.services.deriv_service import DerivService

# instância única (reutilizável)
deriv_service = DerivService()


def get_deriv_service() -> DerivService:
    return deriv_service
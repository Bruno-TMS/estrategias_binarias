from services.deriv_service import DerivService

# Instância única compartilhada
deriv_service = DerivService()


def get_deriv_service() -> DerivService:
    """Dependency provider para DerivService."""
    return deriv_service

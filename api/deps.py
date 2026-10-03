from services.deriv_service import DerivService
from services.memory_service import MemoryService
from services.time_operations import TimeOperations, time_operations

# Instâncias únicas compartilhadas
deriv_service = DerivService()
memory_service = MemoryService()


def get_deriv_service() -> DerivService:
    """Dependency provider para DerivService."""
    return deriv_service


def get_memory_service() -> MemoryService:
    """Dependency provider para MemoryService."""
    return memory_service


def get_time_operations() -> TimeOperations:
    """Dependency provider para TimeOperations."""
    return time_operations

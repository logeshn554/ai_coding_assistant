import pytest
from abc import ABC
from agent_os.core.registry import ServiceRegistry

class IService(ABC):
    pass

class MyService(IService):
    pass

def test_service_registry_singleton():
    registry = ServiceRegistry()
    service = MyService()
    
    registry.register_singleton(IService, service)
    resolved = registry.resolve(IService)
    assert resolved is service

def test_service_registry_factory():
    registry = ServiceRegistry()
    registry.register_factory(IService, lambda: MyService())
    
    inst1 = registry.resolve(IService)
    inst2 = registry.resolve(IService)
    assert isinstance(inst1, MyService)
    assert inst1 is not inst2

def test_service_registry_type_safety():
    registry = ServiceRegistry()
    with pytest.raises(TypeError):
        registry.register_singleton(IService, "not_an_implementation")

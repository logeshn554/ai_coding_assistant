import pytest
from abc import ABC
from agent_os.core.interfaces import IServiceRegistry
from agent_os.core.registry import ServiceRegistry
from agent_os.core.di import DIContainer

class IDep(ABC):
    pass

class MyDep(IDep):
    pass

class TargetClass:
    def __init__(self, dep: IDep) -> None:
        self.dep = dep

def test_di_container_auto_wiring():
    registry = ServiceRegistry()
    dep_instance = MyDep()
    registry.register_singleton(IDep, dep_instance)
    
    container = DIContainer(registry)
    resolved_target = container.resolve(TargetClass)
    
    assert isinstance(resolved_target, TargetClass)
    assert resolved_target.dep is dep_instance

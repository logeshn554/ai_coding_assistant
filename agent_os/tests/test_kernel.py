import pytest
from unittest.mock import MagicMock
from agent_os.core.interfaces import IServiceRegistry, IEventBus, IConfig, ILogger
from agent_os.kernel.interfaces import IKernelService
from agent_os.kernel.kernel import Kernel

def test_kernel_lifecycle():
    registry = MagicMock(spec=IServiceRegistry)
    event_bus = MagicMock(spec=IEventBus)
    config = MagicMock(spec=IConfig)
    logger = MagicMock(spec=ILogger)
    
    kernel = Kernel(registry, event_bus, config, logger)
    
    service = MagicMock(spec=IKernelService)
    kernel.register_service("mock_service", service)
    
    # 1. Boot
    kernel.boot()
    service.on_init.assert_called_once()
    
    # 2. Shutdown
    kernel.shutdown()
    service.on_shutdown.assert_called_once()

from typing import Dict
from agent_os.core.interfaces import IServiceRegistry, IEventBus, IConfig, ILogger
from agent_os.kernel.interfaces import IKernel, IKernelService

class Kernel(IKernel):
    """The central AgentOS Operating System Kernel controlling services and resources."""
    def __init__(
        self,
        registry: IServiceRegistry,
        event_bus: IEventBus,
        config: IConfig,
        logger: ILogger
    ) -> None:
        self._registry = registry
        self._event_bus = event_bus
        self._config = config
        self._logger = logger
        self._services: Dict[str, IKernelService] = {}
        self._booted = False

    @property
    def registry(self) -> IServiceRegistry:
        return self._registry

    @property
    def event_bus(self) -> IEventBus:
        return self._event_bus

    @property
    def config(self) -> IConfig:
        return self._config

    @property
    def logger(self) -> ILogger:
        return self._logger

    def register_service(self, name: str, service: IKernelService) -> None:
        self._services[name] = service
        if self._booted:
            self._logger.info(f"Dynamic initialization of service: {name}")
            service.on_init()

    def boot(self) -> None:
        if self._booted:
            return
        self._logger.info("Booting AgentOS Kernel...")
        for name, service in self._services.items():
            self._logger.debug(f"Initializing service: {name}")
            service.on_init()
        self._booted = True
        self._logger.info("AgentOS Kernel successfully booted.")

    def shutdown(self) -> None:
        if not self._booted:
            return
        self._logger.info("Shutting down AgentOS Kernel...")
        for name, service in reversed(list(self._services.items())):
            self._logger.debug(f"Terminating service: {name}")
            service.on_shutdown()
        self._booted = False
        self._logger.info("AgentOS Kernel shutdown complete.")

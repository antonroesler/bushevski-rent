from typing import Dict, Optional
from aws_lambda_powertools import Logger
from services.base import BaseService

logger = Logger()


class ServiceRegistry:
    _instance = None
    _services: Dict[str, BaseService] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServiceRegistry, cls).__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, service_name: str, service_instance: BaseService) -> None:
        """Register a service instance"""
        cls._services[service_name] = service_instance
        logger.debug(f"Registered service: {service_name}")

    @classmethod
    def get(cls, service_name: str) -> Optional[BaseService]:
        """Get a service instance, creating it if necessary"""
        if service_name not in cls._services:
            try:
                if service_name == "payment":
                    from services.payment import PaymentService

                    cls._services[service_name] = PaymentService()
                elif service_name == "booking":
                    from services.booking import BookingService

                    cls._services[service_name] = BookingService()
                elif service_name == "blocked_dates":
                    from services.blocked_dates import BlockedDatesService

                    cls._services[service_name] = BlockedDatesService()
                elif service_name == "pricing":
                    from services.pricing import PricingService

                    cls._services[service_name] = PricingService()
                else:
                    logger.error(f"Unknown service: {service_name}")
                    return None

                logger.debug(f"Lazy loaded service: {service_name}")
            except Exception as e:
                logger.error(f"Error loading service {service_name}: {str(e)}")
                raise

        return cls._services[service_name]

    @classmethod
    def clear(cls) -> None:
        """Clear all registered services (useful for testing)"""
        cls._services.clear()
        logger.debug("Cleared all services")

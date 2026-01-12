"""EasyPost API client wrapper."""

import logging
import os
from dataclasses import dataclass

import easypost

logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exceptions
# ============================================================================

class EasyPostError(Exception):
    """Base exception for EasyPost errors."""

    def __init__(self, message: str, code: str, original_error: Exception | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.original_error = original_error


class RateError(EasyPostError):
    """Error fetching shipping rates."""
    pass


class ShipmentError(EasyPostError):
    """Error creating shipment."""
    pass


class TrackingError(EasyPostError):
    """Error fetching tracking info."""
    pass


class AddressValidationError(EasyPostError):
    """Error validating address."""
    pass


@dataclass
class Address:
    name: str
    street1: str
    city: str
    state: str
    zip_code: str
    country: str = "US"
    street2: str = ""
    phone: str = ""


@dataclass
class Parcel:
    length: float  # inches
    width: float   # inches
    height: float  # inches
    weight: float  # ounces


@dataclass
class Rate:
    carrier: str
    service: str
    rate: float  # dollars
    delivery_days: int | None
    rate_id: str


@dataclass
class Shipment:
    id: str
    tracking_number: str
    label_url: str
    carrier: str
    service: str
    rate: float


class EasyPostClient:
    """Wrapper around EasyPost API."""

    def __init__(self, api_key: str | None = None):
        key = api_key or os.getenv("EASYPOST_API_KEY")
        if not key:
            raise ValueError("EASYPOST_API_KEY not set")
        self.client = easypost.EasyPostClient(key)
        self._load_from_address()

    def _load_from_address(self) -> None:
        """Load default 'from' address from environment."""
        self.from_address = Address(
            name=os.getenv("FROM_NAME", "Shipper"),
            street1=os.getenv("FROM_STREET1", ""),
            city=os.getenv("FROM_CITY", ""),
            state=os.getenv("FROM_STATE", ""),
            zip_code=os.getenv("FROM_ZIP", ""),
            phone=os.getenv("FROM_PHONE", ""),
        )

    def _address_to_dict(self, addr: Address) -> dict:
        return {
            "name": addr.name,
            "street1": addr.street1,
            "street2": addr.street2,
            "city": addr.city,
            "state": addr.state,
            "zip": addr.zip_code,
            "country": addr.country,
            "phone": addr.phone,
        }

    def validate_address(self, address: Address) -> tuple[bool, Address | None, str]:
        """Validate an address.

        Args:
            address: Address to validate

        Returns:
            Tuple of (is_valid, corrected_address, message)

        Raises:
            AddressValidationError: If API call fails (not for invalid addresses)
        """
        try:
            result = self.client.address.create_and_verify(**self._address_to_dict(address))
            corrected = Address(
                name=result.name or address.name,
                street1=result.street1,
                street2=result.street2 or "",
                city=result.city,
                state=result.state,
                zip_code=result.zip,
                country=result.country,
                phone=result.phone or "",
            )
            return True, corrected, "Address is valid"
        except easypost.errors.ApiError as e:
            # Address validation failures are expected - return as invalid
            error_str = str(e)
            # Extract user-friendly message without internal details
            if "E.ADDRESS" in error_str or "address" in error_str.lower():
                return False, None, "Address could not be verified. Please check the address and try again."
            return False, None, "Address validation failed. Please verify the address."
        except Exception as e:
            logger.exception("Unexpected error validating address: %s", e)
            raise AddressValidationError(
                message="An error occurred while validating the address.",
                code="EASYPOST_ADDRESS_ERROR",
                original_error=e,
            )

    def get_rates(
        self,
        to_address: Address,
        parcel: Parcel,
        from_address: Address | None = None,
    ) -> list[Rate]:
        """Get shipping rates for a parcel.

        Args:
            to_address: Destination address
            parcel: Package dimensions and weight
            from_address: Origin address (uses default if not provided)

        Returns:
            List of available rates sorted by price

        Raises:
            RateError: If unable to fetch rates from EasyPost
        """
        from_addr = from_address or self.from_address

        try:
            shipment = self.client.shipment.create(
                from_address=self._address_to_dict(from_addr),
                to_address=self._address_to_dict(to_address),
                parcel={
                    "length": parcel.length,
                    "width": parcel.width,
                    "height": parcel.height,
                    "weight": parcel.weight,
                },
            )
        except easypost.errors.ApiError as e:
            logger.error("EasyPost API error fetching rates: %s", e)
            raise RateError(
                message="Unable to fetch shipping rates. Please verify the address and try again.",
                code="EASYPOST_RATE_ERROR",
                original_error=e,
            )
        except Exception as e:
            logger.exception("Unexpected error fetching rates: %s", e)
            raise RateError(
                message="An error occurred while fetching shipping rates.",
                code="EASYPOST_RATE_ERROR",
                original_error=e,
            )

        rates = []
        for r in shipment.rates:
            rates.append(Rate(
                carrier=r.carrier,
                service=r.service,
                rate=float(r.rate),
                delivery_days=r.delivery_days,
                rate_id=r.id,
            ))

        # Sort by price
        rates.sort(key=lambda x: x.rate)
        return rates

    def create_shipment(
        self,
        to_address: Address,
        parcel: Parcel,
        rate_id: str,
        from_address: Address | None = None,
    ) -> Shipment:
        """Create a shipment and buy a label.

        Args:
            to_address: Destination address
            parcel: Package dimensions and weight
            rate_id: Selected rate ID from get_rates()
            from_address: Origin address (uses default if not provided)

        Returns:
            Shipment with tracking number and label URL

        Raises:
            ShipmentError: If unable to create shipment or purchase label
        """
        from_addr = from_address or self.from_address

        try:
            shipment = self.client.shipment.create(
                from_address=self._address_to_dict(from_addr),
                to_address=self._address_to_dict(to_address),
                parcel={
                    "length": parcel.length,
                    "width": parcel.width,
                    "height": parcel.height,
                    "weight": parcel.weight,
                },
            )
        except easypost.errors.ApiError as e:
            logger.error("EasyPost API error creating shipment: %s", e)
            raise ShipmentError(
                message="Unable to create shipment. Please verify the address and try again.",
                code="EASYPOST_SHIPMENT_ERROR",
                original_error=e,
            )
        except Exception as e:
            logger.exception("Unexpected error creating shipment: %s", e)
            raise ShipmentError(
                message="An error occurred while creating the shipment.",
                code="EASYPOST_SHIPMENT_ERROR",
                original_error=e,
            )

        # Buy the label with the selected rate
        try:
            bought = self.client.shipment.buy(shipment.id, rate=rate_id)
        except easypost.errors.ApiError as e:
            logger.error("EasyPost API error purchasing label: %s", e)
            raise ShipmentError(
                message="Unable to purchase shipping label. The rate may have expired.",
                code="EASYPOST_SHIPMENT_ERROR",
                original_error=e,
            )
        except Exception as e:
            logger.exception("Unexpected error purchasing label: %s", e)
            raise ShipmentError(
                message="An error occurred while purchasing the label.",
                code="EASYPOST_SHIPMENT_ERROR",
                original_error=e,
            )

        return Shipment(
            id=bought.id,
            tracking_number=bought.tracking_code,
            label_url=bought.postage_label.label_url,
            carrier=bought.selected_rate.carrier,
            service=bought.selected_rate.service,
            rate=float(bought.selected_rate.rate),
        )

    def get_tracking(self, tracking_number: str, carrier: str) -> dict:
        """Get tracking info for a shipment.

        Args:
            tracking_number: Tracking number from the carrier
            carrier: Carrier name (e.g., "USPS", "UPS", "FedEx")

        Returns:
            Dictionary with status, estimated delivery, and tracking events

        Raises:
            TrackingError: If unable to fetch tracking information
        """
        try:
            tracker = self.client.tracker.create(
                tracking_code=tracking_number,
                carrier=carrier,
            )
        except easypost.errors.ApiError as e:
            logger.error("EasyPost API error fetching tracking: %s", e)
            # Check if it's an invalid tracking number
            error_str = str(e).lower()
            if "not found" in error_str or "invalid" in error_str:
                raise TrackingError(
                    message="Tracking number not found. Please verify the number is correct.",
                    code="EASYPOST_TRACKING_ERROR",
                    original_error=e,
                )
            raise TrackingError(
                message="Unable to fetch tracking information. Please try again later.",
                code="EASYPOST_TRACKING_ERROR",
                original_error=e,
            )
        except Exception as e:
            logger.exception("Unexpected error fetching tracking: %s", e)
            raise TrackingError(
                message="An error occurred while fetching tracking information.",
                code="EASYPOST_TRACKING_ERROR",
                original_error=e,
            )

        return {
            "status": tracker.status,
            "estimated_delivery": tracker.est_delivery_date,
            "events": [
                {
                    "status": e.status,
                    "message": e.message,
                    "location": f"{e.tracking_location.city}, {e.tracking_location.state}" if e.tracking_location else None,
                    "datetime": e.datetime,
                }
                for e in (tracker.tracking_details or [])
            ],
        }

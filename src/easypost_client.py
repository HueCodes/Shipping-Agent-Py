"""EasyPost API client wrapper."""

import os
from dataclasses import dataclass

import easypost


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
        """
        Validate an address.

        Returns:
            (is_valid, corrected_address, message)
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
            return False, None, str(e)

    def get_rates(
        self,
        to_address: Address,
        parcel: Parcel,
        from_address: Address | None = None,
    ) -> list[Rate]:
        """Get shipping rates for a parcel."""
        from_addr = from_address or self.from_address

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
        """Create a shipment and buy a label."""
        from_addr = from_address or self.from_address

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

        # Buy the label with the selected rate
        bought = self.client.shipment.buy(shipment.id, rate=rate_id)

        return Shipment(
            id=bought.id,
            tracking_number=bought.tracking_code,
            label_url=bought.postage_label.label_url,
            carrier=bought.selected_rate.carrier,
            service=bought.selected_rate.service,
            rate=float(bought.selected_rate.rate),
        )

    def get_tracking(self, tracking_number: str, carrier: str) -> dict:
        """Get tracking info for a shipment."""
        tracker = self.client.tracker.create(
            tracking_code=tracking_number,
            carrier=carrier,
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

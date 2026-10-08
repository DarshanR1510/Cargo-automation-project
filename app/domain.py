"""Air cargo business rules. Read docs/SPEC.md for the plain English version."""
import math
import re

AIRLINE_PREFIX = "607"
MILESTONES = ["BKD", "RCS", "MAN", "DEP", "ARR", "RCF", "NFD", "DLV"]
MILESTONE_NAMES = {
    "BKD": "Booked",
    "RCS": "Received from shipper",
    "MAN": "Manifested",
    "DEP": "Departed",
    "ARR": "Arrived",
    "RCF": "Received from flight",
    "NFD": "Consignee notified",
    "DLV": "Delivered",
    "CAN": "Cancelled",
}
SPECIAL_HANDLING = {"GEN": "General", "DGR": "Dangerous goods", "PER": "Perishable",
                    "PIL": "Pharma", "AVI": "Live animals"}
VOLUMETRIC_DIVISOR = 6000

AWB_PATTERN = re.compile(r"^(\d{3})-(\d{8})$")


def make_awb(serial7: int) -> str:
    """AWB = 3 digit prefix + 7 digit serial + check digit (serial mod 7)."""
    return f"{AIRLINE_PREFIX}-{serial7:07d}{serial7 % 7}"


def is_valid_awb(awb: str) -> bool:
    match = AWB_PATTERN.match(awb or "")
    if not match:
        return False
    serial, check = match.group(2)[:7], match.group(2)[7]
    return int(serial) % 7 == int(check)


def calc_weights(weight_kg: float, length_cm: float, width_cm: float, height_cm: float,
                 buggy: bool = False) -> tuple[float, float]:
    """Returns (volumetric_kg, chargeable_kg).

    Chargeable weight is the higher of actual and volumetric weight,
    rounded UP to the next 0.5 kg.
    """
    volumetric = round(length_cm * width_cm * height_cm / VOLUMETRIC_DIVISOR, 2)
    raw = max(weight_kg, volumetric)
    if buggy:
        chargeable = round(raw * 2) / 2
    else:
        chargeable = math.ceil(raw * 2 - 1e-9) / 2
    return volumetric, chargeable

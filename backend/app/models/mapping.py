from datetime import datetime
from typing import Optional
import json
from sqlmodel import SQLModel, Field


# ── Data Entity Schema ──────────────────────────────────────────────────────
# These are the canonical entities a transactional platform would expose.
# Each entity has a set of well-known attributes. Users can map template
# fields to any entity.attribute path OR supply a static literal value.

ENTITY_SCHEMA = {
    "buyer": {
        "label": "Buyer / Client",
        "attributes": {
            "full_name": "Full legal name",
            "first_name": "First name",
            "last_name": "Last name",
            "email": "Email address",
            "phone": "Phone number",
            "pan_number": "PAN / Tax ID",
            "passport_number": "Passport number",
            "address_line1": "Address line 1",
            "address_line2": "Address line 2",
            "city": "City",
            "state": "State / Province",
            "country": "Country",
            "pincode": "PIN / ZIP code",
        }
    },
    "seller": {
        "label": "Seller / Vendor Company",
        "attributes": {
            "company_name": "Legal company name",
            "brand_name": "Brand / Trade name",
            "registration_number": "Company registration number",
            "gst_number": "GST / VAT number",
            "address_line1": "Registered address line 1",
            "address_line2": "Registered address line 2",
            "city": "City",
            "state": "State",
            "country": "Country",
            "pincode": "PIN / ZIP code",
            "authorized_signatory": "Authorized signatory name",
            "designation": "Signatory designation",
        }
    },
    "property": {
        "label": "Property / Unit",
        "attributes": {
            "unit_number": "Unit / flat number",
            "project_name": "Project / building name",
            "floor_number": "Floor number",
            "tower": "Tower / block",
            "super_area": "Super built-up area (sqft)",
            "carpet_area": "Carpet area (sqft)",
            "survey_number": "Survey / plot number",
            "registration_district": "Registration district",
            "address": "Full property address",
            "city": "City",
            "state": "State",
            "pincode": "PIN code",
        }
    },
    "deal": {
        "label": "Deal / Order",
        "attributes": {
            "deal_id": "Deal / order ID",
            "agreement_date": "Agreement / contract date",
            "booking_date": "Booking date",
            "total_consideration": "Total sale consideration",
            "base_price": "Base price",
            "gst_amount": "GST amount",
            "stamp_duty": "Stamp duty amount",
            "registration_charges": "Registration charges",
            "possession_date": "Estimated possession date",
            "payment_plan": "Payment plan name",
            "currency": "Currency code (INR/USD/EUR)",
        }
    },
    "agent": {
        "label": "Agent / Representative",
        "attributes": {
            "full_name": "Agent full name",
            "employee_id": "Employee / agent ID",
            "designation": "Designation",
            "branch": "Branch / office",
            "phone": "Phone number",
            "email": "Email address",
            "rera_number": "RERA registration number",
        }
    },
    "bank": {
        "label": "Bank / Financier",
        "attributes": {
            "bank_name": "Bank name",
            "branch_name": "Branch name",
            "account_number": "Account number",
            "ifsc_code": "IFSC code",
            "loan_amount": "Sanctioned loan amount",
            "loan_reference": "Loan reference number",
        }
    },
    "witness": {
        "label": "Witness",
        "attributes": {
            "witness1_name": "Witness 1 name",
            "witness1_address": "Witness 1 address",
            "witness2_name": "Witness 2 name",
            "witness2_address": "Witness 2 address",
        }
    },
    "system": {
        "label": "System / Auto",
        "attributes": {
            "today_date": "Today's date (auto-generated)",
            "current_year": "Current year",
            "document_number": "Auto-generated document number",
        }
    }
}


class FieldMapping(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    template_id: int = Field(foreign_key="template.id")
    field_key: str           # matches TemplateField.key
    mapping_type: str        # entity | literal | unmapped
    entity: Optional[str] = None       # e.g. "buyer"
    attribute: Optional[str] = None    # e.g. "full_name"
    literal_value: Optional[str] = None  # static string if mapping_type==literal
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class FieldMappingCreate(SQLModel):
    field_key: str
    mapping_type: str   # entity | literal | unmapped
    entity: Optional[str] = None
    attribute: Optional[str] = None
    literal_value: Optional[str] = None


class FieldMappingRead(SQLModel):
    id: int
    template_id: int
    field_key: str
    mapping_type: str
    entity: Optional[str]
    attribute: Optional[str]
    literal_value: Optional[str]
    created_at: datetime
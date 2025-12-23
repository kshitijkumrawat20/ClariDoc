from pydantic import BaseModel, model_validator,field_validator, HttpUrl, Field
from typing import List, Dict, Any, Optional, Union, Literal

class CommonMetaData(BaseModel):
    # --- Common metadata (across all domains) ---
    # doc_id: Optional[List[str]] = Field(None, description="Unique document identifier")
    doc_category: Optional[List[str]] = Field(None, description="General pool/category e.g. Insurance, HR, Legal")
    doc_type: Optional[List[str]] = Field(None, description="Specific type e.g. Policy doc, Contract, Handbook")
    jurisdiction: Optional[List[str]] = Field(
    default=None, description="Applicable jurisdictions/regions/countries"
    )
    # effective_date: Optional[List[str]] = Field(None, description="Date from which the document is effective")
    # expiry_date: Optional[List[str]] = Field(None, description="Date until which the document is valid")
    parties: Optional[List[str]] = Field(None, description="Involved parties (e.g., employer/employee, insurer/insured)")
    # obligations: Optional[List[str]] = Field(
    #     default=None,
    #     description="List of short, normalized obligation keywords (2–5 words each, no full sentences)"
    # )
    # penalties: Optional[List[str]] = Field(None, description="Penalties/non-compliance consequences")
    # notes: Optional[List[str]] = Field(None, description="Freeform additional metadata")
    # added_new_keyword: bool = False
    added_new_keyword: bool = True
class InsuranceMetadata(CommonMetaData):

    # --- Insurance ---
    policy_number: Optional[List[str]] = None
    coverage_type: Optional[List[str]] = Field(
    default=None,
    description="Type(s) of coverage. Short keywords (1–3 words each)."
    )
    # premium_amount: Optional[List[str]] = None
    exclusions: Optional[List[str]] = Field(
        description="List of normalized keywords representing exclusions (short, 2-5 words each, not full paragraphs).", default=None
    )
    

class HRMetadata(CommonMetaData):
    # --- HR / Employment ---
    policy_type: Optional[str] = None
    applicable_roles: Optional[List[str]] = None
    notice_period: Optional[str] = None

class LegalMetadata(CommonMetaData):

    # --- Legal / Compliance ---
    clause_type: Optional[str] = None
    governing_law: Optional[str] = None
    duration: Optional[str] = None

class FinancialMetadata(CommonMetaData):

    # --- Financial / Regulatory ---
    section: Optional[str] = None
    compliance_requirement: Optional[str] = None
    reporting_frequency: Optional[str] = None

class HealthcareMetadata(CommonMetaData):

    # --- Healthcare / Pharma ---
    disease: Optional[str] = None
    treatment_limit: Optional[str] = None
    validity_period: Optional[str] = None

class ProcurementMetadata(CommonMetaData):

    # --- Procurement / Vendor Management ---
    vendor_name: Optional[str] = None
    contract_value: Optional[str] = None
    payment_terms: Optional[str] = None
    sla_metrics: Optional[List[str]] = None







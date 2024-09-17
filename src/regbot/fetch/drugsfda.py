"""Provide utilities for interacting with Drugs@FDA API endpoint."""

import datetime
import logging
from collections import namedtuple
from enum import Enum

import requests
from requests.exceptions import RequestException

_logger = logging.getLogger(__name__)


Result = namedtuple(
    "Result",
    ("submissions", "application_number", "sponsor_name", "openfda", "products"),
)
Product = namedtuple(
    "Product",
    (
        "product_number",
        "reference_drug",
        "brand_name",
        "active_ingredients",
        "reference_standard",
        "dosage_form",
        "route",
        "marketing_status",
        "te_code",
    ),
)
ActiveIngredient = namedtuple("ActiveIngredient", ("name", "strength"))
ApplicationDoc = namedtuple("ApplicationDoc", ("id", "url", "date", "type"))
Submission = namedtuple(
    "Submission",
    (
        "submission_type",
        "submission_number",
        "submission_status",
        "submission_status_date",
        "review_priority",
        "submission_class_code",
        "submission_class_code_description",
        "application_docs",
    ),
)
OpenFda = namedtuple(
    "OpenFda",
    (
        "application_number",
        "brand_name",
        "generic_name",
        "manufacturer_name",
        "product_ndc",
        "product_type",
        "route",
        "substance_name",
        "rxcui",
        "spl_id",
        "spl_set_id",
        "package_ndc",
        "nui",
        "pharm_class_epc",
        "pharm_class_cs",
        "pharm_class_moa",
        "unii",
    ),
)


class ApplicationDocType(str, Enum):
    """Provide values for application document type."""

    LABEL = "label"
    LETTER = "letter"
    REVIEW = "review"


class ProductMarketingStatus(str, Enum):
    """'Marketing status indicates how a drug product is sold in the United States. Drug
    products in Drugs@FDA are identified as:

    * Prescription
    * Over-the-counter
    * Discontinued
    * None - drug products that have been tentatively approved'

    https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-glossary-terms#marketing_status
    """

    PRESCRIPTION = "prescription"
    OTC = "over_the_counter"
    DISCONTINUED = "discontinued"
    NONE = "none"

    @classmethod
    def _missing_(cls, value):  # noqa: ANN001 ANN206
        try:
            if value.lower() == "over-the-counter":
                return cls.OTC
            msg = f"'{value}' is not a valid {cls.__name__}"
            raise ValueError(msg)
        except AttributeError as _:
            msg = f"'{value}' is not a valid {cls.__name__}"
            raise ValueError(msg) from None


class ProductRoute(str, Enum):
    """Provide values for product routes."""

    ORAL = "oral"
    ORAL_28 = "oral-28"


class ProductDosageForm(str, Enum):
    """'A dosage form is the physical form in which a drug is produced and dispensed,
    such as a tablet, a capsule, or an injectable.'

    https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-glossary-terms#form
    """

    TABLET = "tablet"
    CAPSULE = "capsule"


class ProductTherapeuticEquivalencyCode(str, Enum):
    """See eg https://www.fda.gov/drugs/development-approval-process-drugs/orange-book-preface#TEC"""

    AA = "aa"
    AB = "ab"
    AB1 = "ab1"
    BC = "bc"


class OpenFdaProductType(str, Enum):
    """Define product type."""

    HUMAN_PRESCRIPTION_DRUG = "human_prescription_drug"

    @classmethod
    def _missing_(cls, value):  # noqa: ANN001 ANN206
        try:
            if value.lower() == "human prescription drug":
                return cls.HUMAN_PRESCRIPTION_DRUG
            msg = f"'{value}' is not a valid {cls.__name__}"
            raise ValueError(msg)
        except AttributeError as _:
            msg = f"'{value}' is not a valid {cls.__name__}"
            raise ValueError(msg) from None


class SubmissionType(str, Enum):
    """Provide values for FDA submission type."""

    ORIG = "orig"
    SUPPL = "suppl"


class SubmissionStatus(str, Enum):
    """Provide values for FDA submission status."""

    AP = "ap"


class SubmissionReviewPriority(str, Enum):
    """Provide values for FDA submission review priority rating."""

    STANDARD = "standard"
    PRIORITY = "priority"
    UNKNOWN = "unknown"
    N_A = "n_a"
    REQUIRE_901 = "require 901"

    @classmethod
    def _missing_(cls, value):  # noqa: ANN001 ANN206
        try:
            val_lower = value.lower()
            if val_lower == "n/a":
                return cls.N_A
            if val_lower == "901 required":
                return cls.REQUIRE_901
            msg = f"'{value}' is not a valid {cls.__name__}"
            raise ValueError(msg)
        except AttributeError as _:
            msg = f"'{value}' is not a valid {cls.__name__}"
            raise ValueError(msg) from None


class SubmissionClassCode(str, Enum):
    """Provide values for class code for FDA submission."""

    UNKNOWN = "unknown"
    EFFICACY = "efficacy"
    MANUF_CMC = "manuf_cmc"  # TODO context
    LABELING = "labeling"
    TYPE_1 = "type_1"
    TYPE_2 = "type_2"
    TYPE_3 = "type_3"
    TYPE_4 = "type_4"

    @classmethod
    def _missing_(cls, value):  # noqa: ANN001 ANN206
        try:
            val_lower = value.lower()
            if val_lower == "manuf (cmc)":
                return cls.MANUF_CMC
            if val_lower == "type 1":
                return cls.TYPE_1
            if val_lower == "type 2":
                return cls.TYPE_2
            if val_lower == "type 3":
                return cls.TYPE_3
            if val_lower == "type 4":
                return cls.TYPE_4
            msg = f"'{value}' is not a valid {cls.__name__}"
            raise ValueError(msg)
        except AttributeError as _:
            msg = f"'{value}' is not a valid {cls.__name__}"
            raise ValueError(msg) from None


def _make_truthy(status: str | None) -> bool | str | None:
    if status is None:
        return None
    lower_status = status.lower()
    if lower_status == "no":
        return False
    if lower_status == "yes":
        return True
    _logger.error("Encountered unknown value for converting to bool: %s", status)
    return status


def _enumify(value: str | None, CandidateEnum: type[Enum]) -> Enum | str | None:  # noqa: N803
    if value is None:
        return None
    try:
        return CandidateEnum(value.lower())
    except ValueError:
        _logger.error(
            "Unable to enumify value '%s' into enum '%s'", value, CandidateEnum
        )
        return value


def _intify(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        _logger.error("Cannot convert value '%s' to int", value)
        return None


def _make_datetime(value: str) -> datetime.datetime | None:
    try:
        return datetime.datetime.strptime(value, "%Y%m%d").replace(
            tzinfo=datetime.timezone.utc
        )
    except ValueError:
        _logger.error("Unable to convert value '%s' to datetime", value)
        return None


def _get_product(data: dict, normalize: bool) -> Product:
    reference_drug = (
        _make_truthy(data["reference_drug"]) if normalize else data["reference_drug"]
    )
    reference_standard = (
        _make_truthy(data["reference_standard"])
        if normalize
        else data["reference_standard"]
    )
    dosage_form = (
        _enumify(data["dosage_form"], ProductDosageForm)
        if normalize
        else data["dosage_form"]
    )
    route = (
        _enumify(data["route"], ProductRoute)
        if normalize and "route" in data
        else data.get("route")
    )
    marketing_status = (
        _enumify(data["marketing_status"], ProductMarketingStatus)
        if normalize
        else data["marketing_status"]
    )
    te_code = (
        _enumify(data["te_code"], ProductTherapeuticEquivalencyCode)
        if normalize and "te_code" in data
        else data.get("te_code")
    )
    return Product(
        product_number=data["product_number"],
        reference_drug=reference_drug,
        brand_name=data["brand_name"],
        active_ingredients=[
            ActiveIngredient(**ai) for ai in data["active_ingredients"]
        ],
        reference_standard=reference_standard,
        dosage_form=dosage_form,
        route=route,
        marketing_status=marketing_status,
        te_code=te_code,
    )


def _get_application_docs(data: list[dict], normalize: bool) -> list[ApplicationDoc]:
    return [
        ApplicationDoc(
            id=doc["id"],
            url=doc["url"],
            date=_make_datetime(doc["date"]) if normalize else doc["date"],
            type=_enumify(doc["type"], ApplicationDocType)
            if normalize
            else doc["type"],
        )
        for doc in data
    ]


def _get_submission(data: dict, normalize: bool) -> Submission:
    submission_type = (
        _enumify(data["submission_type"], SubmissionType)
        if normalize
        else data["submission_type"]
    )
    submission_number = (
        _intify(data["submission_number"]) if normalize else data["submission_number"]
    )
    submission_status = (
        _enumify(data["submission_status"], SubmissionStatus)
        if normalize
        else data["submission_status"]
    )
    submission_status_date = (
        _make_datetime(data["submission_status_date"])
        if normalize
        else data["submission_status_date"]
    )
    review_priority = (
        _enumify(data.get("review_priority"), SubmissionReviewPriority)
        if normalize
        else data.get("review_priority")
    )
    submission_class_code = (
        _enumify(data.get("submission_class_code"), SubmissionClassCode)
        if normalize
        else data.get("submission_class_code")
    )
    application_docs = (
        _get_application_docs(data["application_docs"], normalize)
        if "application_docs" in data
        else None
    )

    return Submission(
        submission_type=submission_type,
        submission_number=submission_number,
        submission_status=submission_status,
        submission_status_date=submission_status_date,
        review_priority=review_priority,
        submission_class_code=submission_class_code,
        submission_class_code_description=data.get("submission_class_code_description"),
        application_docs=application_docs,
    )


def _get_openfda(data: dict, normalize: bool) -> OpenFda:
    product_type = [
        _enumify(pt, OpenFdaProductType) if normalize else pt
        for pt in data["product_type"]
    ]
    if "route" in data:
        route = [
            _enumify(rt, ProductRoute) if normalize else rt for rt in data["route"]
        ]
    else:
        route = None
    return OpenFda(
        application_number=data["application_number"],
        brand_name=data["brand_name"],
        generic_name=data["generic_name"],
        manufacturer_name=data["manufacturer_name"],
        product_ndc=data["product_ndc"],
        product_type=product_type,
        route=route,
        substance_name=data.get("substance_name"),
        rxcui=data["rxcui"],
        spl_id=data["spl_id"],
        spl_set_id=data["spl_set_id"],
        package_ndc=data["package_ndc"],
        nui=data.get("nui"),
        pharm_class_epc=data.get("pharm_class_epc"),
        pharm_class_cs=data.get("pharm_class_cs"),
        pharm_class_moa=data.get("pharm_class_moa"),
        unii=data.get("unii"),
    )


def _get_result(data: dict, normalize: bool) -> Result:
    return Result(
        submissions=[_get_submission(s, normalize) for s in data["submissions"]],
        application_number=data["application_number"],
        sponsor_name=data["sponsor_name"],
        openfda=_get_openfda(data["openfda"], normalize),
        products=[_get_product(p, normalize) for p in data["products"]],
    )


def get_drugsfda_results(url: str, normalize: bool = False) -> list[Result] | None:
    """Get Drugs@FDA data given an API query URL.

    :param url: URL to request
    :param normalize: if ``True``, try to normalize values to controlled enumerations
        and appropriate Python datatypes
    :return: list of Drugs@FDA ``Result``s if successful
    :raise RequestException: if HTTP response status != 200
    """
    with requests.get(url, timeout=30) as r:
        try:
            r.raise_for_status()
        except RequestException as e:
            raise e
        data = r.json()
    return [_get_result(r, normalize) for r in data["results"]]


def get_anda_results(anda: str, normalize: bool = False) -> list[Result] | None:
    """Get Drugs@FDA data for an ANDA ID.

    :param anda: ANDA code (should be a six-digit number formatted as a string)
    :param normalize: if ``True``, try to normalize values to controlled enumerations
        and appropriate Python datatypes
    :return: list of Drugs@FDA ``Result``s if successful
    """
    """TODO"""
    url = f"https://api.fda.gov/drug/drugsfda.json?search=openfda.application_number:ANDA{anda}"
    return get_drugsfda_results(url, normalize)


def get_nda_results(nda: str, normalize: bool = False) -> list[Result] | None:
    """Get Drugs@FDA data for an NDA ID.

    :param nda: NDA code (should be a six-digit number formatted as a string)
    :param normalize: if ``True``, try to normalize values to controlled enumerations
        and appropriate Python datatypes
    :return: list of Drugs@FDA ``Result``s if successful
    """
    url = f"https://api.fda.gov/drug/drugsfda.json?search=openfda.application_number:NDA{nda}"
    return get_drugsfda_results(url, normalize)

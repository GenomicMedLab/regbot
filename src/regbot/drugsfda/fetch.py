"""Provide utilities for interacting with Drugs@FDA API endpoint."""

import datetime
import logging
import re
from enum import Enum

import requests
from requests.exceptions import RequestException

from .schema import (
    ActiveIngredient,
    ApplicationDoc,
    ApplicationDocType,
    OpenFda,
    OpenFdaProductType,
    Product,
    ProductDosageForm,
    ProductMarketingStatus,
    ProductRoute,
    ProductTherapeuticEquivalencyCode,
    Result,
    Submission,
    SubmissionClassCode,
    SubmissionReviewPriority,
    SubmissionStatus,
    SubmissionType,
)

_logger = logging.getLogger(__name__)


def _make_truthy(status: str | None) -> bool | str | None:
    if status is None:
        return None
    lower_status = status.lower()
    if lower_status == "no":
        return False
    if lower_status == "yes":
        return True
    if lower_status == "tbd":
        return None
    _logger.error("Encountered unknown value for converting to bool: %s", status)
    return status


def _enumify(value: str | None, CandidateEnum: type[Enum]) -> Enum | str | None:  # noqa: N803
    if value is None:
        return None
    try:
        return CandidateEnum(
            value.lower()
            .replace(", ", "_")
            .replace(" ", "_")
            .replace("-", "_")
            .replace("(", "")
            .replace(")", "")
            .replace("/", "_")
        )
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
        if normalize and ("reference_standard" in data)
        else data.get("reference_standard")
    )
    dosage_form = (
        _enumify(data["dosage_form"], ProductDosageForm)
        if normalize
        else data["dosage_form"]
    )
    raw_route = data.get("route")
    if raw_route is None:
        route = None
    else:
        if isinstance(raw_route, str):
            raw_route = re.split(r", (?!delayed|extended)", raw_route)
        route = (
            [_enumify(r, ProductRoute) for r in raw_route]
            if normalize
            else data["route"]
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
            ActiveIngredient(**ai)
            if "strength" in ai
            else ActiveIngredient(name=ai["name"], strength=None)
            for ai in data["active_ingredients"]
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
        if normalize and ("submission_status" in data)
        else data.get("submission_status")
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
    product_type = (
        [
            _enumify(pt, OpenFdaProductType) if normalize else pt
            for pt in data["product_type"]
        ]
        if "product_type" in data
        else None
    )
    if "route" in data:
        route = [
            _enumify(rt, ProductRoute) if normalize else rt for rt in data["route"]
        ]
    else:
        route = None
    return OpenFda(
        application_number=data.get("application_number"),
        brand_name=data.get("brand_name"),
        generic_name=data.get("generic_name"),
        manufacturer_name=data.get("manufacturer_name"),
        product_ndc=data.get("product_ndc"),
        product_type=product_type,
        route=route,
        substance_name=data.get("substance_name"),
        rxcui=data.get("rxcui"),
        spl_id=data.get("spl_id"),
        spl_set_id=data.get("spl_set_id"),
        package_ndc=data.get("package_ndc"),
        nui=data.get("nui"),
        pharm_class_epc=data.get("pharm_class_epc"),
        pharm_class_cs=data.get("pharm_class_cs"),
        pharm_class_moa=data.get("pharm_class_moa"),
        unii=data.get("unii"),
    )


def _get_result(data: dict, normalize: bool) -> Result:
    return Result(
        submissions=[_get_submission(s, normalize) for s in data["submissions"]]
        if "submissions" in data
        else None,
        application_number=data["application_number"],
        sponsor_name=data["sponsor_name"],
        openfda=_get_openfda(data["openfda"], normalize) if "openfda" in data else None,
        products=[_get_product(p, normalize) for p in data["products"]],
    )


def make_drugsatfda_request(
    url: str, normalize: bool = False, limit: int = 500
) -> list[Result] | None:
    """Get Drugs@FDA data given an API query URL.

    :param url: URL to request
    :param normalize: if ``True``, try to normalize values to controlled enumerations
        and appropriate Python datatypes
    :param limit: # of results per page
    :return: list of Drugs@FDA ``Result``s if successful
    :raise RequestException: if HTTP response status != 200
    """
    results = []
    remaining = True
    skip = 0
    while remaining:
        full_url = f"{url}&limit={limit}&skip={skip}"
        _logger.debug("Issuing GET request to %s", full_url)
        with requests.get(full_url, timeout=30) as r:
            try:
                r.raise_for_status()
            except RequestException as e:
                _logger.warning(
                    "Request to %s returned status code %s", full_url, r.status_code
                )
                raise e
            data = r.json()
        results += data["results"]
        skip = data["meta"]["results"]["skip"] + len(data["results"])
        remaining = (data["meta"]["results"]["total"] > skip) or (skip >= 25000)
    return [_get_result(r, normalize) for r in results]


def fetch_anda_data(anda: str, normalize: bool = False) -> list[Result] | None:
    """Get Drugs@FDA data for an ANDA ID.

    :param anda: ANDA code (should be a six-digit number formatted as a string)
    :param normalize: if ``True``, try to normalize values to controlled enumerations
        and appropriate Python datatypes
    :return: list of Drugs@FDA ``Result``s if successful
    """
    url = f"https://api.fda.gov/drug/drugsfda.json?search=openfda.application_number:ANDA{anda}"
    return make_drugsatfda_request(url, normalize)


def fetch_nda_data(nda: str, normalize: bool = False) -> list[Result] | None:
    """Get Drugs@FDA data for an NDA ID.

    :param nda: NDA code (should be a six-digit number formatted as a string)
    :param normalize: if ``True``, try to normalize values to controlled enumerations
        and appropriate Python datatypes
    :return: list of Drugs@FDA ``Result``s if successful
    """
    url = f"https://api.fda.gov/drug/drugsfda.json?search=openfda.application_number:NDA{nda}"
    return make_drugsatfda_request(url, normalize)

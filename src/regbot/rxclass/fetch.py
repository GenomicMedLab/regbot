"""Fetch data from RxClass API."""

import logging

import requests
from requests.exceptions import RequestException

from .schema import (
    ClassType,
    DrugClassification,
    DrugConcept,
    Relation,
    RelationSource,
    RxClassEntry,
    TermType,
)

_logger = logging.getLogger(__name__)


def _get_concept(concept_raw: dict, normalize: bool) -> DrugConcept:
    return DrugConcept(
        concept_id=f"rxcui:{concept_raw['rxcui']}",
        name=concept_raw["name"],
        term_type=TermType[concept_raw["tty"]] if normalize else concept_raw["tty"],
    )


def _get_classification(
    classification_raw: dict, normalize: bool
) -> DrugClassification:
    return DrugClassification(
        class_id=classification_raw["classId"],
        class_name=classification_raw["className"],
        class_type=ClassType(classification_raw["classType"].lower())
        if normalize
        else classification_raw["classType"],
        class_url=classification_raw.get("classUrl"),
    )


def _get_relation(raw_value: str | None, normalize: bool) -> str | Relation | None:
    if not raw_value:
        return None
    if normalize:
        return Relation(raw_value.lower())
    return raw_value


def _get_relation_source(raw_value: str, normalize: bool) -> str | RelationSource:
    return RelationSource(raw_value.lower()) if normalize else raw_value


def _get_rxclass_entry(drug_info: dict, normalize: bool) -> RxClassEntry:
    return RxClassEntry(
        concept=_get_concept(drug_info["minConcept"], normalize),
        drug_classification=_get_classification(
            drug_info["rxclassMinConceptItem"], normalize
        ),
        relation=_get_relation(drug_info.get("rela"), normalize),
        relation_source=_get_relation_source(drug_info["relaSource"], normalize),
    )


def make_rxclass_request(
    url: str, include_snomedt: bool = False, normalize: bool = False
) -> list[RxClassEntry]:
    """Issue an API request to RxClass.

    :param url: RxClass API URL to request
    :param include_snomedct: if ``True``, include class claims provided by SNOMEDCT.
        These are provided under a different license from the rest of the data and
        may present publishability issues for data consumers.
    :param normalize: if ``True``, try to normalize values to controlled enumerations
        and appropriate Python datatypes
    :return: processed list of drug class descriptions from RxClass
    """
    with requests.get(url, timeout=30) as r:
        try:
            r.raise_for_status()
        except RequestException as e:
            _logger.warning("Request to %s returned status code %s", url, r.status_code)
            raise e
        raw_data = r.json()
    if not raw_data:
        return []
    processed_results = [
        _get_rxclass_entry(entry, normalize)
        for entry in raw_data["rxclassDrugInfoList"]["rxclassDrugInfo"]
    ]
    if not include_snomedt:
        processed_results = [
            r for r in processed_results if r.relation_source != RelationSource.SNOMEDCT
        ]
    return processed_results


def get_drug_class_info(
    drug: str, include_snomedct: bool = False, normalize: bool = False
) -> list[RxClassEntry]:
    """Get RxClass-provided drug info.

    See also RxClass getClassByRxNormDrugName API:
        https://lhncbc.nlm.nih.gov/RxNav/APIs/api-RxClass.getClassByRxNormDrugName.html

    :param drug: RxNorm-provided drug name
    :param include_snomedct: if ``True``, include class claims provided by SNOMEDCT.
        These are provided under a different license from the rest of the data and
        may present publishability issues for data consumers.
    :param normalize: if ``True``, try to normalize values to controlled enumerations
        and appropriate Python datatypes
    :return: list of drug class descriptions from RxClass
    """
    url = (
        f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byDrugName.json?drugName={drug}"
    )
    return make_rxclass_request(url, include_snomedct, normalize)

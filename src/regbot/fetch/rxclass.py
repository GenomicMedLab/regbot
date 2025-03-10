"""Fetch data from RxClass API."""

import logging
from enum import Enum
from typing import NamedTuple

import requests
from requests.exceptions import RequestException

from regbot.fetch.class_utils import map_to_enum

_logger = logging.getLogger(__name__)


class TermType(str, Enum):
    """Define RxNorm term types.

    See https://www.nlm.nih.gov/research/umls/rxnorm/docs/appendix5.html
    """

    IN = "ingredient"
    PIN = "precise_ingredient"
    MIN = "multiple_ingredients"
    SCDC = "semantic_clinical_drug_component"
    SCDF = "semantic_clinical_drug_form"
    SCDFP = "semantic_clinical_drug_form_precise"
    SCDG = "semantic_clinical_drug_group"
    SCDGP = "semantic_clinical_drug_form_group_precise"
    SCD = "semantic_clinical_drug"
    GPCK = "generic_pack"
    BN = "brand_name"
    SBDC = "semantic_branded_drug_component"
    SBDF = "semantic_branded_drug_form"
    SBDFP = "semantic_branded_drug_form_precise"
    SBDG = "semantic_branded_drug_group"
    SBD = "semantic_branded_drug"
    BPCK = "brand_name_pack"
    DF = "dose_form"
    DFG = "dose_form_group"


class DrugConcept(NamedTuple):
    """Define drug concept object."""

    concept_id: str
    name: str
    term_type: TermType


class ClassType(str, Enum):
    """Define drug class types.

    See https://lhncbc.nlm.nih.gov/RxNav/applications/RxClassIntro.html
    """

    ATC1_4 = "atc1-4"
    CHEM = "chem"
    DISEASE = "disease"
    DISPOS = "dispos"
    EPC = "epc"
    MOA = "moa"
    PE = "pe"
    PK = "pk"
    SCHEDULE = "schedule"
    STRUCT = "struct"
    TC = "tc"
    THERAP = "therap"
    VA = "va"


class DrugClassification(NamedTuple):
    """Define drug classification object."""

    class_id: str
    class_name: str
    class_type: ClassType
    class_url: str | None


class Relation(str, Enum):
    """Constrain relation values."""

    IS_A_DISPOSITION = "isa_disposition"
    IS_A_THERAPEUTIC = "isa_therapeutic"
    IS_A_STRUCTURE = "isa_structure"
    HAS_INGREDIENT = "has_ingredient"
    MAY_TREAT = "may_treat"
    HAS_EPC = "has_epc"
    HAS_PE = "has_pe"
    HAS_MOA = "has_moa"
    CI_WITH = "ci_with"
    HAS_VA_CLASS = "has_va_class"
    HAS_VA_CLASS_EXTENDED = "has_va_class_extended"

    @classmethod
    def _missing_(cls, value):  # noqa: ANN001 ANN206
        return map_to_enum(
            cls,
            value,
            {
                "has_vaclass": cls.HAS_VA_CLASS,
                "has_vaclass_extended": cls.HAS_VA_CLASS_EXTENDED,
            },
        )


class RelationSource(str, Enum):
    """Constrain relation source values."""

    ATC = "atc"
    ATCPROD = "atc_prod"
    DAILYMED = "dailymed"
    FDASPL = "fda_spl"
    FMTSME = ("fmtsme",)
    MEDRT = "med_rt"
    RXNORM = "rxnorm"
    SNOMEDCT = "snomedct"
    VA = "va"

    @classmethod
    def _missing_(cls, value):  # noqa: ANN001 ANN206
        return map_to_enum(
            cls,
            value,
            {"atcprod": cls.ATCPROD, "medrt": cls.MEDRT, "fdaspl": cls.FDASPL},
        )


class RxClassEntry(NamedTuple):
    """Define RxClass entry object."""

    concept: DrugConcept
    drug_classification: DrugClassification
    relation: Relation | None
    relation_source: RelationSource | None


def _get_concept(concept_raw: dict) -> DrugConcept:
    return DrugConcept(
        concept_id=f"rxcui:{concept_raw['rxcui']}",
        name=concept_raw["name"],
        term_type=TermType[concept_raw["tty"]],
    )


def _get_classification(classification_raw: dict) -> DrugClassification:
    return DrugClassification(
        class_id=classification_raw["classId"],
        class_name=classification_raw["className"],
        class_type=ClassType(classification_raw["classType"].lower()),
        class_url=classification_raw.get("classUrl"),
    )


def _get_rxclass_entry(drug_info: dict) -> RxClassEntry:
    raw_relation = drug_info.get("rela")
    relation = Relation(raw_relation.lower()) if raw_relation else None
    raw_relation_source = drug_info.get("relaSource")
    relation_source = (
        RelationSource(raw_relation_source.lower()) if raw_relation_source else None
    )
    return RxClassEntry(
        concept=_get_concept(drug_info["minConcept"]),
        drug_classification=_get_classification(drug_info["rxclassMinConceptItem"]),
        relation=relation,
        relation_source=relation_source,
    )


def make_rxclass_request(url: str, include_snomedt: bool = False) -> list[RxClassEntry]:
    """Issue an API request to RxClass.

    :param url: RxClass API URL to request
    :param include_snomedct: if ``True``, include class claims provided by SNOMEDCT.
        These are provided under a different license from the rest of the data and
        may present publishability issues for data consumers.
    :return: processed list of drug class descriptions from RxClass
    """
    with requests.get(url, timeout=30) as r:
        try:
            r.raise_for_status()
        except RequestException:
            _logger.exception(
                "Request to %s returned status code %s", url, r.status_code
            )
            raise
        raw_data = r.json()
    if not raw_data:
        return []
    processed_results = [
        _get_rxclass_entry(entry)
        for entry in raw_data["rxclassDrugInfoList"]["rxclassDrugInfo"]
    ]
    if not include_snomedt:
        processed_results = [
            r for r in processed_results if r.relation_source != RelationSource.SNOMEDCT
        ]
    return processed_results


def get_drug_class_info(
    drug: str, include_snomedct: bool = False
) -> list[RxClassEntry]:
    """Get RxClass-provided drug info.

    See also RxClass getClassByRxNormDrugName API:
        https://lhncbc.nlm.nih.gov/RxNav/APIs/api-RxClass.getClassByRxNormDrugName.html

    :param drug: RxNorm-provided drug name
    :param include_snomedct: if ``True``, include class claims provided by SNOMEDCT.
        These are provided under a different license from the rest of the data and
        may present publishability issues for data consumers.
    :return: list of drug class descriptions from RxClass
    """
    url = (
        f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byDrugName.json?drugName={drug}"
    )
    return make_rxclass_request(url, include_snomedct)

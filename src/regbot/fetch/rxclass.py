"""todo"""

import logging
from collections import namedtuple
from enum import Enum

import requests
from requests.exceptions import RequestException

from regbot.fetch.class_utils import map_to_enum

_logger = logging.getLogger(__name__)


DrugConcept = namedtuple("DrugConcept", ("concept_id", "name", "term_type"))
DrugClassification = namedtuple(
    "DrugClassification", ("class_id", "class_name", "class_type", "class_url")
)
RxClassEntry = namedtuple(
    "RxClassEntry", ("concept", "drug_classification", "relation", "relation_source")
)


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


def _get_concept(concept_raw: dict) -> DrugConcept:
    """TODO"""
    return DrugConcept(
        concept_id=f"rxcui:{concept_raw['rxcui']}",
        name=concept_raw["name"],
        term_type=TermType[concept_raw["tty"]],
    )


def _get_classification(classification_raw: dict) -> DrugClassification:
    """TODO"""
    return DrugClassification(
        class_id=classification_raw["classId"],
        class_name=classification_raw["className"],
        class_type=classification_raw["classType"],
        class_url=classification_raw.get("classUrl"),
    )


def _get_rxclass_entry(drug_info: dict) -> RxClassEntry:
    """Todo"""
    return RxClassEntry(
        concept=_get_concept(drug_info["minConcept"]),
        drug_classification=_get_classification(drug_info["rxclassMinConceptItem"]),
        relation=Relation(drug_info["rela"].lower()) if drug_info["rela"] else None,
        relation_source=RelationSource(drug_info["relaSource"].lower()),
    )


def make_rxclass_request(url: str, include_snomedt: bool = False) -> list[RxClassEntry]:
    """TODO"""
    with requests.get(url, timeout=30) as r:
        try:
            r.raise_for_status()
        except RequestException as e:
            _logger.warning("Request to %s returned status code %s", url, r.status_code)
            raise e
        raw_data = r.json()
    processed_results = [
        _get_rxclass_entry(entry)
        for entry in raw_data["rxclassDrugInfoList"]["rxclassDrugInfo"]
    ]
    if not include_snomedt:
        processed_results = [
            r for r in processed_results if r.relation_source != RelationSource.SNOMEDCT
        ]
    return processed_results


def get_drug_info(drug: str) -> list[RxClassEntry]:
    """TODO"""
    url = (
        f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byDrugName.json?drugName={drug}"
    )
    return make_rxclass_request(url)

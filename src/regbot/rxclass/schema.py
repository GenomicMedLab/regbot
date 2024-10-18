"""Define RxClass object structures."""

from collections import namedtuple
from enum import Enum

from ..normalize_utils import map_to_enum

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

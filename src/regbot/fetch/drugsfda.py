"""Provide utilities for interacting with Drugs@FDA API endpoint."""

import datetime
import logging
import re
from collections import namedtuple
from enum import Enum

import requests
from requests.exceptions import RequestException

from regbot.fetch.class_utils import map_to_enum

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

    AT = "at"
    EXCLUSIVITY_LETTER = "exclusivity_letter"
    FDA_PRESS_RELEASE = "fda_press_release"
    FEDERAL_REGISTER_NOTICE = "federal_register_notice"
    HEALTHCARE_PROFESSIONAL_SHEET = "healthcare_professional_sheet"
    LABEL = "label"
    LETTER = "letter"
    MEDICATION_GUIDE = ("medication_guide",)
    OTHER = "other"
    OTHER_IMPORTANT_INFORMATION_FROM_FDA = "other_important_information_from_fda"
    PATIENT_INFORMATION_SHEET = "patient_information_sheet"
    PATIENT_PACKAGE_INSERT = "patient_package_insert"
    PEDIATRIC_ADDENDUM = "pediatric_addendum"
    PEDIATRIC_AMENDMENT_1 = "pediatric_amendment_1"
    PEDIATRIC_AMENDMENT_2 = "pediatric_amendment_2"
    PEDIATRIC_AMENDMENT_3 = "pediatric_amendment_3"
    PEDIATRIC_AMENDMENT_4 = "pediatric_amendment_4"
    PEDIATRIC_AMENDMENT_5 = "pediatric_amendment_5"
    PEDIATRIC_AMENDMENT_6 = "pediatric_amendment_6"
    PEDIATRIC_AMENDMENT_7 = "pediatric_amendment_7"
    PEDIATRIC_CDTL_REVIEW = "pediatric_cdtl_review"
    PEDIATRIC_CLINICAL_PHARMACOLOGY_ADDENDUM = (
        "pediatric_clinical_pharmacology_addendum"
    )
    PEDIATRIC_CLINICAL_PHARMACOLOGY_REVIEW = "pediatric_clinical_pharmacology_review"
    PEDIATRIC_DD_SUMMARY_REVIEW = "pediatric_dd_summary_review"
    PEDIATRIC_MEDICAL_REVIEW = "pediatric_medical_review"
    PEDIATRIC_MEMO = "pediatric_memo"
    PEDIATRIC_OTHER = "pediatric_other"
    PEDIATRIC_REISSUE = "pediatric_reissue"
    PEDIATRIC_REISSUE_AMENDMENT_1 = "pediatric_reissue_amendment_1"
    PEDIATRIC_REISSUE_AMENDMENT_2 = "pediatric_reissue_amendment_2"
    PEDIATRIC_REISSUE_AMENDMENT_3 = "pediatric_reissue_amendment_3"
    PEDIATRIC_REISSUE_AMENDMENT_4 = "pediatric_reissue_amendment_4"
    PEDIATRIC_REISSUE_AMENDMENT_5 = "pediatric_reissue_amendment_5"
    PEDIATRIC_REISSUE_AMENDMENT_6 = "pediatric_reissue_amendment_6"
    PEDIATRIC_STATISTICAL_REVIEW = "pediatric_statistical_review"
    PEDIATRIC_WRITTEN_REQUEST = "pediatric_written_request"
    REMS = "rems"
    REVIEW = "review"
    SUMMARY_REVIEW = "summary_review"
    WITHDRAWAL_NOTICE = "withdrawal_notice"


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
    NONE_TENTATIVE_APPROVAL = "none_tentative_approval"
    NONE = "none"

    @classmethod
    def _missing_(cls, value):  # noqa: ANN001 ANN206
        return map_to_enum(cls, value, {"over-the-counter": cls.OTC})


class ProductRoute(str, Enum):
    """Provide values for product routes.

    TODO: make compound terms just return multiple individual enums?
    """

    AURICULAR_OTIC = "auricular_otic"
    BILIARY = "biliary"
    BUCCAL = "buccal"
    DENTAL = "dental"
    EPIDURAL = "epidural"
    FOR_RX_COMPOUNDING = "for_rx_compounding"
    IMPLANTATION = "implantation"
    IM_IV = "im_iv"
    INFILTRATION = "infiltration"
    INHALATION = "inhalation"
    INJECTION = "injection"
    INTRAARTERIAL = "intra_arterial"
    INTRACARDIAC = "intracardiac"
    INTRACAUDAL = "intracaudal"
    INTRACAVERNOUS = "intracavernous"
    INTRALESIONAL = "intralesional"
    INTRAMUSCULAR = "intramuscular"
    INTRAOCULAR = "intraocular"
    INTRAPERITONEAL = "intraperitoneal"
    INTRAPLEURAL = "intrapleural"
    INTRASYNOVIAL = "intrasynovial"
    INTRATHECAL = "intrathecal"
    INTRATRACHEAL = "intratracheal"
    INTRAUTERINE = "intrauterine"
    INTRAVASCULAR = "intravascular"
    INTRAVENOUS = "intravenous"
    INTRAVESICAL = "intravesical"
    INTRAVESICULAR = "intravesicular"
    INTRAVITREAL = "intravitreal"
    INTRA_ARTICULAR = "intra_articular"
    IONTOPHORESIS = "iontophoresis"
    IRRIGATION = "irrigation"
    IV_INFUSION = "iv_infusion"
    NASAL = "nasal"
    N_A = "n_a"
    OPHTHALMIC = "ophthalmic"
    ORAL = "oral"
    ORALLY_DISINTEGRATING = "orally_disintegrating"
    ORAL_20 = "oral_20"
    ORAL_21 = "oral_21"
    ORAL_28 = "oral_28"
    OTIC = "otic"
    PARENTERAL = "parenteral"
    PERCUTANEOUS = "percutaneous"
    PERFUSION = "perfusion"
    PERIARTICULAR = "periarticular"
    PERINEURAL = "perineural"
    PERIODONTAL = "periodontal"
    POWDER_FOR_SOLUTION = "powder_for_solution"
    RECTAL = "rectal"
    RESPIRATORY_INHALATION = "respiratory_inhalation"
    SOFT_TISSUE = "soft_tissue"
    SPINAL = "spinal"
    SUBCUTANEOUS = "subcutaneous"
    SUBLINGUAL = "sublingual"
    TOPICAL = "topical"
    TRANSDERMAL = "transdermal"
    TRANSMUCOSAL = "transmucosal"
    URETERAL = "ureteral"
    URETHRAL = "urethral"
    VAGINAL = "vaginal"

    @classmethod
    def _missing_(cls, value):  # noqa: ANN001 ANN206
        return map_to_enum(
            cls,
            value,
            {
                "n/a": cls.N_A,
                "powder,for_solution": cls.POWDER_FOR_SOLUTION,
            },
        )


class ProductDosageForm(str, Enum):
    """'A dosage form is the physical form in which a drug is produced and dispensed,
    such as a tablet, a capsule, or an injectable.'

    https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-glossary-terms#form
    """

    AEROSOL = "aerosol"
    AEROSOL_FOAM = "aerosol_foam"
    AEROSOL_METERED = "aerosol_metered"
    CAPSULE = "capsule"
    CAPSULE_DELAYED_RELEASE = "capsule_delayed_release"
    CAPSULE_DELAYED_REL_PELLETS = "capsule_delayed_rel_pellets"
    CAPSULE_DELAYED_REL_PELLETS_TABLET = "capsule_delayed_rel_pellets_tablet"
    CAPSULE_EXTENDED_RELEASE = "capsule_extended_release"
    CAPSULE_PELLET = "capsule_pellet"
    CAPSULE_PELLETTE = "capsule_pellette"
    CONCENTRATE = "concentrate"
    CREAM = "cream"
    CREAM_AUGMENTED = "cream_augmented"
    CREAM_SUPPOSITORY = "cream_suppository"
    CREAM_TABLET = "cream_tablet"
    DISC = "disc"
    DRESSING = "dressing"
    ELIXIR = "elixir"
    EMULSION = "emulsion"
    ENEMA = "enema"
    FIBER_EXTENDED_RELEASE = "fiber_extended_release"
    FILM = "film"
    FILM_EXTENDED_RELEASE = "film_extended_release"
    FOR_SOLUTION = "for_solution"
    FOR_SUSPENSION = "for_suspension"
    FOR_SUSPENSION_EXTENDED_RELEASE = "for_suspension_extended_release"
    FOR_SUSPENSION_TABLET = "for_suspension_tablet"
    GAS = "gas"
    GEL = "gel"
    GEL_AUGMENTED = "gel_augmented"
    GEL_METERED = "gel_metered"
    GRANULE = "granule"
    GRANULE_EFFERVESCENT = "granule_effervescent"
    GUM_CHEWING = "gum_chewing"
    IMPLANT = "implant"
    INJECTABLE = "injectable"
    INJECTABLE_LIPID_COMPLEX = "injectable_lipid_complex"
    INJECTABLE_LIPOSOMAL = "injectable_liposomal"
    INJECTION = "injection"
    INSERT = "insert"
    INSERT_EXTENDED_RELEASE = "insert_extended_release"
    INTRAUTERINE_DEVICE = "intrauterine_device"
    JELLY = "jelly"
    LIQUID = "liquid"
    LOTION = "lotion"
    LOTION_AUGMENTED = "lotion_augmented"
    LOTION_SHAMPOO = "lotion_shampoo"
    N_A = "n_a"
    OIL = "oil"
    OIL_DROPS = "oil_drops"
    OINTMENT = "ointment"
    PASTE = "paste"
    PASTILLE = "pastille"
    PATCH = "patch"
    POWDER = "powder"
    POWDER_METERED = "powder_metered"
    RING = "ring"
    SHAMPOO = "shampoo"
    SOAP = "soap"
    SOLUTION = "solution"
    SOLUTION_DROPS = "solution_drops"
    SOLUTION_EXTENDED_RELEASE = "solution_extended_release"
    SOLUTION_METERED = "solution_metered"
    SPONGE = "sponge"
    SPRAY = "spray"
    SPRAY_METERED = "spray_metered"
    SUPPOSITORY = "suppository"
    SUSPENSION = "suspension"
    SUSPENSION_DROPS = "suspension_drops"
    SUSPENSION_EXTENDED_RELEASE = "suspension_extended_release"
    SWAB = "swab"
    SYRUP = "syrup"
    SYSTEM = "system"
    SYSTEM_EXTENDED_RELEASE = "system_extended_release"
    TABLET = "tablet"
    TABLET_CHEWABLE = "tablet_chewable"
    TABLET_COATED_PARTICLES = "tablet_coated_particles"
    TABLET_DELAYED_RELEASE = "tablet_delayed_release"
    TABLET_EFFERVESCENT = "tablet_effervescent"
    TABLET_EXTENDED_RELEASE = "tablet_extended_release"
    TABLET_FOR_SUSPENSION = "tablet_for_suspension"
    TABLET_ORALLY_DISINTEGRATING = "tablet_orally_disintegrating"
    TABLET_ORALLY_DISINTEGRATING_EXTENDED_RELEASE = (
        "tablet_orally_disintegrating_extended_release"
    )
    TAMPON = "tampon"
    TROCHE_LOZENGE = "troche_lozenge"
    VIAL = "vial"


class ProductTherapeuticEquivalencyCode(str, Enum):
    """See eg https://www.fda.gov/drugs/development-approval-process-drugs/orange-book-preface#TEC"""

    AA = "aa"
    AB = "ab"
    AB1 = "ab1"
    AB2 = "ab2"
    AB3 = "ab3"
    AB4 = "ab4"
    AN = "an"
    AO = "ao"
    AP = "ap"
    AP1 = "ap1"
    AP2 = "ap2"
    AT = "at"
    AT1 = "at1"
    BC = "bc"
    BS = "bs"
    BT = "bt"
    BX = "bx"
    TBD = "tbd"


class OpenFdaProductType(str, Enum):
    """Define product type."""

    HUMAN_PRESCRIPTION_DRUG = "human_prescription_drug"
    HUMAN_OTC_DRUG = "human_otc_drug"

    @classmethod
    def _missing_(cls, value):  # noqa: ANN001 ANN206
        return map_to_enum(
            cls, value, {"human prescription drug": cls.HUMAN_PRESCRIPTION_DRUG}
        )


class SubmissionType(str, Enum):
    """Provide values for FDA submission type."""

    ORIG = "orig"
    SUPPL = "suppl"


class SubmissionStatus(str, Enum):
    """Provide values for FDA submission status."""

    AP = "ap"
    TA = "ta"


class SubmissionReviewPriority(str, Enum):
    """Provide values for FDA submission review priority rating."""

    STANDARD = "standard"
    PRIORITY = "priority"
    UNKNOWN = "unknown"
    N_A = "n_a"
    REQUIRE_901 = "require_901"
    ORDER_901 = "order_901"

    @classmethod
    def _missing_(cls, value):  # noqa: ANN001 ANN206
        return map_to_enum(
            cls,
            value,
            {
                "n/a": cls.N_A,
                "901_required": cls.REQUIRE_901,
                "901_order": cls.ORDER_901,
            },
        )


class SubmissionClassCode(str, Enum):
    """Provide values for class code for FDA submission."""

    BIOEQUIV = "bioequiv"
    EFFICACY = "efficacy"
    LABELING = "labeling"
    MANUF_CMC = "manuf_cmc"  # TODO context
    MEDGAS = "medgas"
    N_A = "n_a"
    REMS = "rems"
    S = "s"
    TYPE_1 = "type_1"
    TYPE_10 = "type_10"
    TYPE_1_4 = "type_1_4"
    TYPE_2 = "type_2"
    TYPE_2_3 = "type_2_3"
    TYPE_2_4 = "type_2_4"
    TYPE_3 = "type_3"
    TYPE_3_4 = "type_3_4"
    TYPE_4 = "type_4"
    TYPE_4_5 = "type_4_5"
    TYPE_5 = "type_5"
    TYPE_6 = "type_6"
    TYPE_7 = "type_7"
    TYPE_8 = "type_8"
    TYPE_9 = "type_9"
    UNKNOWN = "unknown"


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
        return datetime.datetime.strptime(value, "%Y%m%d").replace(tzinfo=datetime.UTC)
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


def get_anda_results(anda: str, normalize: bool = False) -> list[Result] | None:
    """Get Drugs@FDA data for an ANDA ID.

    :param anda: ANDA code (should be a six-digit number formatted as a string)
    :param normalize: if ``True``, try to normalize values to controlled enumerations
        and appropriate Python datatypes
    :return: list of Drugs@FDA ``Result``s if successful
    """
    url = f"https://api.fda.gov/drug/drugsfda.json?search=openfda.application_number:ANDA{anda}"
    return make_drugsatfda_request(url, normalize)


def get_nda_results(nda: str, normalize: bool = False) -> list[Result] | None:
    """Get Drugs@FDA data for an NDA ID.

    :param nda: NDA code (should be a six-digit number formatted as a string)
    :param normalize: if ``True``, try to normalize values to controlled enumerations
        and appropriate Python datatypes
    :return: list of Drugs@FDA ``Result``s if successful
    """
    url = f"https://api.fda.gov/drug/drugsfda.json?search=openfda.application_number:NDA{nda}"
    return make_drugsatfda_request(url, normalize)

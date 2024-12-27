"""Fetch data from FDA Clinical Trials API.

See
* API description: https://clinicaltrials.gov/data-api/api
* Bioregistry entry: https://bioregistry.io/registry/clinicaltrials


..code-block:: pycon

    >>> results = get_clinical_trials("imatinib")
    >>> results[0].protocol.identification.nct_id
    'clinicaltrials:NCT00769782'
    >>> len(results)
    755

Filter studies by age criteria:

..code-block:: pycon

    >>> import datetime
    >>> ped_age = datetime.timedelta(365 * 24 * 60 * 60 * 18)
    >>> pediatric_studies = [
    ...     r
    ...     for r in results
    ...     if r.protocol.eligibility
    ...     and r.protocol.eligibility.max_age
    ...     and r.protocol.eligibility.max_age < ped_age
    ... ]

Get all serious adverse events:

.. code-block:: pycon

    >>> serious_events = []
    >>> for r in results:
    >>>     if f.results and r.results.adverse_events and r.results.adverse_events.serious_events:
    >>>          serious_events.append(event.term)
    >>> serious_events[:3]
    ['ANAEMIA', 'AUTOIMMUNE HAEMOLYTIC ANAEMIA', 'EVANS SYNDROME']

"""

import datetime
import logging
from collections import namedtuple
from enum import StrEnum
from typing import NamedTuple

import requests
from requests.exceptions import RequestException

from .class_utils import map_to_enum

_logger = logging.getLogger(__name__)


def _get_dt_object(raw_date: str) -> datetime.datetime:
    """Extract datetime object from raw date.

    :param raw_date: raw string from JSON response
    :return: structured datetime instance depending on available data
    """
    try:
        return datetime.datetime.strptime(raw_date, "%Y-%m-%d").replace(
            tzinfo=datetime.UTC
        )
    except ValueError:
        try:
            return datetime.datetime.strptime(raw_date, "%Y-%m").replace(
                tzinfo=datetime.UTC
            )
        except ValueError:
            try:
                return datetime.datetime.strptime(raw_date, "%Y").replace(
                    tzinfo=datetime.UTC
                )
            except ValueError as e:
                msg = f"Unable to format {raw_date} as YYYY-MM-DD, YYYY-MM, or YYYY"
                _logger.error(msg)
                raise ValueError(msg) from e


ProtocolIdentification = namedtuple(
    "ProtocolIdentification",
    (
        "nct_id",
        "nct_id_aliases",
        "org_id",
        "secondary_org_ids",
        "brief_title",
        "official_title",
        "organization",
    ),
)
Organization = namedtuple("Organization", ("full_name", "org_class"))
OrgStudyId = namedtuple("OrgStudyId", ("id", "id_type", "link", "domain"))


class AgencyClass(StrEnum):
    """Define valid agency class descriptions

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#enum-AgencyClass
    """

    NIH = "nih"
    FED = "fed"
    OTHER_GOV = "other_gov"
    INDIV = "indiv"
    INDUSTRY = "industry"
    NETWORK = "network"
    AMBIG = "ambig"
    OTHER = "other"
    UNKNOWN = "unknown"


def _format_protocol_id(id_input: dict) -> ProtocolIdentification:
    """Format ProtocolSection.IdentificationModule

    See
    * https://clinicaltrials.gov/policy/protocol-definitions#identification
    * https://clinicaltrials.gov/data-api/about-api/study-data-structure#IdentificationModule

    :param id_input: raw module input
    :return: structured output
    """
    org_study_id_input = id_input.get("orgStudyIdInfo")
    if org_study_id_input:
        org_study_id = OrgStudyId(
            id=org_study_id_input["id"],
            id_type=org_study_id_input.get("orgStudyIdType"),
            link=org_study_id_input.get("orgStudyIdLink"),
            domain=org_study_id_input.get(""),
        )
        secondary_ids = [
            OrgStudyId(
                id=secondary["secondaryId"],
                id_type=secondary["secondaryIdType"],
                link=secondary["secondaryIdLink"],
                domain=secondary["secondaryIdDomain"],
            )
            for secondary in org_study_id_input.get("secondaryIdInfo", [])
        ]
    else:
        org_study_id, secondary_ids = None, None
    return ProtocolIdentification(
        nct_id=f"clinicaltrials:{id_input['nctId']}",
        nct_id_aliases=id_input.get("nctIdAlias"),
        org_id=org_study_id,
        secondary_org_ids=secondary_ids,
        brief_title=id_input["briefTitle"],
        official_title=id_input.get("officialTitle"),
        organization=Organization(
            full_name=id_input["organization"]["fullName"],
            org_class=AgencyClass(id_input["organization"]["class"].lower())
            if id_input.get("organization", {}).get("class")
            else None,
        ),
    )


class Status(StrEnum):
    """Define valid study status values

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#enum-Status
    """

    ACTIVE_NOT_RECRUITING = "active_not_recruiting"
    COMPLETED = "completed"
    ENROLLING_BY_INVITATION = "enrolling_by_invitation"
    NOT_YET_RECRUITING = "not_yet_recruiting"
    RECRUITING = "recruiting"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    WITHDRAWN = "withdrawn"
    AVAILABLE = "available"
    NO_LONGER_AVAILABLE = "no_longer_available"
    TEMPORARILY_NOT_AVAILABLE = "temporarily_not_available"
    APPROVED_FOR_MARKETING = "approved_for_marketing"
    WITHHELD = "withheld"
    UNKNOWN = "unknown"


ProtocolStatus = namedtuple(
    "ProtocolStatus",
    (
        "overall_status",
        "last_known_status",
        "delayed_posting",
        "why_stopped",
        "expanded_access_info",
        "dates",
        "results_waived",
    ),
)

ExpandedAccessInfo = namedtuple(
    "ExpandedAccessInfo",
    (
        "has_expanded_access",
        "nct_id",
        "status_for_nct_id",
    ),
)

ProtocolStatusDates = namedtuple(
    "ProtocolStatusDates",
    (
        "start_date",
        "start_date_type",
        "primary_completion_date",
        "primary_completion_date_type",
        "completion_date",
        "completion_date_type",
        "study_first_submit_date",
        "results_first_submit_date",
        "last_update_submit_date",
    ),
)


class DateType(StrEnum):
    """Define valid date type descriptions

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#enum-DateType
    """

    ACTUAL = "actual"
    ESTIMATED = "estimated"


def _format_protocol_status_dates(status_input: dict) -> ProtocolStatusDates:
    """Structure dates from ProtocolSection.StatusModule

    :param status_input: StatusModule JSON
    :return: structured dates data
    """
    if "primaryCompletionDateStruct" in status_input:
        primary_completion_date = _get_dt_object(
            status_input["primaryCompletionDateStruct"]["date"]
        )
        primary_completion_date_type = (
            DateType(status_input["primaryCompletionDateStruct"]["type"].lower())
            if "type" in status_input["primaryCompletionDateStruct"]
            else None
        )
    else:
        primary_completion_date, primary_completion_date_type = None, None

    if "completionDateStruct" in status_input:
        completion_date = _get_dt_object(status_input["completionDateStruct"]["date"])
        completion_date_type = (
            DateType(status_input["completionDateStruct"]["type"].lower())
            if "type" in status_input["completionDateStruct"]
            else None
        )
    else:
        completion_date, completion_date_type = None, None

    if "startDateStruct" in status_input:
        start_date = _get_dt_object(status_input["startDateStruct"]["date"])
        start_date_type = (
            DateType(status_input["startDateStruct"]["type"].lower())
            if "type" in status_input["startDateStruct"]
            else None
        )
    else:
        start_date, start_date_type = None, None
    return ProtocolStatusDates(
        start_date=start_date,
        start_date_type=start_date_type,
        primary_completion_date=primary_completion_date,
        primary_completion_date_type=primary_completion_date_type,
        completion_date=completion_date,
        completion_date_type=completion_date_type,
        study_first_submit_date=_get_dt_object(status_input["studyFirstSubmitDate"])
        if "studyFirstSubmitDate" in status_input
        else None,
        results_first_submit_date=_get_dt_object(status_input["resultsFirstSubmitDate"])
        if "resultsFirstSubmitDate" in status_input
        else None,
        last_update_submit_date=_get_dt_object(status_input["lastUpdateSubmitDate"])
        if "lastUpdateSubmitDate" in status_input
        else None,
    )


def _format_status(status_input: dict) -> ProtocolStatus:
    """Structure ProtocolSection.StatusModule

    See
    * https://clinicaltrials.gov/policy/protocol-definitions#status
    * https://clinicaltrials.gov/data-api/about-api/study-data-structure#StatusModule

    :param status_input: raw StatusModule input
    :return: structured data
    """
    expanded_access_info_input = status_input.get("expandedAccessInfo")
    expanded_access_info = (
        ExpandedAccessInfo(
            has_expanded_access=expanded_access_info_input.get("hasExpandedAccess"),
            nct_id=expanded_access_info_input.get("expandedAccessNCTId"),
            status_for_nct_id=expanded_access_info_input.get(
                "expandedAccessStatusForNCTId"
            ),
        )
        if expanded_access_info_input
        else None
    )
    return ProtocolStatus(
        overall_status=Status(status_input["overallStatus"].lower())
        if "overallStatus" in status_input
        else None,
        last_known_status=Status(status_input["lastKnownStatus"].lower())
        if "lastKnownStatus" in status_input
        else None,
        delayed_posting=status_input.get("delayedPosting"),
        why_stopped=status_input.get("whyStopped"),
        results_waived=status_input.get("resultsWaived"),
        expanded_access_info=expanded_access_info,
        dates=_format_protocol_status_dates(status_input),
    )


SponsorCollaborators = namedtuple(
    "SponsorCollaborators", ("lead_sponsor_name", "lead_sponsor_class")
)


def _format_sponsor_collaborators(spo_collab: dict) -> SponsorCollaborators:
    """Format ProtocolSection.SponsorCollaboratorsModule

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#SponsorCollaboratorsModule

    :param spo_collab: raw JSON
    :return: structured output
    """
    return SponsorCollaborators(
        lead_sponsor_name=spo_collab["leadSponsor"]["name"],
        lead_sponsor_class=AgencyClass(spo_collab["leadSponsor"]["class"].lower())
        if spo_collab.get("leadSponsor", {}).get("class")
        else None,
    )


Oversight = namedtuple(
    "Oversight",
    (
        "has_dmc",
        "is_fda_regulated_drug",
        "is_fda_regulated_device",
        "is_unapproved_device",
        "is_ppsd",
    ),
)


def _format_oversight(oversight_input: dict) -> Oversight:
    """Format ProtocolSection.OversightModule

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#OversightModule

    :param oversight_input: raw JSON
    :return: structured data
    """
    return Oversight(
        has_dmc=oversight_input.get("oversightHasDmc"),
        is_fda_regulated_drug=oversight_input.get("isFdaRegulatedDrug"),
        is_fda_regulated_device=oversight_input.get("isFdaRegulatedDevice"),
        is_unapproved_device=oversight_input.get("isUnapprovedDevice"),
        is_ppsd=oversight_input.get("isPPSD"),
    )


Description = namedtuple("Description", ("summary", "detailed"))


def _format_description(descr_input: dict) -> Description:
    """Format ProtocolSection.DescriptionModule

    see https://clinicaltrials.gov/data-api/about-api/study-data-structure#DescriptionModule

    :param descr_input: raw JSON
    :return: structured output
    """
    return Description(
        summary=descr_input.get("briefSummary"),
        detailed=descr_input.get("detailedDescription"),
    )


ProtocolConditions = namedtuple("ProtocolConditions", ("conditions", "keywords"))


Enrollment = namedtuple("Enrollment", ("count", "type"))


class StudyType(StrEnum):
    """Define valid study type terms

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#enum-StudyType
    """

    EXPANDED_ACCESS = "expanded_access"
    INTERVENTIONAL = "interventional"
    OBSERVATIONAL = "observational"


class StudyPhase(StrEnum):
    """Define valid study phase terms

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#enum-Phase
    """

    NA = "na"
    EARLY_PHASE_1 = "early_phase_1"
    PHASE_1 = "phase_1"
    PHASE_2 = "phase_2"
    PHASE_3 = "phase_3"
    PHASE_4 = "phase_4"

    @classmethod
    def _missing_(cls, value):  # noqa: ANN001 ANN206
        return map_to_enum(
            cls,
            value,
            {
                "early_phase1": cls.EARLY_PHASE_1,
                "phase1": cls.PHASE_1,
                "phase2": cls.PHASE_2,
                "phase3": cls.PHASE_3,
                "phase4": cls.PHASE_4,
            },
        )


class EnrollmentType(StrEnum):
    """Define valid enrollment type terms

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#enum-EnrollmentType
    """

    ACTUAL = "actual"
    ESTIMATED = "estimated"


Design = namedtuple("Design", ("study_type", "phases", "enrollment"))


def _format_design(design_input: dict) -> Design:
    """Format ProtocolSection.DesignModule

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#DesignModule

    :param design_input: raw JSON
    :return: structured data
    """
    enrollment = (
        Enrollment(
            count=design_input["enrollmentInfo"].get("count"),
            type=EnrollmentType(design_input["enrollmentInfo"]["type"].lower())
            if "type" in design_input["enrollmentInfo"]
            else None,
        )
        if "enrollmentInfo" in design_input
        else None
    )
    return Design(
        study_type=StudyType(design_input["studyType"].lower()),
        phases=[StudyPhase(p.lower()) for p in design_input["phases"]]
        if "phases" in design_input
        else None,
        enrollment=enrollment,
    )


class InterventionType(StrEnum):
    """Define valid intervention type terms

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#enum-InterventionType
    """

    BEHAVIORAL = "behavioral"
    BIOLOGICAL = "biological"
    COMBINATION_PRODUCT = "combination_product"
    DEVICE = "device"
    DIAGNOSTIC_TEST = "diagnostic_test"
    DIETARY_SUPPLEMENT = "dietary_supplement"
    DRUG = "drug"
    GENETIC = "genetic"
    PROCEDURE = "procedure"
    RADIATION = "radiation"
    OTHER = "other"


Intervention = namedtuple("Intervention", ("type", "name", "description", "aliases"))
ArmsInterventions = namedtuple("ArmsInterventions", ("interventions"))


def _format_arms_interventions(arms_ints_input: dict) -> ArmsInterventions:
    """Format ProtocolSection.ArmsInterventionsModule

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#ArmsInterventionsModule

    :param arms_ints_input: raw JSON
    :return: structured data
    """
    interventions = (
        [
            Intervention(
                type=InterventionType(i["type"].lower()) if "type" in i else None,
                name=i.get("name"),
                description=i.get("description"),
                aliases=i.get("otherNames"),
            )
            for i in arms_ints_input["interventions"]
        ]
        if "interventions" in arms_ints_input
        else None
    )
    return ArmsInterventions(interventions=interventions)


Outcome = namedtuple("Outcome", ("measure", "description", "timeframe"))
Outcomes = namedtuple("Outcomes", ("primary_outcomes", "secondary_outcomes"))


def _format_outcomes(outcomes: dict) -> Outcomes:
    """Format ProtocolSection.OutcomesModule

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#OutcomesModule

    :param outcomes: raw JSON
    :return: structured data
    """
    primary = [
        Outcome(
            measure=po.get("measure"),
            description=po.get("description"),
            timeframe=po.get("timeFrame"),
        )
        for po in outcomes["primaryOutcomes"]
    ]
    secondary = [
        Outcome(
            measure=po.get("measure"),
            description=po.get("description"),
            timeframe=po.get("timeFrame"),
        )
        for po in outcomes["secondaryOutcomes"]
    ]
    return Outcomes(primary_outcomes=primary, secondary_outcomes=secondary)


Eligibility = namedtuple(
    "Eligibility",
    (
        "min_age",
        "max_age",
        "std_age",
        "description",
        "accepts_healthy",
        "sex",
        "gender_based",
        "gender_description",
        "population",
    ),
)


class StandardAge(StrEnum):
    """Define possible standardized age group values.

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#enum-StandardAge
    """

    CHILD = "child"
    ADULT = "adult"
    OLDER_ADULT = "older_adult"


# these are obviously imprecise, to varying degrees, but it's what we have to work with
_SECONDS_IN_MINUTE = 60
_SECONDS_IN_HOUR = 60 * _SECONDS_IN_MINUTE
_SECONDS_IN_DAY = 24 * _SECONDS_IN_HOUR
_SECONDS_IN_WEEK = 7 * _SECONDS_IN_DAY
_SECONDS_IN_MONTH = 31 * _SECONDS_IN_DAY
_SECONDS_IN_YEAR = 365 * _SECONDS_IN_DAY


def _age_to_timedelta(raw_age: str) -> datetime.timedelta:
    """Reformat age as a timedelta object

    :param raw_age: raw string description:
    :return: age as time delta
    """
    num = int(raw_age.split(" ", 1)[0])
    if "Year" in raw_age:
        factor = _SECONDS_IN_YEAR
    elif "Month" in raw_age:
        factor = _SECONDS_IN_MONTH
    elif "Week" in raw_age:
        factor = _SECONDS_IN_WEEK
    elif "Day" in raw_age:
        factor = _SECONDS_IN_DAY
    elif "Hour" in raw_age:
        factor = _SECONDS_IN_HOUR
    elif "Minute" in raw_age:
        factor = _SECONDS_IN_MINUTE
    else:
        msg = f"Unable to parse '{raw_age}' as a duration"
        raise ValueError(msg)
    return datetime.timedelta(seconds=factor * num)


class CandidateSex(StrEnum):
    """Sex of a participant in a study

    https://clinicaltrials.gov/data-api/about-api/study-data-structure#enum-Sex
    """

    FEMALE = "female"
    MALE = "male"
    ALL = "all"


def _format_eligibility(elig_input: dict) -> Eligibility:
    """Format ProtocolSection.EligibilityModule

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#EligibilityModule

    :param elig_input: raw JSON
    :return: structured data
    """
    min_age = (
        _age_to_timedelta(elig_input["minimumAge"])
        if "minimumAge" in elig_input
        else None
    )
    max_age = (
        _age_to_timedelta(elig_input["maximumAge"])
        if "maximumAge" in elig_input
        else None
    )
    return Eligibility(
        min_age=min_age,
        max_age=max_age,
        std_age=[StandardAge(a.lower()) for a in elig_input["stdAges"]]
        if "stdAges" in elig_input
        else None,
        description=elig_input.get("eligibilityCriteria"),
        accepts_healthy=elig_input.get("healthyVolunteers"),
        sex=CandidateSex(elig_input["sex"].lower()) if elig_input.get("sex") else None,
        # distinction between gender and sex here -- these fields are for self-ID of gender
        # https://clinicaltrials.gov/policy/protocol-definitions#GenderDescription
        gender_based=elig_input.get("genderBased"),
        gender_description=elig_input.get("genderDescription"),
        population=elig_input.get("studyPopulation"),
    )


class Location(NamedTuple):
    """Define data object for an individual location (i.e. for a trial site)."""

    facility: str | None
    status: Status | None
    city: str | None
    state_province: str | None
    postal_code: str | None
    country: str | None
    # (latitude, longitude)
    geo: tuple[float, float] | None


class ContactsLocationData(NamedTuple):
    """Define data object for a the contacts-locations module

    https://clinicaltrials.gov/data-api/about-api/study-data-structure#ContactsLocationsModule
    """

    locations: list[Location]


def _format_locations(loc_input: dict) -> ContactsLocationData:
    """Extract data from contactsLocations module

    :param loc_input: raw protocolSection.contactsLocationsModule object
    :return: completed location data description
    """
    locations = []
    for i in loc_input.get("locations", []):
        locations.append(  # noqa: PERF401
            Location(
                facility=i.get("facility"),
                status=Status(i["status"].lower()) if i.get("status") else None,
                city=i.get("city"),
                state_province=i.get("state"),
                postal_code=i.get("zip"),
                country=i.get("country"),
                geo=(i["geoPoint"]["lat"], i["geoPoint"]["lon"])
                if i.get("geoPoint")
                else None,
            )
        )
    return ContactsLocationData(locations=locations)


class ReferenceType(StrEnum):
    """Define possible reference types.

    https://clinicaltrials.gov/data-api/about-api/study-data-structure#enum-ReferenceType
    """

    BACKGROUND = "background"
    RESULT = "result"
    DERIVED = "derived"


Reference = namedtuple(
    "Reference", ("pmid", "type", "citation", "retraction_pmid", "retraction_source")
)


def _format_reference(ref_input: dict) -> Reference:
    """Format ProtocolSection.ReferencesModule.reference

    See
    * https://clinicaltrials.gov/data-api/about-api/study-data-structure#Reference
    * https://clinicaltrials.gov/policy/protocol-definitions#RefCitations

    :param ref_input: raw JSON
    :return: structured data
    """
    retraction_pmid, retraction_source = None, None
    if "retraction" in ref_input:
        retraction = ref_input["retraction"]
        retraction_pmid = retraction.get("retractionPmid")
        retraction_source = retraction.get("retractionSource")
    return Reference(
        pmid=ref_input.get("pmid"),
        type=ReferenceType(ref_input["type"].lower()) if "type" in ref_input else None,
        citation=ref_input.get("citation"),
        retraction_pmid=retraction_pmid,
        retraction_source=retraction_source,
    )


Protocol = namedtuple(
    "Protocol",
    (
        "identification",
        "status",
        "sponsor_collaborators",
        "oversight",
        "description",
        "conditions",
        "design",
        "arms_intervention",
        "outcomes",
        "eligibility",
        "contacts_locations",
        "references",
    ),
)


def _format_protocol(protocol_input: dict) -> Protocol:
    """Format ProtocolSection

    See
    * https://clinicaltrials.gov/policy/protocol-definitions
    * https://clinicaltrials.gov/data-api/about-api/study-data-structure#protocolSection

    :param protocol_input: raw JSON
    :return: structured data
    """
    conditions = (
        ProtocolConditions(
            conditions=protocol_input["conditionsModule"].get("conditions"),
            keywords=protocol_input["conditionsModule"].get("keywords"),
        )
        if "conditionsModule" in protocol_input
        else None
    )
    return Protocol(
        identification=_format_protocol_id(protocol_input["identificationModule"])
        if "identificationModule" in protocol_input
        else None,
        status=_format_status(protocol_input["statusModule"])
        if "statusModule" in protocol_input
        else None,
        sponsor_collaborators=_format_sponsor_collaborators(
            protocol_input["sponsorCollaboratorsModule"]
        )
        if "sponsorCollaboratorsModule" in protocol_input
        else None,
        oversight=_format_oversight(protocol_input["oversightModule"])
        if "oversightModule" in protocol_input
        else None,
        description=_format_description(protocol_input["description"])
        if "description" in protocol_input
        else None,
        conditions=conditions,
        design=_format_design(protocol_input["designModule"])
        if "designModule" in protocol_input
        else None,
        arms_intervention=_format_arms_interventions(
            protocol_input["armsInterventionsModule"]
        )
        if "armsInterventionsModule" in protocol_input
        else None,
        outcomes=_format_outcomes(protocol_input["outcomes"])
        if "outcomes" in protocol_input
        else None,
        eligibility=_format_eligibility(protocol_input["eligibilityModule"])
        if "eligibilityModule" in protocol_input
        else None,
        contacts_locations=_format_locations(protocol_input["contactsLocationsModule"])
        if "contactsLocationsModule" in protocol_input
        else None,
        references=[
            _format_reference(r)
            for r in protocol_input["referencesModule"]["references"]
        ]
        if protocol_input.get("referencesModule", {}).get("references")
        else None,
    )


class EventAssessment(StrEnum):
    """Define possible values for event assessment.

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#enum-EventAssessment
    """

    NON_SYSTEMATIC_ASSESSMENT = "non_systematic_assessment"
    SYSTEMATIC_ASSESSMENT = "systematic_assessment"


AdverseEventStat = namedtuple(
    "AdverseEventStat", ("group_id", "num_events", "num_affected", "num_at_risk")
)
AdverseEvent = namedtuple(
    "AdverseEvent",
    ("term", "organ_system", "source_vocabulary", "assessment_type", "notes", "stats"),
)
AdverseEvents = namedtuple(
    "AdverseEvents",
    (
        "frequency_threshold",
        "timeframe",
        "description",
        "all_cause_mortality_comment",
        "serious_events",
        "other_events",
    ),
)


def _format_event(event_input: dict) -> AdverseEvent:
    """Format adverse event

    :param event_input: raw JSON
    :return: Structured data
    """
    return AdverseEvent(
        term=event_input.get("term"),
        organ_system=event_input.get("organSystem"),
        source_vocabulary=event_input.get("sourceVocabulary"),
        assessment_type=EventAssessment(event_input["assessmentType"].lower())
        if "assessmentType" in event_input
        else None,
        stats=[
            AdverseEventStat(
                group_id=s.get("groupId"),
                num_events=s.get("numEvents"),
                num_affected=s.get("numAffected"),
                num_at_risk=s.get("numAtRisk"),
            )
            for s in event_input.get("stats", [])
        ]
        if "stats" in event_input
        else None,
        notes=event_input.get("notes"),
    )


def _format_adverse_events(aes_input: dict) -> AdverseEvents:
    """Format ResultsSection.AdverseEventsModule

    See
    * https://clinicaltrials.gov/data-api/about-api/study-data-structure#AdverseEventsModule
    * https://clinicaltrials.gov/policy/results-definitions#Result_AdverseEvents

    :param aes_input: raw JSON
    :return: Structured data
    """
    return AdverseEvents(
        frequency_threshold=aes_input.get("frequencyThreshold"),
        timeframe=aes_input.get("timeFrame"),
        description=aes_input.get("description"),
        all_cause_mortality_comment=aes_input.get("allCauseMortalityComment"),
        serious_events=[_format_event(event) for event in aes_input["seriousEvents"]]
        if "seriousEvents" in aes_input
        else None,
        other_events=[_format_event(event) for event in aes_input["otherEvents"]]
        if "otherEvents" in aes_input
        else None,
    )


Results = namedtuple("Results", ("adverse_events"))


def _format_results(results_input: dict) -> Results:
    """Format ResultsSection

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#resultsSection

    :param results_input: raw JSON
    :return: structured data
    """
    return Results(
        adverse_events=_format_adverse_events(results_input["adverseEventsModule"])
        if "adverseEventsModule" in results_input
        else None,
    )


MeshConcept = namedtuple("MeshConcept", ("id", "term"))
Derived = namedtuple("Derived", ("conditions"))


def _format_derived(der_input: dict) -> Derived:
    """Format DerivedSection data


    See https://clinicaltrials.gov/data-api/about-api/study-data-structure#DerivedSection

    :param der_input: raw JSON
    :return: structured data
    """
    return Derived(
        conditions=[
            MeshConcept(id=c.get("id"), term=c.get("term"))
            for c in der_input["conditionBrowseModule"]["meshes"]
        ]
        if der_input.get("conditionBrowseModule", {}).get("meshes")
        else None
    )


Study = namedtuple("Study", ("protocol", "results", "derived"))


def _format_study(study_input: dict) -> Study:
    """Format a raw study JSON object received from the ClinicalTrials.gov API

    See https://clinicaltrials.gov/data-api/about-api/study-data-structure

    :param study_input: raw JSON
    :return: Structured data
    """
    return Study(
        protocol=_format_protocol(study_input["protocolSection"]),
        results=_format_results(study_input["resultsSection"])
        if "resultsSection" in study_input
        else None,
        derived=_format_derived(study_input["derivedSection"])
        if "derivedSection" in study_input
        else None,
    )


def _get_id(study_response: dict, url: str, i: int) -> str | None:
    """Extract NCT ID from study response

    :param study_response: a single study response object
    :param url: URL used to issue request
    :param i: index of individual study within response to that URL
    :return: NCT ID if available (should be, but we're being careful)
    """
    study_id = (
        study_response.get("protocolSection", {})
        .get("identificationModule", {})
        .get("nctId")
    )
    if not study_id:
        _logger.error(
            "Unable to fetch study ID for the %s 'th entry in %s. Is the JSON object malformed?",
            i,
            url,
        )
    return study_id


def make_fda_clinical_trials_request(
    url: str, skip_parsing_failures: bool
) -> list[Study]:
    """Issue a request against provided URL for FDA Clinical Trials API

    :param url: URL to request. This method doesn't add any additional parameters except
        for pagination.
    :param skip_parsing_failures: if ``True``, catch and suppress failures to parse
        study metadata
    :return: studies contained in API response
    """
    results = []
    next_page_token = None
    while True:
        formatted_url = f"{url}&pageToken={next_page_token}" if next_page_token else url
        with requests.get(formatted_url, timeout=30) as r:
            try:
                r.raise_for_status()
            except RequestException as e:
                _logger.warning(
                    "Request to %s returned status code %s", url, r.status_code
                )
                raise e
            raw_data = r.json()
            for i, study in enumerate(raw_data.get("studies", [])):
                try:
                    parsed_data = _format_study(study)
                except ValueError as e:
                    if skip_parsing_failures:
                        nct_id = _get_id(study, formatted_url, i)
                        _logger.warning("Failed to parse study %s: %s", nct_id, e)
                        continue
                    raise e
                results.append(parsed_data)

            next_page_token = raw_data.get("nextPageToken")
            if not next_page_token:
                break
    return results


def get_clinical_trials(
    drug_name: str | None = None, skip_parsing_failures: bool = False
) -> list[Study]:
    """Get data from the FDA Clinical Trials API.

    >>> results = get_clinical_trials("imatinib")
    >>> results[0].protocol.identification.nct_id
    'NCT00769782'

    :param drug_name: name of drug used for trial intervention. This is passed to the
        API intervention parameter, which appears to search for inclusion as a substring
        rather than a full-span match
    :param skip_parsing_failures: if ``True``
    :return: list of matching trial descriptions
    """
    if not drug_name:
        msg = "Must supply a query parameter like `drug_name`"
        raise ValueError(msg)
    params = ["pageSize=50"]
    if drug_name:
        params.append(f"query.intr={drug_name}")
    url = f"https://clinicaltrials.gov/api/v2/studies?{'&'.join(params)}"
    return make_fda_clinical_trials_request(url, skip_parsing_failures)

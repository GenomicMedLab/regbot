from datetime import UTC, datetime
from pathlib import Path

import pytest
import requests_mock

from regbot.fetch.clinical_trials import (
    CandidateSex,
    InterventionType,
    Location,
    MeshConcept,
    Status,
    get_clinical_trials,
)


def test_fetch_clinical_trials(fixtures_dir: Path):
    with pytest.raises(
        ValueError, match="Must supply a query parameter like `drug_name`"
    ):
        get_clinical_trials()
    with (
        requests_mock.Mocker() as m,
        (fixtures_dir / "fetch_clinical_trial_zolgensma.json").open() as json_response,
    ):
        m.get(
            "https://clinicaltrials.gov/api/v2/studies?query.intr=zolgensma",
            text=json_response.read(),
        )
        results = get_clinical_trials(drug_name="zolgensma")
    assert results
    example = results[2]

    assert example.protocol.identification.nct_id == "clinicaltrials:NCT05386680"
    assert example.protocol.identification.org_id.id == "COAV101B12302"
    assert (
        example.protocol.sponsor_collaborators.lead_sponsor_name
        == "Novartis Pharmaceuticals"
    )
    assert example.protocol.conditions.conditions == ["Spinal Muscular Atrophy"]
    assert example.protocol.status.overall_status == Status.ACTIVE_NOT_RECRUITING
    assert example.protocol.status.dates.start_date == datetime(2023, 1, 12, tzinfo=UTC)
    assert example.protocol.oversight.is_fda_regulated_drug is True
    assert example.protocol.arms_intervention.interventions[0].name == "OAV101"
    assert (
        example.protocol.arms_intervention.interventions[0].type
        == InterventionType.GENETIC
    )
    assert "SMA diagnosis" in example.protocol.eligibility.description
    assert example.protocol.eligibility.accepts_healthy is False
    assert example.protocol.eligibility.sex == CandidateSex.ALL
    assert len(example.protocol.contacts_locations.locations) == 13
    assert example.protocol.contacts_locations.locations[4] == Location(
        facility="Novartis Investigative Site",
        city="Leuven",
        postal_code="3000",
        country="Belgium",
        geo=(50.87959, 4.70093),
        status=None,
        state_province=None,
    )
    assert example.derived.conditions[0] == MeshConcept(
        id="D009133", term="Muscular Atrophy"
    )

    with (
        requests_mock.Mocker() as m,
        (
            fixtures_dir / "fetch_clinical_trial_zolgensma_parsing_error.json"
        ).open() as json_response,
    ):
        m.get(
            "https://clinicaltrials.gov/api/v2/studies?query.intr=zolgensma",
            text=json_response.read(),
        )
        # check that parsing errors are skipped
        results = get_clinical_trials(drug_name="zolgensma", skip_parsing_failures=True)

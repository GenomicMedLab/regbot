from pathlib import Path

import pytest
import requests_mock

from regbot.fetch.rxclass import (
    ClassType,
    DrugClassification,
    DrugConcept,
    Relation,
    RelationSource,
    RxClassEntry,
    TermType,
    get_drug_class_info,
)


def test_get_rxclass(fixtures_dir: Path):
    with requests_mock.Mocker() as m:
        m.get(
            "https://rxnav.nlm.nih.gov/REST/rxclass/class/byDrugName.json?drugName=not_a_drug",
            text="{}",
        )
        results = get_drug_class_info("not_a_drug")
        assert results == []

    with (
        requests_mock.Mocker() as m,
        (fixtures_dir / "fetch_rxclass_imatinib.json").open() as json_response,
    ):
        m.get(
            "https://rxnav.nlm.nih.gov/REST/rxclass/class/byDrugName.json?drugName=imatinib",
            text=json_response.read(),
        )
        results = get_drug_class_info("imatinib")
        assert len(results) == 46
        expected = RxClassEntry(
            concept=DrugConcept(
                concept_id="rxcui:282388",
                name="imatinib",
                term_type=TermType.IN,
            ),
            drug_classification=DrugClassification(
                class_id="D054437",
                class_name="Myelodysplastic-Myeloproliferative Diseases",
                class_type=ClassType.DISEASE,
                class_url=None,
            ),
            relation=Relation.MAY_TREAT,
            relation_source=RelationSource.MEDRT,
        )

        for result in results:
            if result == expected:
                break
        else:
            msg = "No classification found relating imatinib to class ID D054437"
            raise pytest.fail(msg)

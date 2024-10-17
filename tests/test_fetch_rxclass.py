from pathlib import Path

import requests_mock

from regbot.fetch.rxclass import get_drug_class_info


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
        results = get_drug_class_info("imatinib", normalize=True)

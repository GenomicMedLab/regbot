"""Test regbot.fetch.drugsfda"""

from pathlib import Path

import requests_mock

from regbot.fetch.drugsfda import get_anda_results, get_nda_results


def test_get_anda_results(fixtures_dir: Path):
    with (
        requests_mock.Mocker() as m,
        (fixtures_dir / "fetch_anda_falmina.json").open() as json_response,
    ):
        m.get(
            "https://api.fda.gov/drug/drugsfda.json?search=openfda.application_number:ANDA090721",
            text=json_response.read(),
        )

        results = get_anda_results("090721", True)
        assert results
        assert len(results) > 0


def test_get_nda_results(fixtures_dir: Path):
    with (
        requests_mock.Mocker() as m,
        (fixtures_dir / "fetch_nda_xadago.json").open() as json_response,
    ):
        m.get(
            "https://api.fda.gov/drug/drugsfda.json?search=openfda.application_number:NDA207145",
            text=json_response.read(),
        )

        results = get_nda_results("207145", True)
        assert results
        assert len(results) > 0

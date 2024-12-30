# 🤖 regbot 🤖

[![image](https://img.shields.io/pypi/v/regbot.svg)](https://pypi.python.org/pypi/regbot)
[![image](https://img.shields.io/pypi/l/regbot.svg)](https://pypi.python.org/pypi/regbot)
[![image](https://img.shields.io/pypi/pyversions/regbot.svg)](https://pypi.python.org/pypi/regbot)
[![Actions status](https://github.com/genomicmedlab/regbot/actions/workflows/checks.yaml/badge.svg)](https://github.com/genomicmedlab/regbot/actions/checks.yaml)

<!-- description -->
Acquire cleaned and structured data about drugs and therapeutics from US regulatory agencies and services:

* ClinicalTrials.gov
* Drugs@FDA
* RxClass
<!-- /description -->

All data returned from regulatory APIs is structured as instances of standard library NamedTuples. This is done to give data structure and rudimentary type annotation (i.e. to benefit code editor and analysis tools) without adding runtime heft or being wedded to particular schema libraries like Pydantic. This may change in the future.

---

## Installation

Install from [PyPI](https://pypi.org/project/regbot/):

```shell
python3 -m pip install regbot
```

---

## Development

Clone the repo and create a virtual environment:

```shell
git clone https://github.com/genomicmedlab/regbot
cd regbot
python3 -m virtualenv venv
source venv/bin/activate
```

Install development dependencies and `pre-commit`:

```shell
python3 -m pip install -e '.[dev,tests]'
pre-commit install
```

Check style with `ruff`:

```shell
python3 -m ruff format . && python3 -m ruff check --fix .
```

Run tests with `pytest`:

```shell
pytest
```

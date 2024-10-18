"""Provide helper methods for imposing structure onto raw data fetched from external APIs."""

from enum import Enum


def map_to_enum(cls: type[Enum], value: str, mapping: dict) -> Enum:
    """Use in enum _missing_ methods to map alternate constructions to python-legal values."""
    try:
        if value in mapping:
            return mapping[value]
        msg = f"'{value}' is not a valid {cls.__name__}"
        raise ValueError(msg)
    except AttributeError as _:
        msg = f"'{value}' is not a valid {cls.__name__}"
        raise ValueError(msg) from None

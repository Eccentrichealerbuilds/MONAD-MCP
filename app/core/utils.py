# app/core/utils.py
from web3.types import HexBytes
from collections.abc import Mapping # Use this for broader compatibility
from typing import Any

def attrdict_to_dict(attr_dict: Any) -> Any:
    """
    Recursively converts an AttributeDict (often returned by web3.py)
    and its elements (like HexBytes, large ints) into a standard JSON-serializable dict/list/value.
    """
    if isinstance(attr_dict, HexBytes):
        return attr_dict.hex()
    elif isinstance(attr_dict, Mapping): # Check if it's dict-like
        return {key: attrdict_to_dict(value) for key, value in attr_dict.items()}
    elif isinstance(attr_dict, list):
         return [attrdict_to_dict(item) for item in attr_dict]
    elif isinstance(attr_dict, int) and attr_dict > 2**53: # Handle large integers for JSON safety
         return str(attr_dict)
    # Return other types (str, bool, small int, float, None) as is
    return attr_dict
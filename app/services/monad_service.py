# app/services/monad_service.py

import httpx
import os
import sys  # Ensure sys is imported
import asyncio

from web3 import Web3 # Import Web3 itself
from web3.exceptions import (
    InvalidAddress,
    TransactionNotFound,
    BlockNotFound,
    ContractLogicError,
    ABIFunctionNotFound
)
from web3.types import HexBytes
from collections.abc import Mapping
from typing import Union, Dict, Any, List, Optional

from pydantic import ValidationError

# Import dependencies from our core module
from app.core.web3_setup import get_w3
from app.core.utils import attrdict_to_dict

# Get the web3 instance (available globally within this module after import)
w3 = get_w3()

# --- Core Service Functions ---

async def get_balance(address: str) -> Dict[str, str]:
    """
    Gets native MON balance for an address on Monad Testnet.
    Args: address (str): The Monad wallet address (0x...).
    Returns: dict: Dictionary with address, balance_wei, balance_mon.
    Raises: ValueError, ConnectionError.
    """
    global w3
    if not w3 or not w3.is_connected(): w3 = get_w3() # Try re-getting
    if not w3 or not w3.is_connected(): raise ConnectionError("Monad RPC connection not available.")
    try: checksum_address = w3.to_checksum_address(address)
    except (InvalidAddress, ValueError): raise ValueError(f"Invalid address format: {address}")
    try:
        loop = asyncio.get_running_loop()
        balance_wei = await loop.run_in_executor(None, w3.eth.get_balance, checksum_address)
        balance_mon = w3.from_wei(balance_wei, 'ether')
        return {
            "address": checksum_address,
            "balance_wei": str(balance_wei),
            "balance_mon": f"{balance_mon:.18f}"
        }
    except Exception as e:
        print(f"Service Error (get_balance for {address}): {type(e).__name__} - {e}", file=sys.stderr)
        raise ConnectionError(f"Could not retrieve balance: {e}")

async def get_native_monad_balance(address: str) -> str:
    """
    Gets the native MON balance (main network coin) for an address on Monad Testnet.
    Use this specifically for 'MON' or 'native' balance requests.
    Args: address (str): The Monad wallet address (0x...).
    Returns: str: Formatted balance string (e.g., "4.157... MON") or raises error.
    Raises: ValueError, ConnectionError.
    """
    # This function is called by the @mcp.tool wrapper
    global w3
    if not w3 or not w3.is_connected(): w3 = get_w3()
    if not w3 or not w3.is_connected(): raise ConnectionError("Monad RPC connection not available.")
    try: checksum_address = w3.to_checksum_address(address)
    except (InvalidAddress, ValueError): raise ValueError(f"Invalid address format: {address}")
    try:
        loop = asyncio.get_running_loop()
        balance_wei = await loop.run_in_executor(None, w3.eth.get_balance, checksum_address)
        balance_mon = w3.from_wei(balance_wei, 'ether')
        result_str = f"{balance_mon:.18f} MON"
        print(f"SERVICE: Native balance found: {result_str}", file=sys.stderr)
        return result_str
    except Exception as e:
        print(f"Service Error (get_native_monad_balance for {address}): {type(e).__name__} - {e}", file=sys.stderr)
        raise ConnectionError(f"Could not retrieve native balance: {e}")

async def get_transaction(tx_hash: str) -> Dict[str, Any]:
    """
    Gets details for a specific transaction hash on Monad Testnet.
    Args: tx_hash (str): The transaction hash (0x...).
    Returns: dict: Dictionary of transaction details.
    Raises: ValueError, FileNotFoundError, ConnectionError.
    """
    global w3
    if not w3 or not w3.is_connected(): w3 = get_w3()
    if not w3 or not w3.is_connected(): raise ConnectionError("Monad RPC connection not available.")
    if not tx_hash.startswith('0x') or len(tx_hash) != 66: raise ValueError("Invalid transaction hash format.")
    try:
        loop = asyncio.get_running_loop()
        tx_data = await loop.run_in_executor(None, w3.eth.get_transaction, tx_hash)
        if tx_data is None: raise FileNotFoundError(f"Transaction not found or pending: {tx_hash}")
        return attrdict_to_dict(tx_data)
    except TransactionNotFound: raise FileNotFoundError(f"Transaction not found: {tx_hash}")
    except Exception as e:
        print(f"Service Error (get_transaction for {tx_hash}): {type(e).__name__} - {e}", file=sys.stderr)
        raise ConnectionError(f"Could not retrieve transaction details: {e}")

async def get_block(block_identifier: Union[int, str]) -> Dict[str, Any]:
    """
    Gets details for a specific block number or identifier on Monad Testnet.
    Args: block_identifier (int | str): Block number or 'latest', 'earliest', 'pending'.
    Returns: dict: Dictionary of block details.
    Raises: ValueError, TypeError, FileNotFoundError, ConnectionError.
    """
    global w3
    if not w3 or not w3.is_connected(): w3 = get_w3()
    if not w3 or not w3.is_connected(): raise ConnectionError("Monad RPC connection not available.")
    block_id: Union[int, str]
    if isinstance(block_identifier, str):
        block_id_lower = block_identifier.lower()
        if block_id_lower in ['latest', 'earliest', 'pending']: block_id = block_id_lower
        else:
            try: block_id = int(block_identifier); assert block_id >= 0
            except (ValueError, AssertionError): raise ValueError("Invalid block identifier string.")
    elif isinstance(block_identifier, int):
        if block_identifier < 0: raise ValueError("Block number cannot be negative.")
        block_id = block_identifier
    else: raise TypeError("Invalid block identifier type.")

    if block_id is None: raise ValueError("Could not parse block identifier.")
    try:
        loop = asyncio.get_running_loop()
        block_data = await loop.run_in_executor(None, w3.eth.get_block, block_id, False)
        if block_data is None: raise FileNotFoundError(f"Block not found: {block_identifier}")
        return attrdict_to_dict(block_data)
    except BlockNotFound: raise FileNotFoundError(f"Block not found: {block_identifier}")
    except Exception as e:
        print(f"Service Error (get_block for {block_identifier}): {type(e).__name__} - {e}", file=sys.stderr)
        raise ConnectionError(f"Could not retrieve block details: {e}")

async def read_contract(
    contract_address: str,
    function_name: str,
    args: List[Any],
    abi: Optional[List[Dict[str, Any]]] = None
) -> Any:
    """
    Calls a read-only contract function, fetching ABI if needed via Thirdweb Insight.
    Requires THIRDWEB_CLIENT_ID env var if ABI not provided.
    Args: contract_address (str), function_name (str), args (list), abi (list, optional).
    Returns: Any: Result of the contract call.
    Raises: ValueError, FileNotFoundError (for ABI), ConnectionError.
    """
    global w3
    if not w3 or not w3.is_connected(): w3 = get_w3()
    if not w3 or not w3.is_connected(): raise ConnectionError("Monad RPC connection not available.")
    try: checksum_address = w3.to_checksum_address(contract_address)
    except (InvalidAddress, ValueError): raise ValueError(f"Invalid contract address format: {contract_address}")

    fetched_abi = None
    if not abi:
        print(f"ABI not provided for {checksum_address}. Fetching from Thirdweb Insight...", file=sys.stderr)
        client_id = os.getenv("THIRDWEB_CLIENT_ID")
        if not client_id: raise ValueError("ABI fetch requires THIRDWEB_CLIENT_ID env var.")
        chain_id = 10143
        insight_url = f"https://insight.thirdweb.com/v1/contracts/abi/{checksum_address}?chain={chain_id}&clientId={client_id}"
        print(f"Calling Insight API: {insight_url}", file=sys.stderr)
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
                response = await client.get(insight_url, headers=headers)
                print(f"Insight API Status Code: {response.status_code}", file=sys.stderr)
                response.raise_for_status()
                fetched_data = response.json()
                print("Insight API JSON parsed successfully.", file=sys.stderr)
                abi_list = None
                if isinstance(fetched_data, list): abi_list = fetched_data
                elif isinstance(fetched_data, dict):
                     if 'result' in fetched_data and isinstance(fetched_data['result'], list): abi_list = fetched_data['result']
                     elif 'abi' in fetched_data and isinstance(fetched_data['abi'], list): abi_list = fetched_data['abi']
                if abi_list is None: raise ValueError("Could not parse ABI list from Insight response.")
                print(f"Successfully fetched ABI with {len(abi_list)} items.", file=sys.stderr)
                abi = abi_list
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404: raise FileNotFoundError(f"ABI not found on Thirdweb Insight (404).")
            else: raise ConnectionError(f"Failed to fetch ABI: HTTP {e.response.status_code}")
        except Exception as e: raise ConnectionError(f"Failed to fetch ABI: {e}")

    if not isinstance(abi, list) or not abi: raise ValueError("Invalid or empty ABI.")

    try:
        contract = w3.eth.contract(address=checksum_address, abi=abi)
        if not hasattr(contract.functions, function_name): raise ValueError(f"Function '{function_name}' not found in ABI.")
        contract_function = getattr(contract.functions, function_name)
        processed_args = [w3.to_checksum_address(arg) if isinstance(arg, str) and w3.is_address(arg) else arg for arg in args]
        print(f"Calling contract function '{function_name}' at {checksum_address}...", file=sys.stderr)
        loop = asyncio.get_running_loop()
        raw_result = await loop.run_in_executor(None, contract_function(*processed_args).call)
        # Process result
        if isinstance(raw_result, int) and raw_result > 2**53: return str(raw_result)
        if isinstance(raw_result, bytes): return HexBytes(raw_result).hex()
        if isinstance(raw_result, (list, tuple)):
            return [str(item) if isinstance(item, int) and item > 2**53 else HexBytes(item).hex() if isinstance(item, bytes) else item for item in raw_result]
        return raw_result
    except ContractLogicError as e: raise ValueError(f"Contract execution reverted: {e}")
    except ABIFunctionNotFound: raise ValueError(f"Function '{function_name}' ABI signature mismatch.")
    except ValidationError as e: raise ValueError(f"Invalid arguments for function '{function_name}': {e}")
    except Exception as e:
        print(f"Service Error (read_contract {function_name} on {checksum_address}): {type(e).__name__} - {e}", file=sys.stderr)
        raise ConnectionError(f"Could not read contract: {e}")

async def get_contract_interactions(wallet_address: str) -> Dict[str, Any]:
    """
    Gets unique contract interactions (sent to) via Zerion API.
    Requires ZERION_API_KEY env var.
    Args: wallet_address (str): The address to analyze.
    Returns: dict: Counts and list of unique contract addresses.
    Raises: ValueError, FileNotFoundError, ConnectionError.
    """
    print(f"Starting Zerion interaction analysis for {wallet_address}", file=sys.stderr)
    global w3
    if not w3 or not w3.is_connected(): w3 = get_w3()
    if not w3 or not w3.is_connected(): raise ConnectionError("Monad RPC connection needed for contract checks.")

    zerion_api_key = os.getenv("ZERION_API_KEY")
    if not zerion_api_key: raise ValueError("Zerion API Key not configured.")

    interacted_addresses = set()
    total_txns_processed = 0
    page_num = 1
    api_base_url = "https://api.zerion.io/v1/"
    endpoint_path = f"wallets/{wallet_address}/transactions"
    chain_filter = "monad-test-v2"
    page_size = 100
    initial_params = {"filter[chain_ids]": chain_filter, "page[size]": page_size, "currency": "usd", "filter[trash]": "no_filter"}
    current_endpoint_url = api_base_url + endpoint_path
    current_params = initial_params

    async with httpx.AsyncClient(auth=(zerion_api_key, ""), timeout=60.0, follow_redirects=True) as client:
        while current_endpoint_url:
            print(f"Fetching Zerion page {page_num}... Unique addresses: {len(interacted_addresses)}", end='\r', file=sys.stderr)
            try:
                headers = {"accept": "application/json", "X-Env": "testnet"}
                params_to_send = current_params if page_num == 1 else None
                response = await client.get(current_endpoint_url, params=params_to_send, headers=headers)
                response.raise_for_status()
                api_data = response.json()
                tx_list_page = api_data.get('data', [])
                next_page_url = api_data.get('links', {}).get('next')

                if not tx_list_page and page_num == 1: print(f"\nNo Zerion tx found for {wallet_address}", file=sys.stderr); break
                for tx in tx_list_page:
                     if tx.get('type') == 'transactions':
                         sent_to = tx.get('attributes', {}).get('sent_to')
                         if sent_to: interacted_addresses.add(sent_to.lower())

                processed_count = len(tx_list_page); total_txns_processed += processed_count
                print(f"Page {page_num} OK ({total_txns_processed} total). Unique addresses: {len(interacted_addresses)}   ", end='\r', file=sys.stderr)
                current_endpoint_url = next_page_url; current_params = None; page_num += 1
                if current_endpoint_url: await asyncio.sleep(0.5)
                else: print("\nEnd of Zerion history.", file=sys.stderr)

            except httpx.HTTPStatusError as e: print(f"\nHTTP error (Zerion page {page_num}): {e.response.status_code} - {e.response.text}", file=sys.stderr); raise ConnectionError(f"Zerion API error: {e.response.status_code}")
            except httpx.RequestError as e: print(f"\nNetwork error (Zerion page {page_num}): {e}", file=sys.stderr); raise ConnectionError(f"Network error connecting to Zerion: {e}")
            except Exception as e: print(f"\nError processing Zerion page {page_num}: {type(e).__name__} - {e}", file=sys.stderr); raise ConnectionError(f"Unexpected error during Zerion fetch: {e}")

    print(f"\nFinished Zerion fetch. Unique interacted addresses: {len(interacted_addresses)}", file=sys.stderr)

    contract_addresses = set()
    if not w3: print("Warning: Monad RPC unavailable for contract checks.", file=sys.stderr)
    else:
        print("Checking addresses for contract code...", file=sys.stderr)
        checked_count = 0; total_to_check = len(interacted_addresses)
        loop = asyncio.get_running_loop();
        for addr in interacted_addresses:
            checked_count += 1
            print(f"Checking contract {checked_count}/{total_to_check}: {addr[:15]}...", end='\r', file=sys.stderr)
            try:
                checksum_addr = w3.to_checksum_address(addr)
                code = await loop.run_in_executor(None, w3.eth.get_code, checksum_addr)
                if code and code.hex() != '0x': contract_addresses.add(checksum_addr)
                await asyncio.sleep(0.05)
            except InvalidAddress: print(f"\nSkipping invalid address format: {addr}", file=sys.stderr); continue
            except Exception as e: print(f"\nWarning: Could not check code for {addr}: {e}", file=sys.stderr); await asyncio.sleep(0.5)
    print("\nContract check complete.", file=sys.stderr)

    sorted_contract_list = sorted(list(contract_addresses))
    return {
        "analysis_address": wallet_address,
        "total_transactions_processed_by_zerion": total_txns_processed,
        "unique_interacted_address_count": len(interacted_addresses),
        "unique_contract_count": len(contract_addresses),
        "contract_addresses": sorted_contract_list
    }

# --- NEW Service Function for ERC20 Balances (using Insight) ---
async def get_monad_erc20_balances(address: str) -> List[Dict[str, Any]]:
    """
    Fetches ERC20 token balances for a wallet on Monad Testnet (chain 10143)
    using the Thirdweb Insight API with the backend Secret Key.
    Requires THIRDWEB_SECRET_KEY environment variable.
    Args: address (str): The wallet address.
    Returns: list: A list of token dicts [{'token_address': ..., 'balance': ...}] or raises error.
    Raises: ValueError, ConnectionError.
    """
    print(f"SERVICE: Getting Monad ERC20 balances for {address} via Insight...", file=sys.stderr)
    secret_key = os.getenv("THIRDWEB_SECRET_KEY")
    if not secret_key:
        raise ValueError("THIRDWEB_SECRET_KEY environment variable is not set.")

    global w3
    if not w3: w3 = get_w3() # Ensure w3 is available for validation
    if not w3: raise ConnectionError("Web3 connection not available for address validation.")
    try:
        checksum_address = w3.to_checksum_address(address)
    except (InvalidAddress, ValueError):
         raise ValueError(f"Invalid contract address format provided: {address}")

    chain_id = 10143 # Monad Testnet
    # Note: Using secret key based on curl success, adjust if needed
    headers = {"accept": "application/json", "x-secret-key": secret_key}
    # Endpoint based on successful curl test and docs
    insight_url = f"https://insight.thirdweb.com/v1/tokens/erc20/{checksum_address}"
    params = {"chain": str(chain_id), "include_price": "false"}

    print(f"Calling Insight ERC20 endpoint: {insight_url}", file=sys.stderr)
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(insight_url, params=params, headers=headers)
            print(f"Insight ERC20 Status Code: {response.status_code}", file=sys.stderr)
            response.raise_for_status() # Check for HTTP errors (like 401, 404)
            fetched_data = response.json()

            # Expecting response like {"data": [...]}
            if isinstance(fetched_data, dict) and "data" in fetched_data and isinstance(fetched_data["data"], list):
                print(f"Found {len(fetched_data['data'])} ERC20 tokens.", file=sys.stderr)
                # We might want to clean up the data slightly here if needed
                # For now, return the list directly
                return fetched_data["data"]
            else:
                print(f"Warning: Unexpected format from Insight ERC20 endpoint: {fetched_data}", file=sys.stderr)
                raise ValueError("Could not parse ERC20 balance list from Thirdweb Insight response.")

    except httpx.HTTPStatusError as e:
        print(f"HTTP error fetching ERC20 balances from Insight: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        # Re-raise as ConnectionError for generic handling, or specific error?
        raise ConnectionError(f"Failed to fetch ERC20 balances from Thirdweb Insight: HTTP {e.response.status_code}")
    except Exception as e:
        print(f"Error fetching ERC20 balances from Insight: {type(e).__name__} - {e}", file=sys.stderr)
        raise ConnectionError(f"Failed to fetch ERC20 balances: {e}")
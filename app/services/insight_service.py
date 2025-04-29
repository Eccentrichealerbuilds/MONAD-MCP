import httpx
import os
import sys
import asyncio
from typing import Dict, Any, List, Optional
from web3 import Web3
from web3.exceptions import InvalidAddress
from web3.types import HexBytes
from app.core.web3_setup import get_w3
from app.core.utils import attrdict_to_dict


async def get_abi_from_insight(contract_address: str) ->List[Dict[str, Any]]:
    """
    Fetches the ABI for a contract from the Thirdweb Insight API.
    Requires THIRDWEB_CLIENT_ID environment variable.
    Defaults to Monad Testnet (chain=10143).
    """
    print(f'SERVICE (Insight): Fetching ABI for {contract_address}...',
        file=sys.stderr)
    client_id = os.getenv('THIRDWEB_CLIENT_ID')
    if not client_id:
        raise ValueError('THIRDWEB_CLIENT_ID environment variable is not set.')
    w3 = get_w3()
    if not w3:
        raise ConnectionError('Web3 needed for validation.')
    try:
        checksum_address = w3.to_checksum_address(contract_address)
    except (InvalidAddress, ValueError):
        raise ValueError(f'Invalid contract address format: {contract_address}'
            )
    chain_id = 10143
    insight_url = (
        f'https://insight.thirdweb.com/v1/contracts/abi/{checksum_address}?chain={chain_id}&clientId={client_id}'
        )
    print(f'Calling Insight API: {insight_url}', file=sys.stderr)
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True
            ) as client:
            headers = {'User-Agent': 'Mozilla/5.0', 'Accept':
                'application/json'}
            response = await client.get(insight_url, headers=headers)
            print(f'Insight ABI Status Code: {response.status_code}', file=
                sys.stderr)
            response.raise_for_status()
            fetched_data = response.json()
            print('Insight API JSON parsed.', file=sys.stderr)
            abi_list = None
            if isinstance(fetched_data, list):
                abi_list = fetched_data
            elif isinstance(fetched_data, dict):
                if 'result' in fetched_data and isinstance(fetched_data[
                    'result'], list):
                    abi_list = fetched_data['result']
                elif 'abi' in fetched_data and isinstance(fetched_data[
                    'abi'], list):
                    abi_list = fetched_data['abi']
            if abi_list is None:
                raise ValueError(
                    'Could not parse ABI list from Insight response.')
            print(f'Successfully fetched ABI with {len(abi_list)} items.',
                file=sys.stderr)
            return abi_list
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise FileNotFoundError(f'ABI not found on Insight (404).')
        else:
            raise ConnectionError(
                f'Failed to fetch ABI: HTTP {e.response.status_code}')
    except Exception as e:
        raise ConnectionError(f'Failed to fetch ABI: {e}')


async def get_transaction_history(address: str, limit: int=50, page: int=0,
    sort_order: str='desc', timestamp_gte: Optional[int]=None) ->List[Dict[
    str, Any]]:
    """
    Fetches wallet transaction history (specific page) from Thirdweb Insight API.
    Requires THIRDWEB_CLIENT_ID environment variable. Uses Monad Testnet (10143).

    Args:
        address (str): Wallet address.
        limit (int, optional): Max items per page (max 500?). Defaults to 50.
        page (int, optional): Page number (0-indexed). Defaults to 0.
        sort_order (str, optional): 'asc' or 'desc'. Defaults to 'desc'.
        timestamp_gte (int, optional): Unix timestamp to filter >=. Defaults to None.

    Returns:
        list: List of raw transaction dicts from Insight API for the requested page.
    Raises:
        ValueError: If inputs are invalid or Client ID is missing.
        ConnectionError: If API call fails.
    """
    print(
        f'SERVICE (Insight): Getting Tx History for {address} (Page: {page}, Limit: {limit})'
        , file=sys.stderr)
    client_id = os.getenv('THIRDWEB_CLIENT_ID')
    if not client_id:
        raise ValueError('THIRDWEB_CLIENT_ID environment variable is not set.')
    w3 = get_w3()
    if not w3:
        raise ConnectionError(
            'Web3 connection not available for address validation.')
    try:
        checksum_address = w3.to_checksum_address(address)
    except (InvalidAddress, ValueError):
        raise ValueError(f'Invalid address format: {address}')
    if not isinstance(page, int) or page < 0:
        raise ValueError('Page must be a non-negative integer.')
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError('Limit must be between 1 and 500.')
    sort_order = sort_order.lower()
    if sort_order not in ['asc', 'desc']:
        raise ValueError("sort_order must be 'asc' or 'desc'.")
    chain_id = 10143
    insight_url = (
        f'https://insight.thirdweb.com/v1/wallets/{checksum_address}/transactions'
        )
    params = {'chain': str(chain_id), 'clientId': client_id, 'limit': limit,
        'page': page, 'sort_order': sort_order}
    if timestamp_gte is not None:
        if not isinstance(timestamp_gte, int) or timestamp_gte < 0:
            raise ValueError(
                'timestamp_filter_gte must be a non-negative integer Unix timestamp.'
                )
        params['filter_block_timestamp_gte'] = timestamp_gte
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    print(
        f'Calling Insight Tx History API: {insight_url} with params: {params}',
        file=sys.stderr)
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True
            ) as client:
            response = await client.get(insight_url, params=params, headers
                =headers)
            print(f'Insight Tx History Status Code: {response.status_code}',
                file=sys.stderr)
            response.raise_for_status()
            fetched_data = response.json()
            if isinstance(fetched_data, dict
                ) and 'data' in fetched_data and isinstance(fetched_data[
                'data'], list):
                print(
                    f"Successfully fetched {len(fetched_data['data'])} transactions."
                    , file=sys.stderr)
                return fetched_data['data']
            else:
                print(
                    f'Warning: Unexpected format from Insight Tx History endpoint: {fetched_data}'
                    , file=sys.stderr)
                raise ValueError(
                    'Could not parse transaction list from Thirdweb Insight response.'
                    )
    except httpx.HTTPStatusError as e:
        print(
            f'HTTP error fetching Insight Tx History: {e.response.status_code} - {e.response.text}'
            , file=sys.stderr)
        raise ConnectionError(
            f'Failed to fetch Tx History from Thirdweb Insight: HTTP {e.response.status_code}'
            )
    except Exception as e:
        print(f'Error fetching Insight Tx History: {type(e).__name__} - {e}',
            file=sys.stderr)
        raise ConnectionError(f'Failed to fetch Tx History: {e}')

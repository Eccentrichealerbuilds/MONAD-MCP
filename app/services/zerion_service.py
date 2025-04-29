import httpx
import os
import sys
import asyncio
from typing import Dict, Any, List, Optional
from app.core.web3_setup import get_w3
from app.core.utils import attrdict_to_dict
from web3 import Web3
from web3.exceptions import InvalidAddress
w3 = get_w3()


def _parse_zerion_token_data(position_list: List[Dict[str, Any]]) ->List[Dict
    [str, str]]:
    tokens = []
    for position in position_list:
        if position.get('type') == 'positions':
            attributes = position.get('attributes', {})
            fungible_info = attributes.get('fungible_info')
            quantity_info = attributes.get('quantity')
            flags = attributes.get('flags', {})
            is_trash = flags.get('trash', False)
            is_native = flags.get('native', False)
            if (fungible_info and quantity_info and not is_trash and not
                is_native):
                name = fungible_info.get('name', 'N/A')
                symbol = fungible_info.get('symbol', 'N/A')
                balance_str = quantity_info.get('numeric', '0')
                tokens.append({'name': name, 'symbol': symbol,
                    'balance_exact': balance_str})
    return tokens


async def get_monad_erc20_balances(address: str) ->List[Dict[str, Any]]:
    """Gets richer ERC20 balances using Zerion /positions API."""
    print(
        f'SERVICE (Zerion): Getting Monad ERC20 balances for {address} via Zerion Positions...'
        , file=sys.stderr)
    zerion_api_key = os.getenv('ZERION_API_KEY')
    if not zerion_api_key:
        raise ValueError('ZERION_API_KEY environment variable is not set.')
    w3 = get_w3()
    if not w3:
        raise ConnectionError(
            'Web3 connection not available for address validation.')
    try:
        checksum_address = w3.to_checksum_address(address)
    except (InvalidAddress, ValueError):
        raise ValueError(f'Invalid address format provided: {address}')
    all_parsed_tokens = []
    page_num = 1
    api_base_url = 'https://api.zerion.io/v1/'
    endpoint_path = f'wallets/{checksum_address}/positions'
    chain_filter = 'monad-test-v2'
    page_size = 100
    current_params = {'filter[chain_ids]': chain_filter, 'page[size]':
        page_size, 'currency': 'usd', 'filter[trash]': 'no_filter',
        'filter[positions]': 'no_filter', 'sort': 'value'}
    current_endpoint_url = api_base_url + endpoint_path
    async with httpx.AsyncClient(auth=(zerion_api_key, ''), timeout=60.0,
        follow_redirects=True) as client:
        while current_endpoint_url:
            print(f'Fetching Zerion Positions page {page_num}...', end='\r',
                file=sys.stderr)
            try:
                params_to_send = current_params if page_num == 1 else None
                headers = {'accept': 'application/json', 'X-Env': 'testnet'}
                response = await client.get(current_endpoint_url, params=
                    params_to_send, headers=headers)
                print(f' -> Zerion Positions Status: {response.status_code}  ',
                    end='\r', file=sys.stderr)
                response.raise_for_status()
                api_data = response.json()
                position_list_page = api_data.get('data', [])
                parsed_page_tokens = _parse_zerion_token_data(
                    position_list_page)
                all_parsed_tokens.extend(parsed_page_tokens)
                next_page_url = api_data.get('links', {}).get('next')
                if not next_page_url:
                    print(
                        f"""
Finished fetching Zerion positions. Found {len(all_parsed_tokens)} non-native tokens."""
                        , file=sys.stderr)
                    break
                current_endpoint_url = next_page_url
                current_params = None
                page_num += 1
                await asyncio.sleep(0.5)
            except httpx.HTTPStatusError as e:
                print(
                    f"""
HTTP error fetching Zerion Positions page {page_num}: {e.response.status_code}"""
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Zerion API error: {e.response.status_code}')
            except httpx.RequestError as e:
                print(
                    f'\nNetwork error fetching Zerion Positions page {page_num}: {e}'
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Network error connecting to Zerion API: {e}')
            except Exception as e:
                print(
                    f'\nUnexpected error processing Zerion Positions page {page_num}: {e}'
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Unexpected error during Zerion positions fetch: {e}')
    return sorted(all_parsed_tokens, key=lambda x: x.get('name', '').lower())


async def get_contract_interactions(wallet_address: str) ->Dict[str, Any]:
    """Gets unique contract interactions (sent to) via Zerion /transactions API."""
    print(
        f'SERVICE (Zerion): Starting contract interaction analysis for {wallet_address}'
        , file=sys.stderr)
    global w3
    if not w3 or not w3.is_connected():
        w3 = get_w3()
    if not w3 or not w3.is_connected():
        raise ConnectionError('Monad RPC connection needed.')
    zerion_api_key = os.getenv('ZERION_API_KEY')
    if not zerion_api_key:
        raise ValueError('Zerion API Key not configured.')
    try:
        checksum_address = w3.to_checksum_address(wallet_address)
    except (InvalidAddress, ValueError):
        raise ValueError(f'Invalid address format: {wallet_address}')
    interacted_addresses = set()
    total_txns_processed = 0
    page_num = 1
    api_base_url = 'https://api.zerion.io/v1/'
    endpoint_path = f'wallets/{checksum_address}/transactions'
    chain_filter = 'monad-test-v2'
    page_size = 100
    initial_params = {'filter[chain_ids]': chain_filter, 'page[size]':
        page_size, 'currency': 'usd', 'filter[trash]': 'no_filter'}
    current_endpoint_url = api_base_url + endpoint_path
    current_params = initial_params
    async with httpx.AsyncClient(auth=(zerion_api_key, ''), timeout=60.0,
        follow_redirects=True) as client:
        while current_endpoint_url:
            print(
                f'Fetching Zerion Tx page {page_num}... Unique addresses: {len(interacted_addresses)}'
                , end='\r', file=sys.stderr)
            try:
                headers = {'accept': 'application/json', 'X-Env': 'testnet'}
                params_to_send = current_params if page_num == 1 else None
                response = await client.get(current_endpoint_url, params=
                    params_to_send, headers=headers)
                response.raise_for_status()
                api_data = response.json()
                tx_list_page = api_data.get('data', [])
                next_page_url = api_data.get('links', {}).get('next')
                if not tx_list_page and page_num == 1:
                    print(f'\nNo Zerion tx found for {wallet_address}',
                        file=sys.stderr)
                    break
                for tx in tx_list_page:
                    if tx.get('type') == 'transactions':
                        sent_to = tx.get('attributes', {}).get('sent_to')
                    if sent_to:
                        interacted_addresses.add(sent_to.lower())
                processed_count = len(tx_list_page)
                total_txns_processed += processed_count
                print(
                    f'Tx Page {page_num} OK ({total_txns_processed} total). Unique addresses: {len(interacted_addresses)}   '
                    , end='\r', file=sys.stderr)
                current_endpoint_url = next_page_url
                current_params = None
                page_num += 1
                if current_endpoint_url:
                    await asyncio.sleep(0.5)
                else:
                    print('\nEnd of Zerion tx history.', file=sys.stderr)
            except httpx.HTTPStatusError as e:
                print(
                    f'\nHTTP error (Zerion Tx page {page_num}): {e.response.status_code}'
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Zerion API error: {e.response.status_code}')
            except httpx.RequestError as e:
                print(f'\nNetwork error (Zerion Tx page {page_num}): {e}',
                    file=sys.stderr)
                raise ConnectionError(
                    f'Network error connecting to Zerion: {e}')
            except Exception as e:
                print(f'\nError processing Zerion Tx page {page_num}: {e}',
                    file=sys.stderr)
                raise ConnectionError(
                    f'Unexpected error during Zerion fetch: {e}')
    print(
        f'\nFinished Zerion fetch. Unique interacted addresses: {len(interacted_addresses)}'
        , file=sys.stderr)
    contract_addresses = set()
    if not w3:
        print('Warning: Monad RPC unavailable for contract checks.', file=
            sys.stderr)
    else:
        print('Checking addresses for contract code...', file=sys.stderr)
        checked_count = 0
        total_to_check = len(interacted_addresses)
        loop = asyncio.get_running_loop()
        for addr in interacted_addresses:
            checked_count += 1
            print(
                f'Checking contract {checked_count}/{total_to_check}: {addr[:15]}...'
                , end='\r', file=sys.stderr)
            try:
                contract_checksum = w3.to_checksum_address(addr)
                code = await loop.run_in_executor(None, w3.eth.get_code,
                    contract_checksum)
                if code and code.hex() != '0x':
                    contract_addresses.add(contract_checksum)
                await asyncio.sleep(0.05)
            except InvalidAddress:
                print(f'\nSkipping invalid address format: {addr}', file=
                    sys.stderr)
                continue
            except Exception as e:
                print(f'\nWarning: Could not check code for {addr}: {e}',
                    file=sys.stderr)
                await asyncio.sleep(0.5)
    print('\nContract check complete.', file=sys.stderr)
    sorted_contract_list = sorted(list(contract_addresses))
    return {'analysis_address': wallet_address,
        'total_transactions_processed_by_zerion': total_txns_processed,
        'unique_interacted_address_count': len(interacted_addresses),
        'unique_contract_count': len(contract_addresses),
        'contract_addresses': sorted_contract_list}


async def get_user_nft_transactions(user_address: str, limit_per_page: int=50
    ) ->List[Dict[str, Any]]:
    """
    Fetches NFT-related transactions for a user on Monad Testnet (chain 10143)
    using the Zerion Wallets Transactions API endpoint with asset type filter.
    Requires ZERION_API_KEY environment variable.

    Args:
        user_address (str): The wallet address.
        limit_per_page (int): Transactions per page (default 50).

    Returns:
        list: List of raw transaction dictionaries filtered for NFT types. Raises error on failure.
    Raises:
        ValueError: If inputs are invalid or API key is missing.
        ConnectionError: If API call fails.
    """
    print(
        f'SERVICE (Zerion): Getting Monad User NFT Transactions for {user_address}...'
        , file=sys.stderr)
    zerion_api_key = os.getenv('ZERION_API_KEY')
    if not zerion_api_key:
        raise ValueError('ZERION_API_KEY environment variable is not set.')
    global w3
    if not w3:
        w3 = get_w3()
    if not w3:
        raise ConnectionError(
            'Web3 connection not available for address validation.')
    try:
        checksum_address = w3.to_checksum_address(user_address)
    except (InvalidAddress, ValueError):
        raise ValueError(f'Invalid address format provided: {user_address}')
    all_nft_transactions = []
    page_num = 1
    api_base_url = 'https://api.zerion.io/v1/'
    endpoint_path = f'wallets/{checksum_address}/transactions'
    current_endpoint_url = api_base_url + endpoint_path
    chain_filter = 'monad-test-v2'
    current_params = {'filter[chain_ids]': chain_filter, 'page[size]':
        limit_per_page, 'currency': 'usd', 'filter[trash]': 'no_filter',
        'filter[asset_types]': 'nft'}
    headers = {'accept': 'application/json', 'X-Env': 'testnet'}
    async with httpx.AsyncClient(auth=(zerion_api_key, ''), timeout=60.0,
        follow_redirects=True) as client:
        while current_endpoint_url:
            print(f'Fetching Zerion NFT Tx page {page_num}...', end='\r',
                file=sys.stderr)
            try:
                params_to_send = current_params if page_num == 1 else None
                response = await client.get(current_endpoint_url, params=
                    params_to_send, headers=headers)
                print(f' -> Zerion Tx Status: {response.status_code}  ',
                    end='\r', file=sys.stderr)
                response.raise_for_status()
                api_data = response.json()
                tx_list_page = api_data.get('data', [])
                next_page_url = api_data.get('links', {}).get('next')
                if not tx_list_page and page_num == 1:
                    print(
                        f"""
No NFT transactions found via Zerion for {checksum_address} on {chain_filter}."""
                        , file=sys.stderr)
                    break
                all_nft_transactions.extend(tx_list_page)
                print(
                    f'Page {page_num} OK. Total NFT txns so far: {len(all_nft_transactions)}   '
                    , end='\r', file=sys.stderr)
                if not next_page_url:
                    print('\nReached end of Zerion NFT transaction history.',
                        file=sys.stderr)
                    break
                current_endpoint_url = next_page_url
                current_params = None
                page_num += 1
                await asyncio.sleep(0.5)
            except httpx.HTTPStatusError as e:
                print(
                    f"""
HTTP error fetching Zerion NFT Tx page {page_num}: {e.response.status_code} - {e.response.text}"""
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Zerion API error: {e.response.status_code}')
            except httpx.RequestError as e:
                print(
                    f'\nNetwork error fetching Zerion NFT Tx page {page_num}: {e}'
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Network error connecting to Zerion API: {e}')
            except Exception as e:
                print(
                    f"""
Unexpected error processing Zerion NFT Tx page {page_num}: {type(e).__name__} - {e}"""
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Unexpected error during Zerion NFT Tx fetch: {e}')
    print(
        f"""
Finished fetching Zerion NFT transactions. Total events found: {len(all_nft_transactions)}"""
        , file=sys.stderr)
    return all_nft_transactions

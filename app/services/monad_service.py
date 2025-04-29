import httpx
import os
import sys
import asyncio
from web3 import Web3
from web3.exceptions import InvalidAddress, TransactionNotFound, BlockNotFound, ContractLogicError, ABIFunctionNotFound
from web3.types import HexBytes
from collections.abc import Mapping
from typing import Union, Dict, Any, List, Optional
from pydantic import ValidationError
from app.core.web3_setup import get_w3
from app.core.utils import attrdict_to_dict
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


async def get_balance(address: str) ->Dict[str, str]:
    """Service logic to get NATIVE MON balance."""
    global w3
    if not w3 or not w3.is_connected():
        w3 = get_w3()
    if not w3 or not w3.is_connected():
        raise ConnectionError('Monad RPC connection not available.')
    try:
        checksum_address = w3.to_checksum_address(address)
    except (InvalidAddress, ValueError):
        raise ValueError(f'Invalid address format: {address}')
    try:
        loop = asyncio.get_running_loop()
        balance_wei = await loop.run_in_executor(None, w3.eth.get_balance,
            checksum_address)
        balance_mon = w3.from_wei(balance_wei, 'ether')
        return {'address': checksum_address, 'balance_wei': str(balance_wei
            ), 'balance_mon': f'{balance_mon:.18f}'}
    except Exception as e:
        print(f'Service Error (get_balance...): {e}', file=sys.stderr)
        raise ConnectionError(f'Could not retrieve balance: {e}')


async def get_native_monad_balance(address: str) ->str:
    """Service logic wrapped for the @mcp.tool, gets native MON balance."""
    global w3
    if not w3 or not w3.is_connected():
        w3 = get_w3()
    if not w3 or not w3.is_connected():
        raise ConnectionError('Monad RPC connection not available.')
    try:
        checksum_address = w3.to_checksum_address(address)
    except (InvalidAddress, ValueError):
        raise ValueError(f'Invalid address format: {address}')
    try:
        loop = asyncio.get_running_loop()
        balance_wei = await loop.run_in_executor(None, w3.eth.get_balance,
            checksum_address)
        balance_mon = w3.from_wei(balance_wei, 'ether')
        result_str = f'{balance_mon:.18f} MON'
        print(f'SERVICE: Native balance found: {result_str}', file=sys.stderr)
        return result_str
    except Exception as e:
        print(f'Service Error (get_native_monad_balance...): {e}', file=sys
            .stderr)
        raise ConnectionError(f'Could not retrieve native balance: {e}')


async def get_transaction(tx_hash: str) ->Dict[str, Any]:
    """Service logic to get transaction details."""
    global w3
    if not w3 or not w3.is_connected():
        w3 = get_w3()
    if not w3 or not w3.is_connected():
        raise ConnectionError('Monad RPC connection not available.')
    if not tx_hash.startswith('0x') or len(tx_hash) != 66:
        raise ValueError('Invalid transaction hash format.')
    try:
        loop = asyncio.get_running_loop()
        tx_data = await loop.run_in_executor(None, w3.eth.get_transaction,
            tx_hash)
        if tx_data is None:
            raise FileNotFoundError(
                f'Transaction not found or pending: {tx_hash}')
        return attrdict_to_dict(tx_data)
    except TransactionNotFound:
        raise FileNotFoundError(f'Transaction not found: {tx_hash}')
    except Exception as e:
        print(f'Service Error (get_transaction...): {e}', file=sys.stderr)
        raise ConnectionError(f'Could not retrieve transaction details: {e}')


async def get_block(block_identifier: Union[int, str]) ->Dict[str, Any]:
    """Service logic to get block details."""
    global w3
    if not w3 or not w3.is_connected():
        w3 = get_w3()
    if not w3 or not w3.is_connected():
        raise ConnectionError('Monad RPC connection not available.')
    block_id: Union[int, str]
    if isinstance(block_identifier, str):
        block_id_lower = block_identifier.lower()
        if block_id_lower in ['latest', 'earliest', 'pending']:
            block_id = block_id_lower
        else:
            try:
                block_id = int(block_identifier)
                assert block_id >= 0
            except (ValueError, AssertionError):
                raise ValueError('Invalid block identifier string.')
    elif isinstance(block_identifier, int):
        if block_identifier < 0:
            raise ValueError('Block number cannot be negative.')
        block_id = block_identifier
    else:
        raise TypeError('Invalid block identifier type.')
    if block_id is None:
        raise ValueError('Could not parse block identifier.')
    try:
        loop = asyncio.get_running_loop()
        block_data = await loop.run_in_executor(None, w3.eth.get_block,
            block_id, False)
        if block_data is None:
            raise FileNotFoundError(f'Block not found: {block_identifier}')
        return attrdict_to_dict(block_data)
    except BlockNotFound:
        raise FileNotFoundError(f'Block not found: {block_identifier}')
    except Exception as e:
        print(f'Service Error (get_block...): {e}', file=sys.stderr)
        raise ConnectionError(f'Could not retrieve block details: {e}')


async def read_contract(contract_address: str, function_name: str, args:
    List[Any], abi: Optional[List[Dict[str, Any]]]=None) ->Any:
    """Service logic to call read-only contract functions, fetching ABI if needed."""
    global w3
    if not w3 or not w3.is_connected():
        w3 = get_w3()
    if not w3 or not w3.is_connected():
        raise ConnectionError('Monad RPC connection not available.')
    try:
        checksum_address = w3.to_checksum_address(contract_address)
    except (InvalidAddress, ValueError):
        raise ValueError(f'Invalid contract address format: {contract_address}'
            )
    fetched_abi = None
    if not abi:
        print(
            f'ABI not provided for {checksum_address}. Fetching from Thirdweb Insight...'
            , file=sys.stderr)
        client_id = os.getenv('THIRDWEB_CLIENT_ID')
        if not client_id:
            raise ValueError('ABI fetch requires THIRDWEB_CLIENT_ID env var.')
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
                print(f'Insight API Status Code: {response.status_code}',
                    file=sys.stderr)
                response.raise_for_status()
                fetched_data = response.json()
                print('Insight API JSON parsed.', file=sys.stderr)
                abi_list = None
                if isinstance(fetched_data, list):
                    abi_list = fetched_data
                elif isinstance(fetched_data, dict):
                    if 'result' in fetched_data and isinstance(fetched_data
                        ['result'], list):
                        abi_list = fetched_data['result']
                    elif 'abi' in fetched_data and isinstance(fetched_data[
                        'abi'], list):
                        abi_list = fetched_data['abi']
                if abi_list is None:
                    raise ValueError(
                        'Could not parse ABI list from Insight response.')
                print(f'Fetched ABI with {len(abi_list)} items.', file=sys.
                    stderr)
                abi = abi_list
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise FileNotFoundError(
                    f'ABI not found on Thirdweb Insight (404).')
            else:
                raise ConnectionError(
                    f'Failed to fetch ABI: HTTP {e.response.status_code}')
        except Exception as e:
            raise ConnectionError(f'Failed to fetch ABI: {e}')
    if not isinstance(abi, list) or not abi:
        raise ValueError('Invalid or empty ABI.')
    try:
        contract = w3.eth.contract(address=checksum_address, abi=abi)
        if not hasattr(contract.functions, function_name):
            raise ValueError(f"Function '{function_name}' not found in ABI.")
        contract_function = getattr(contract.functions, function_name)
        processed_args = [(w3.to_checksum_address(arg) if isinstance(arg,
            str) and w3.is_address(arg) else arg) for arg in args]
        print(
            f"Calling contract function '{function_name}' at {checksum_address}..."
            , file=sys.stderr)
        loop = asyncio.get_running_loop()
        raw_result = await loop.run_in_executor(None, contract_function(*
            processed_args).call)
        if isinstance(raw_result, int) and raw_result > 2 ** 53:
            return str(raw_result)
        if isinstance(raw_result, bytes):
            return HexBytes(raw_result).hex()
        if isinstance(raw_result, (list, tuple)):
            return [(str(item) if isinstance(item, int) and item > 2 ** 53 else
                HexBytes(item).hex() if isinstance(item, bytes) else item) for
                item in raw_result]
        return raw_result
    except ContractLogicError as e:
        raise ValueError(f'Contract execution reverted: {e}')
    except ABIFunctionNotFound:
        raise ValueError(f"Function '{function_name}' ABI signature mismatch.")
    except ValidationError as e:
        raise ValueError(
            f"Invalid arguments for function '{function_name}': {e}")
    except Exception as e:
        print(f'Service Error (read_contract...): {e}', file=sys.stderr)
        raise ConnectionError(f'Could not read contract: {e}')


async def get_contract_interactions(wallet_address: str) ->Dict[str, Any]:
    """Gets unique contract interactions (sent to) via Zerion API."""
    print(f'Starting Zerion interaction analysis for {wallet_address}',
        file=sys.stderr)
    global w3
    if not w3 or not w3.is_connected():
        w3 = get_w3()
    if not w3 or not w3.is_connected():
        raise ConnectionError(
            'Monad RPC connection needed for contract checks.')
    zerion_api_key = os.getenv('ZERION_API_KEY')
    if not zerion_api_key:
        raise ValueError('Zerion API Key not configured.')
    interacted_addresses = set()
    total_txns_processed = 0
    page_num = 1
    api_base_url = 'https://api.zerion.io/v1/'
    endpoint_path = f'wallets/{wallet_address}/transactions'
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
                f'Fetching Zerion page {page_num}... Unique addresses: {len(interacted_addresses)}'
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
                    f'Page {page_num} OK ({total_txns_processed} total). Unique addresses: {len(interacted_addresses)}   '
                    , end='\r', file=sys.stderr)
                current_endpoint_url = next_page_url
                current_params = None
                page_num += 1
                if current_endpoint_url:
                    await asyncio.sleep(0.5)
                else:
                    print('\nEnd of Zerion history.', file=sys.stderr)
            except httpx.HTTPStatusError as e:
                print(
                    f"""
HTTP error (Zerion page {page_num}): {e.response.status_code} - {e.response.text}"""
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Zerion API error: {e.response.status_code}')
            except httpx.RequestError as e:
                print(f'\nNetwork error (Zerion page {page_num}): {e}',
                    file=sys.stderr)
                raise ConnectionError(
                    f'Network error connecting to Zerion: {e}')
            except Exception as e:
                print(f'\nError processing Zerion page {page_num}: {e}',
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
                checksum_addr = w3.to_checksum_address(addr)
                code = await loop.run_in_executor(None, w3.eth.get_code,
                    checksum_addr)
                if code and code.hex() != '0x':
                    contract_addresses.add(checksum_addr)
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


async def get_monad_erc20_balances(address: str) ->List[Dict[str, Any]]:
    """Gets richer ERC20 balances using Zerion /positions API."""
    print(
        f'SERVICE: Getting Monad ERC20 balances for {address} via Zerion Positions...'
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
                print(f'Zerion Positions Status Code: {response.status_code}',
                    file=sys.stderr)
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
Finished fetching Zerion positions. Found {len(all_parsed_tokens)} non-native tokens total."""
                        , file=sys.stderr)
                    break
                current_endpoint_url = next_page_url
                current_params = None
                page_num += 1
                await asyncio.sleep(0.5)
            except httpx.HTTPStatusError as e:
                print(
                    f"""
HTTP error fetching Zerion Positions page {page_num}: {e.response.status_code} - {e.response.text}"""
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
                    f"""
Unexpected error processing Zerion Positions page {page_num}: {type(e).__name__} - {e}"""
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Unexpected error during Zerion positions fetch: {e}')
    return sorted(all_parsed_tokens, key=lambda x: x.get('name', '').lower())


async def get_nft_collection_stats(wallet_address: str) ->List[Dict[str, Any]]:
    """
    Fetches detailed NFT collection statistics for a wallet on Monad Testnet (chain 10143)
    using the Magic Eden Collections V3 API endpoint.
    Requires MAGIC_EDEN_API_KEY environment variable.
    Args: wallet_address (str): The wallet address.
    Returns: list: A list of raw collection stat dicts from ME API. Raises error on failure.
    Raises: ValueError, ConnectionError.
    """
    print(
        f'SERVICE: Getting Monad NFT collection stats for {wallet_address} via Magic Eden...'
        , file=sys.stderr)
    magic_eden_key = os.getenv('MAGIC_EDEN_API_KEY')
    if not magic_eden_key:
        raise ValueError('MAGIC_EDEN_API_KEY environment variable is not set.')
    global w3
    if not w3:
        w3 = get_w3()
    if not w3:
        raise ConnectionError(
            'Web3 connection not available for address validation.')
    try:
        checksum_address = w3.to_checksum_address(wallet_address)
    except (InvalidAddress, ValueError):
        raise ValueError(f'Invalid address format provided: {wallet_address}')
    all_collections_data = []
    current_offset = 0
    page_limit = 100
    api_base_url = 'https://api-mainnet.magiceden.dev'
    network = 'monad-testnet'
    endpoint_path = (
        f'/v3/rtp/{network}/users/{checksum_address}/collections/v3')
    url = api_base_url + endpoint_path
    headers = {'accept': '*/*', 'Authorization': f'Bearer {magic_eden_key}'}
    print(f'Calling Magic Eden Endpoint: {url}', file=sys.stderr)
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True
        ) as client:
        while True:
            params = {'limit': page_limit, 'offset': current_offset,
                'includeTopBid': True, 'includeLiquidCount': True}
            print(
                f'Fetching ME Collections page: Offset={current_offset}, Limit={page_limit}'
                , end='\r', file=sys.stderr)
            try:
                response = await client.get(url, headers=headers, params=params
                    )
                print(f' -> ME Status: {response.status_code}', end='\r',
                    file=sys.stderr)
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and 'collections' in data:
                    collections_page = data['collections']
                    if not collections_page:
                        print(
                            '\nNo more collections found on this page or subsequent pages.'
                            , file=sys.stderr)
                        break
                    all_collections_data.extend(collections_page)
                    print(
                        f'Page OK. Total collections fetched so far: {len(all_collections_data)}   '
                        , end='\r', file=sys.stderr)
                    if len(collections_page) < page_limit:
                        print(
                            '\nReached end of Magic Eden collections list (received < limit).'
                            , file=sys.stderr)
                        break
                    current_offset += page_limit
                    await asyncio.sleep(0.5)
                else:
                    print(
                        f'\nError: Unexpected API response format from Magic Eden: {data}'
                        , file=sys.stderr)
                    raise ValueError(
                        'Unexpected format from Magic Eden collections endpoint.'
                        )
            except httpx.HTTPStatusError as e:
                print(
                    f"""
HTTP error fetching Magic Eden collections page: {e.response.status_code} - {e.response.text}"""
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Magic Eden API error: {e.response.status_code}')
            except httpx.RequestError as e:
                print(
                    f'\nNetwork error fetching Magic Eden collections page: {e}'
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Network error connecting to Magic Eden API: {e}')
            except Exception as e:
                print(
                    f"""
Unexpected error processing Magic Eden collections page: {type(e).__name__} - {e}"""
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Unexpected error during Magic Eden fetch: {e}')
    print(
        f'\nFinished fetching Magic Eden collections. Total found: {len(all_collections_data)}'
        , file=sys.stderr)
    return all_collections_data

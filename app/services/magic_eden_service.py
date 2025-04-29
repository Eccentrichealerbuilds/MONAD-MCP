import httpx
import os
import sys
import requests
import asyncio
import urllib.parse
from typing import Dict, Any, List, Union, Optional
from web3 import Web3
from web3.exceptions import InvalidAddress
from web3.types import HexBytes
from app.core.web3_setup import get_w3
w3 = get_w3()
from app.core.utils import attrdict_to_dict


async def get_nft_collection_stats(wallet_address: str) ->List[Dict[str, Any]]:
    """
    Fetches detailed NFT collection statistics for a wallet on Monad Testnet (chain 10143)
    using the Magic Eden Collections V3 API endpoint.
    Requires MAGIC_EDEN_API_KEY environment variable.
    Args: wallet_address (str): The wallet address.
    Returns: list: List of raw collection stat dicts from ME API. Raises error on failure.
    Raises: ValueError, ConnectionError.
    """
    print(
        f'SERVICE: Getting Monad NFT collection stats for {wallet_address} via Magic Eden...'
        , file=sys.stderr)
    magic_eden_key = os.getenv('MAGIC_EDEN_API_KEY')
    w3 = get_w3()
    if not magic_eden_key:
        raise ValueError('MAGIC_EDEN_API_KEY environment variable is not set.')
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
            print(f'Fetching ME Collections page: Offset={current_offset}',
                end='\r', file=sys.stderr)
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
                        print('\nNo more collections found.', file=sys.stderr)
                        break
                    all_collections_data.extend(collections_page)
                    print(
                        f'Page OK. Total collections: {len(all_collections_data)}   '
                        , end='\r', file=sys.stderr)
                    if len(collections_page) < page_limit:
                        print('\nReached end of ME collections list.', file
                            =sys.stderr)
                        break
                    current_offset += page_limit
                    await asyncio.sleep(0.5)
                else:
                    print(
                        f'\nError: Unexpected API format from ME collections: {data}'
                        , file=sys.stderr)
                    raise ValueError(
                        'Unexpected format from ME collections endpoint.')
            except httpx.HTTPStatusError as e:
                print(
                    f'\nHTTP error fetching ME collections: {e.response.status_code}'
                    , file=sys.stderr)
                raise ConnectionError(f'ME API error: {e.response.status_code}'
                    )
            except httpx.RequestError as e:
                print(f'\nNetwork error fetching ME collections: {e}', file
                    =sys.stderr)
                raise ConnectionError(
                    f'Network error connecting to ME API: {e}')
            except Exception as e:
                print(f'\nUnexpected error processing ME collections: {e}',
                    file=sys.stderr)
                raise ConnectionError(f'Unexpected error during ME fetch: {e}')
    print(
        f'\nFinished fetching ME collections. Total found: {len(all_collections_data)}'
        , file=sys.stderr)
    return all_collections_data


async def get_nft_activity(contract_address: str, token_id: str) ->List[Dict
    [str, Any]]:
    """
    Fetches the activity history for a specific NFT on Monad Testnet (chain 10143)
    using the Magic Eden Tokens Activity V5 API endpoint.
    Requires MAGIC_EDEN_API_KEY environment variable.
    Args:
        contract_address (str): The NFT collection contract address.
        token_id (str): The specific token ID within the collection.
    Returns:
        list: A list of raw activity event dictionaries from ME API. Raises error on failure.
    Raises:
        ValueError: If inputs are invalid or API key is missing.
        ConnectionError: If API call fails.
    """
    print(
        f'SERVICE: Getting Monad NFT Activity for {contract_address}:{token_id} via Magic Eden...'
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
        checksum_address = w3.to_checksum_address(contract_address)
    except (InvalidAddress, ValueError):
        raise ValueError(
            f'Invalid contract address format provided: {contract_address}')
    if not token_id or not isinstance(token_id, str):
        raise ValueError(f'Invalid token_id provided: {token_id}')
    all_activities = []
    current_continuation = None
    page_num = 1
    page_limit = 20
    api_base_url = 'https://api-mainnet.magiceden.dev'
    network = 'monad-testnet'
    token_identifier_raw = f'{checksum_address}:{token_id}'
    token_identifier_encoded = urllib.parse.quote(token_identifier_raw)
    endpoint_path = (
        f'/v3/rtp/{network}/tokens/{token_identifier_encoded}/activity/v5')
    current_url = api_base_url + endpoint_path
    headers = {'accept': '*/*', 'Authorization': f'Bearer {magic_eden_key}'}
    initial_params = {'limit': page_limit, 'sortBy': 'eventTimestamp',
        'includeMetadata': True}
    print(f'Calling Magic Eden Endpoint initially: {current_url}', file=sys
        .stderr)
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True
        ) as client:
        while current_url:
            print(f'Fetching ME Activity page {page_num}...', end='\r',
                file=sys.stderr)
            try:
                params_to_send = initial_params if page_num == 1 else None
                response = await client.get(current_url, headers=headers,
                    params=params_to_send)
                print(f' -> ME Status: {response.status_code}  ', end='\r',
                    file=sys.stderr)
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict):
                    activities_page = data.get('activities', [])
                    if not activities_page and page_num == 1:
                        print(
                            f'\nNo activity found via Magic Eden for {token_identifier_raw}.'
                            , file=sys.stderr)
                        break
                    all_activities.extend(activities_page)
                    print(
                        f'Page {page_num} OK. Total activities so far: {len(all_activities)}   '
                        , end='\r', file=sys.stderr)
                    next_continuation_url = data.get('continuation')
                    if not next_continuation_url:
                        print(f'\nReached end of Magic Eden activity feed.',
                            file=sys.stderr)
                        break
                    current_url = next_continuation_url
                    page_num += 1
                    await asyncio.sleep(0.5)
                else:
                    print(
                        f'\nError: Unexpected API format from ME activity: {data}'
                        , file=sys.stderr)
                    raise ValueError(
                        'Unexpected format from Magic Eden activity endpoint.')
            except httpx.HTTPStatusError as e:
                print(
                    f"""
HTTP error fetching ME activity page {page_num}: {e.response.status_code} - {e.response.text}"""
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Magic Eden API error: {e.response.status_code}')
            except httpx.RequestError as e:
                print(
                    f'\nNetwork error fetching ME activity page {page_num}: {e}'
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Network error connecting to Magic Eden API: {e}')
            except Exception as e:
                print(
                    f"""
Unexpected error processing ME activity page {page_num}: {type(e).__name__} - {e}"""
                    , file=sys.stderr)
                raise ConnectionError(
                    f'Unexpected error during Magic Eden activity fetch: {e}')
    print(
        f'\nFinished fetching Magic Eden activity. Total events found: {len(all_activities)}'
        , file=sys.stderr)
    return all_activities


async def get_user_nft_activity(user_address: str, limit_per_page: int=50
    ) ->List[Dict[str, Any]]:
    """
    Fetches the MOST RECENT NFT activity feed (up to limit_per_page items) for a user
    on Monad Testnet (chain 10143) using the Magic Eden User Activity V6 API endpoint.
    Does NOT automatically fetch all pages.
    Requires MAGIC_EDEN_API_KEY environment variable.

    Args:
        user_address (str): The wallet address.
        limit_per_page (int): Max number of activities to fetch. Defaults to 50. Max likely 100-500.

    Returns:
        list: List of raw activity event dictionaries from ME API. Raises error on failure.
    Raises:
        ValueError: If inputs are invalid or API key is missing.
        ConnectionError: If API call fails.
    """
    print(
        f'SERVICE: Getting {limit_per_page} most recent Monad User NFT Activity for {user_address} via ME...'
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
        checksum_address = w3.to_checksum_address(user_address)
    except (InvalidAddress, ValueError):
        raise ValueError(f'Invalid address format provided: {user_address}')
    try:
        limit = int(limit_per_page)
        if not 1 <= limit <= 1000:
            print(
                f'Warning: Requested limit {limit} outside reasonable range 1-500. Clamping to 50.'
                , file=sys.stderr)
            limit = 100
    except ValueError:
        print(
            f"Warning: Invalid limit '{limit_per_page}' provided. Using default 20."
            , file=sys.stderr)
        limit = 20
    api_base_url = 'https://api-mainnet.magiceden.dev'
    network = 'monad-testnet'
    endpoint_path = f'/v3/rtp/{network}/users/activity/v6'
    url = api_base_url + endpoint_path
    headers = {'accept': '*/*', 'Authorization': f'Bearer {magic_eden_key}',
        'User-Agent': 'Mozilla/5.0'}
    params = {'users': checksum_address, 'limit': limit, 'sortBy':
        'eventTimestamp', 'includeMetadata': False}
    print(f'Calling Magic Eden Endpoint: {url}', file=sys.stderr)
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True
            ) as client:
            print(f'Fetching ME User Activity page 1 (Limit={limit})...',
                file=sys.stderr)
            response = await client.get(url, headers=headers, params=params)
            print(f' -> ME Status: {response.status_code}', file=sys.stderr)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and 'activities' in data:
                activities_page = data.get('activities', [])
                print(
                    f'Finished fetching ME user activity. Found {len(activities_page)} events.'
                    , file=sys.stderr)
                return activities_page
            else:
                print(
                    f'\nError: Unexpected API format from ME user activity: {data}'
                    , file=sys.stderr)
                raise ValueError(
                    'Unexpected format from Magic Eden user activity endpoint.'
                    )
    except httpx.HTTPStatusError as e:
        print(
            f"""
HTTP error fetching ME User Activity: {e.response.status_code} - {e.response.text}"""
            , file=sys.stderr)
        raise ConnectionError(f'Magic Eden API error: {e.response.status_code}'
            )
    except httpx.RequestError as e:
        print(f'\nNetwork error fetching ME User Activity: {e}', file=sys.
            stderr)
        raise ConnectionError(
            f'Network error connecting to Magic Eden API: {e}')
    except Exception as e:
        print(
            f'\nUnexpected error processing ME User Activity: {type(e).__name__} - {e}'
            , file=sys.stderr)
        raise ConnectionError(
            f'Unexpected error during Magic Eden user activity fetch: {e}')


async def get_trending_collections(limit: int=20, period: str='1d', sort_by:
    str='sales') ->List[Dict[str, Any]]:
    """
    Fetches trending NFT collections on Monad Testnet (chain 10143)
    from the Magic Eden Trending Collections V1 API endpoint.
    Requires MAGIC_EDEN_API_KEY environment variable.

    Args:
        limit (int, optional): Number of collections to fetch. Defaults to 20.
        period (str, optional): Time period. Defaults to '1d'.
        sort_by (str, optional): Sorting criteria. Defaults to 'sales'.

    Returns:
        list: List of raw trending collection data objects from ME API. Raises error on failure.
    Raises:
        ValueError: If inputs are invalid or API key is missing.
        ConnectionError: If API call fails.
    """
    print(
        f'SERVICE: Getting Top {limit} Trending Monad Collections ({period}, by {sort_by}) via Magic Eden...'
        , file=sys.stderr)
    magic_eden_key = os.getenv('MAGIC_EDEN_API_KEY')
    if not magic_eden_key:
        raise ValueError('MAGIC_EDEN_API_KEY environment variable is not set.')
    allowed_periods = ['5m', '10m', '30m', '1h', '6h', '1d', '24h', '7d', '30d'
        ]
    allowed_sort = ['sales', 'volume']
    if period.lower() not in allowed_periods:
        raise ValueError(
            f"Invalid period: '{period}'. Must be one of {allowed_periods}")
    if sort_by.lower() not in allowed_sort:
        raise ValueError(
            f"Invalid sortBy: '{sort_by}'. Must be one of {allowed_sort}")
    try:
        limit = int(limit)
        if not 1 <= limit <= 500:
            raise ValueError('Limit must be between 1 and 500')
    except ValueError:
        raise ValueError('Invalid limit value, must be an integer.')
    api_base_url = 'https://api-mainnet.magiceden.dev'
    network = 'monad-testnet'
    endpoint_path = f'/v3/rtp/{network}/collections/trending/v1'
    url = api_base_url + endpoint_path
    headers = {'accept': '*/*', 'Authorization': f'Bearer {magic_eden_key}'}
    params = {'limit': limit, 'period': period.lower(), 'sortBy': sort_by.
        lower(), 'normalizeRoyalties': True, 'useNonFlaggedFloorAsk': False}
    print(f'Calling Magic Eden Endpoint: {url} with params: {params}', file
        =sys.stderr)
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True
            ) as client:
            response = await client.get(url, headers=headers, params=params)
            print(f'ME Trending Status Code: {response.status_code}', file=
                sys.stderr)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and 'collections' in data and isinstance(
                data['collections'], list):
                print(
                    f"Successfully fetched {len(data['collections'])} trending collections."
                    , file=sys.stderr)
                return data['collections']
            else:
                print(
                    f'Error: Unexpected API response format from ME Trending: {data}'
                    , file=sys.stderr)
                raise ValueError(
                    'Unexpected format from Magic Eden trending endpoint.')
    except httpx.HTTPStatusError as e:
        print(
            f'HTTP error fetching ME Trending Collections: {e.response.status_code} - {e.response.text}'
            , file=sys.stderr)
        raise ConnectionError(f'Magic Eden API error: {e.response.status_code}'
            )
    except httpx.RequestError as e:
        print(f'Network error fetching ME Trending Collections: {e}', file=
            sys.stderr)
        raise ConnectionError(
            f'Network error connecting to Magic Eden API: {e}')
    except Exception as e:
        print(
            f'Unexpected error fetching ME Trending Collections: {type(e).__name__} - {e}'
            , file=sys.stderr)
        raise ConnectionError(
            f'Unexpected error during Magic Eden trending fetch: {e}')

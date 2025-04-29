import os
import sys
import json
import click
import asyncio
from typing import Union, Dict, Any, List, Optional
from dotenv import load_dotenv
load_dotenv()
print('MCP Server: Loaded environment variables.', file=sys.stderr)
try:
    from mcp.server.fastmcp import FastMCP
    from smolagents import tool
except ImportError as e:
    print(f'MCP Server: FATAL - Failed to import mcp/smolagents: {e}', file
        =sys.stderr)
    print(
        'MCP Server: Try running: pip install mcp smolagents click python-dotenv'
        , file=sys.stderr)
    sys.exit(1)
try:
    from app.services import monad_service
    from app.services import magic_eden_service
    from app.services import zerion_service
    from app.services import insight_service
    from app.core.web3_setup import get_w3
except ImportError as imp_err:
    print(
        'MCP Server: Error importing from app/ directory. Adding parent to path...'
        , file=sys.stderr)
    import pathlib
    parent_dir = str(pathlib.Path(__file__).parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    try:
        from app.services import monad_service
        from app.services import magic_eden_service
        from app.services import zerion_service
        from app.services import insight_service
        from app.core.web3_setup import get_w3
        print('MCP Server: Re-import successful.', file=sys.stderr)
    except ImportError as imp_err_retry:
        print(
            f'MCP Server: FATAL - Still cannot import app modules ({imp_err_retry}). Check structure and __init__.py files.'
            , file=sys.stderr)
        sys.exit(1)


@click.command()
@click.option('--transport', type=click.Choice(['stdio', 'sse']), default=
    'stdio', help='Communication protocol.')
@click.option('-p', '--port', type=int, default=8000, help=
    'Port for SSE transport.')
@click.option('--chain-id', type=int, multiple=True, default=[10143], help=
    'Chain ID(s) (default: 10143).')
def main(port: int, transport: str, chain_id: list[int]):
    """Runs the Custom Monad MCP Server with custom tools."""
    print('MCP Server: Performing initial environment checks...', file=sys.
        stderr)
    if not os.getenv('MONAD_TESTNET_RPC_URL'):
        print('MCP Server: FATAL - MONAD_TESTNET_RPC_URL not found.', file=
            sys.stderr)
        sys.exit(1)
    if not os.getenv('MAGIC_EDEN_API_KEY'):
        print(
            'MCP Server: Warning - MAGIC_EDEN_API_KEY not set (Magic Eden tools will fail).'
            , file=sys.stderr)
    if not os.getenv('ZERION_API_KEY'):
        print(
            'MCP Server: Warning - ZERION_API_KEY not set (Zerion tools will fail).'
            , file=sys.stderr)
    if not os.getenv('THIRDWEB_CLIENT_ID'):
        print(
            'MCP Server: Warning - THIRDWEB_CLIENT_ID not set (Insight tools will fail).'
            , file=sys.stderr)
    if get_w3() is None:
        print(
            'MCP Server: FATAL - Web3 instance failed to initialize (RPC connection failed?).'
            , file=sys.stderr)
        sys.exit(1)
    else:
        print('MCP Server: Web3 instance check passed.', file=sys.stderr)
    primary_chain_id = chain_id[0] if chain_id else 10143
    print(f'MCP Server: Configuring for Chain ID: {primary_chain_id}', file
        =sys.stderr)
    print(f"MCP Server: Initializing FastMCP for transport '{transport}'...",
        file=sys.stderr)
    mcp = FastMCP('Monad Custom Agent v1.1', port=port)
    print('MCP Server: Registering custom tools...', file=sys.stderr)

    @mcp.tool()
    async def get_native_monad_balance_tool(address: str) ->str:
        """Gets native MON balance for an address on Monad Testnet."""
        print(f'TOOL WRAPPER: get_native_monad_balance_tool for {address}',
            file=sys.stderr)
        return await monad_service.get_native_monad_balance(address)

    @mcp.tool()
    async def read_contract_tool(contract_address: str, function_name: str,
        args: List[Any]=[], abi: Optional[List[Dict[str, Any]]]=None) ->Any:
        """Calls read-only contract function (fetches ABI via Thirdweb Insight if needed). Requires THIRDWEB_CLIENT_ID."""
        print(
            f'TOOL WRAPPER: read_contract_tool for {contract_address} func {function_name}'
            , file=sys.stderr)
        return await monad_service.read_contract(contract_address,
            function_name, args, abi)

    @mcp.tool()
    async def get_monad_transaction_tool(tx_hash: str) ->Dict[str, Any]:
        """Gets details for a specific transaction hash on Monad Testnet."""
        print(f'TOOL WRAPPER: get_monad_transaction_tool for {tx_hash}',
            file=sys.stderr)
        return await monad_service.get_transaction(tx_hash)

    @mcp.tool()
    async def get_monad_block_tool(block_identifier: str) ->Dict[str, Any]:
        """Gets details for block number (as string) or identifier ('latest') on Monad Testnet."""
        print(
            f'TOOL WRAPPER: get_monad_block_tool for identifier: {block_identifier}'
            , file=sys.stderr)
        return await monad_service.get_block(block_identifier)

    @mcp.tool()
    async def get_contract_interactions_tool(address: str) ->Dict[str, Any]:
        """Analyzes address history for unique contracts interacted with (sent to, via Zerion /transactions). Requires ZERION_API_KEY."""
        print(f'TOOL WRAPPER: get_contract_interactions_tool for {address}',
            file=sys.stderr)
        return await zerion_service.get_contract_interactions(address)

    @mcp.tool()
    async def get_monad_erc20_balances_tool(address: str) ->List[Dict[str, Any]
        ]:
        """Gets ERC20 balances (name, symbol, balance) for an address on Monad Testnet (via Zerion /positions). Requires ZERION_API_KEY."""
        print(f'TOOL WRAPPER: get_monad_erc20_balances_tool for {address}',
            file=sys.stderr)
        return await zerion_service.get_monad_erc20_balances(address)

    @mcp.tool()
    async def get_user_nft_transactions_tool(user_address: str, limit:
        Optional[int]=50) ->List[Dict[str, Any]]:
        """Fetches NFT-related transaction history for a user on Monad Testnet (via Zerion /transactions, filtered). Requires ZERION_API_KEY."""
        print(
            f'TOOL WRAPPER: get_user_nft_transactions_tool for {user_address} limit {limit}'
            , file=sys.stderr)
        return await zerion_service.get_user_nft_transactions(user_address,
            limit_per_page=limit if limit is not None else 50)

    @mcp.tool()
    async def get_nft_collection_stats_tool(wallet_address: str) ->List[Dict
        [str, Any]]:
        """Fetches detailed stats for all NFT collections held by wallet on Monad Testnet (via Magic Eden /collections). Requires MAGIC_EDEN_API_KEY."""
        print(
            f'TOOL WRAPPER: get_nft_collection_stats_tool for {wallet_address}'
            , file=sys.stderr)
        return await magic_eden_service.get_nft_collection_stats(wallet_address
            )

    @mcp.tool()
    async def get_nft_activity_tool(contract_address: str, token_id: str
        ) ->List[Dict[str, Any]]:
        """Fetches activity history for a specific NFT on Monad Testnet (via Magic Eden /activity). Requires MAGIC_EDEN_API_KEY."""
        print(
            f'TOOL WRAPPER: get_nft_activity_tool for {contract_address}:{token_id}'
            , file=sys.stderr)
        return await magic_eden_service.get_nft_activity(contract_address,
            token_id)

    @mcp.tool()
    async def get_trending_collections_tool(limit: int=20, period: str='1d',
        sort_by: str='sales') ->List[Dict[str, Any]]:
        """
        Fetches trending NFT collections on Monad Testnet from Magic Eden API.
        Requires MAGIC_EDEN_API_KEY environment variable.

        Args:
            limit (int, optional): Number of collections to fetch (e.g., 10, 50). Defaults to 20. Max is likely 500.
            period (str, optional): Time period. Allowed values: '5m', '10m', '30m', '1h', '6h', '1d', '24h', '7d', '30d'. Defaults to '1d'.
            sort_by (str, optional): Sorting criteria. Allowed values: 'sales', 'volume'. Defaults to 'sales'.

        Returns:
            list: List of dictionaries, each containing data for one trending collection (name, image, id, ownerCount, volume, count, floorAsk, topBid). Raises error on failure.
        """
        print(
            f'TOOL WRAPPER: Called get_trending_collections_tool (limit={limit}, period={period}, sort_by={sort_by})'
            , file=sys.stderr)
        return await magic_eden_service.get_trending_collections(limit=
            limit, period=period, sort_by=sort_by)

    @mcp.tool()
    async def get_contract_abi_tool(contract_address: str) ->List[Dict[str,
        Any]]:
        """Fetches the ABI for a verified contract from Thirdweb Insight API for Monad Testnet. Requires THIRDWEB_CLIENT_ID."""
        print(
            f'TOOL WRAPPER: Called get_contract_abi_tool for {contract_address}'
            , file=sys.stderr)
        return await insight_service.get_abi_from_insight(contract_address)

    @mcp.tool()
    async def get_transaction_history_tool(address: str, limit: Optional[
        int]=50, page: Optional[int]=0, sort_order: Optional[str]='desc',
        timestamp_filter_gte: Optional[int]=None) ->List[Dict[str, Any]]:
        """Fetches a page of wallet transaction history from Thirdweb Insight API for Monad Testnet. Requires THIRDWEB_CLIENT_ID."""
        print(
            f'TOOL WRAPPER: Called get_transaction_history_tool for {address}',
            file=sys.stderr)
        return await insight_service.get_transaction_history(address=
            address, limit=limit if limit is not None else 50, page=page if
            page is not None else 0, sort_order=sort_order if sort_order is not
            None else 'desc', timestamp_gte=timestamp_filter_gte)
    print(f"MCP Server: Starting server with transport '{transport}'...",
        file=sys.stderr)
    try:
        mcp.run(transport)
    except Exception as run_err:
        print(f'MCP Server: Error during mcp.run: {run_err}', file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    print('MCP Server: Performing final environment checks...', file=sys.stderr
        )
    if not os.getenv('MONAD_TESTNET_RPC_URL'):
        print('MCP Server: Error - MONAD_TESTNET_RPC_URL not found.', file=
            sys.stderr)
        sys.exit(1)
    if not os.getenv('MAGIC_EDEN_API_KEY'):
        print('MCP Server: Warning - MAGIC_EDEN_API_KEY not set.', file=sys
            .stderr)
    if not os.getenv('ZERION_API_KEY'):
        print('MCP Server: Warning - ZERION_API_KEY not set.', file=sys.stderr)
    if not os.getenv('THIRDWEB_CLIENT_ID'):
        print(
            'MCP Server: Error - THIRDWEB_CLIENT_ID not set (Required for Insight tools).'
            , file=sys.stderr)
        sys.exit(1)
    if get_w3() is None:
        print('MCP Server: Error - Web3 instance failed.', file=sys.stderr)
        sys.exit(1)
    print('MCP Server: Checks passed, calling main()...', file=sys.stderr)
    main()
    print('MCP Server: main() finished.', file=sys.stderr)

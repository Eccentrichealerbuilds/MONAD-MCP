# mcp_server.py (Custom Monad Agent MCP Server)

import os
import sys
import json
import click
import asyncio
from typing import Union, Dict, Any, List, Optional

# Load .env file FIRST
from dotenv import load_dotenv
load_dotenv()
print("MCP Server: Loaded environment variables.", file=sys.stderr)

# Imports AFTER dotenv load
from mcp.server.fastmcp import FastMCP
# We don't need to import Thirdweb services or adapter anymore for this version
# from thirdweb_ai import Insight, Nebula, Storage, Engine
# from thirdweb_ai.adapters.mcp import add_fastmcp_tools

# Import our custom service logic
try:
    from app.services import monad_service
    from app.core.web3_setup import get_w3
except ImportError:
    print("MCP Server: Error importing from app/ directory. Adding parent to path...", file=sys.stderr)
    import pathlib
    parent_dir = str(pathlib.Path(__file__).parent)
    if parent_dir not in sys.path: sys.path.insert(0, parent_dir)
    try:
         from app.services import monad_service
         from app.core.web3_setup import get_w3
         print("MCP Server: Re-import successful.", file=sys.stderr)
    except ImportError as imp_err:
         print(f"MCP Server: FATAL - Still cannot import app modules: {imp_err}", file=sys.stderr); sys.exit(1)


@click.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio", help="Communication protocol.")
@click.option("-p", "--port", type=int, default=8000, help="Port for SSE transport.")
# Remove secret_key option as it's not directly used by this server now
# Add back if needed for specific tool authentication later
@click.option("--chain-id", type=int, multiple=True, default=[10143], help="Chain ID(s) (default: 10143).")
def main(
    port: int,
    transport: str,
    chain_id: list[int],
):
    """Runs the Custom Monad MCP Server with only custom tools."""

    # --- Initial Checks ---
    # Check only keys needed by OUR tools
    if not os.getenv("ZERION_API_KEY"):
        print("MCP Server: Warning - ZERION_API_KEY not set. Contract interaction count tool will fail.", file=sys.stderr)
    if not os.getenv("THIRDWEB_CLIENT_ID"):
         print("MCP Server: Warning - THIRDWEB_CLIENT_ID not set. Auto-ABI fetch in read_contract tool will fail.", file=sys.stderr)
    if get_w3() is None:
         print("MCP Server: Error - Web3 RPC connection failed. Most tools will fail.", file=sys.stderr)
         sys.exit(1) # Make RPC connection mandatory

    primary_chain_id = chain_id[0] if chain_id else 10143
    print(f"MCP Server: Configuring for Chain ID: {primary_chain_id}", file=sys.stderr)
    # We might need to pass this chain_id to service functions if they need it

    print(f"MCP Server: Initializing FastMCP for transport '{transport}'...", file=sys.stderr)
    mcp = FastMCP("Custom Monad Agent Only", port=port) # New Name

    # --- Remove Thirdweb Tool Initialization ---
    print("MCP Server: Skipping standard Thirdweb tool loading.", file=sys.stderr)

    # --- Add Our Custom Tools using Decorators ---
    print("MCP Server: Adding custom tools...", file=sys.stderr)

    @mcp.tool()
    async def get_native_monad_balance_tool(address: str) -> str:
        """
        Gets the native MON balance (main network coin) for an address on Monad Testnet (Chain ID 10143).
        Use this specifically for 'MON' or 'native' balance requests.
        Args: address (str): The Monad wallet address (0x...).
        Returns: str: Formatted balance string (e.g., "4.157... MON") or error message.
        """
        print(f"TOOL WRAPPER: Called get_native_monad_balance_tool for {address}", file=sys.stderr)
        try: return await monad_service.get_native_monad_balance(address)
        except Exception as e: return f"Error: {e}" # Return error string

    @mcp.tool()
    async def get_contract_interactions_tool(address: str) -> Dict[str, Any]:
        """
        Analyzes recent history for a Monad Testnet address (using Zerion API)
        to count unique contracts interacted with (sent to).
        Requires ZERION_API_KEY env var set where this server runs.
        Args: address (str): The Monad wallet address (0x...).
        Returns: dict: Counts and list of unique contract addresses. Raises error on failure.
        """
        print(f"TOOL WRAPPER: Called get_contract_interactions_tool for {address}", file=sys.stderr)
        return await monad_service.get_contract_interactions(address) # Let exceptions propagate

    @mcp.tool()
    async def read_contract_tool(
        contract_address: str,
        function_name: str,
        args: List[Any] = [],
        abi: Optional[List[Dict[str, Any]]] = None
    ) -> Any:
        """
        Calls a read-only function on a Monad Testnet contract.
        Automatically fetches ABI from Thirdweb Insight if 'abi' is omitted.
        Requires THIRDWEB_CLIENT_ID env var if fetching ABI.
        Args: contract_address (str), function_name (str), args (list, optional), abi (list, optional).
        Returns: Any: The result from the contract function call. Raises error on failure.
        """
        print(f"TOOL WRAPPER: Called read_contract_tool for {contract_address} func {function_name}", file=sys.stderr)
        return await monad_service.read_contract(contract_address, function_name, args, abi) # Let exceptions propagate

    @mcp.tool()
    async def get_monad_erc20_balances_tool(address: str) -> List[Dict[str, Any]]:
        """
        Gets the list of ERC20 token balances for a given wallet address specifically on Monad Testnet (Chain ID 10143).
        Uses Thirdweb Insight API via Secret Key (requires THIRDWEB_SECRET_KEY env var).
        Args: address (str): The Monad wallet address (0x...).
        Returns: list: A list of token balances [{'token_address': ..., 'balance': ...}]. Raises error on failure.
        """
        # NOTE: This still requires THIRDWEB_SECRET_KEY based on our previous successful curl test for this endpoint
        if not os.getenv("THIRDWEB_SECRET_KEY"):
             print("MCP Server: Error - THIRDWEB_SECRET_KEY needed for get_monad_erc20_balances_tool.", file=sys.stderr)
             # Raise or return error? Let's raise for consistency
             raise ValueError("THIRDWEB_SECRET_KEY environment variable needed for this tool.")
        print(f"TOOL WRAPPER: Called get_monad_erc20_balances_tool for {address}", file=sys.stderr)
        return await monad_service.get_monad_erc20_balances(address) # Let exceptions propagate

    # --- NEW: Add wrappers for basic reads ---
    @mcp.tool()
    async def get_monad_transaction_tool(tx_hash: str) -> Dict[str, Any]:
        """
        Gets details for a specific transaction hash on Monad Testnet.
        Args: tx_hash (str): The transaction hash (0x...).
        Returns: dict: Dictionary of transaction details. Raises error on failure.
        """
        print(f"TOOL WRAPPER: Called get_monad_transaction_tool for {tx_hash}", file=sys.stderr)
        return await monad_service.get_transaction(tx_hash) # Let exceptions propagate

    @mcp.tool()
    async def get_monad_block_tool(block_identifier: Union[int, str]) -> Dict[str, Any]:
        """
        Gets details for a specific block number or identifier ('latest') on Monad Testnet.
        Args: block_identifier (int | str): Block number or 'latest', 'earliest', 'pending'.
        Returns: dict: Dictionary of block details. Raises error on failure.
        """
        print(f"TOOL WRAPPER: Called get_monad_block_tool for {block_identifier}", file=sys.stderr)
        return await monad_service.get_block(block_identifier) # Let exceptions propagate

    print("MCP Server: Custom tools added.", file=sys.stderr)

    # --- Run the Server ---
    print(f"MCP Server: Starting server with transport '{transport}'...", file=sys.stderr)
    try:
        mcp.run(transport) # This blocks and handles communication
    except Exception as run_err:
        print(f"MCP Server: Error during mcp.run: {type(run_err).__name__} - {run_err}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # Check essential env vars for our custom tools
    if not os.getenv("MONAD_TESTNET_RPC_URL"):
         print("MCP Server: Error - MONAD_TESTNET_RPC_URL not found.", file=sys.stderr); sys.exit(1)
    # Add checks for ZERION_API_KEY, THIRDWEB_CLIENT_ID, THIRDWEB_SECRET_KEY if tools strictly require them at start
    if not os.getenv("ZERION_API_KEY"): print("MCP Server: Warning - ZERION_API_KEY not set.", file=sys.stderr)
    if not os.getenv("THIRDWEB_CLIENT_ID"): print("MCP Server: Warning - THIRDWEB_CLIENT_ID not set.", file=sys.stderr)
    if not os.getenv("THIRDWEB_SECRET_KEY"): print("MCP Server: Warning - THIRDWEB_SECRET_KEY not set (needed for ERC20 balances tool).", file=sys.stderr)

    if get_w3() is None:
         print("MCP Server: Error - Web3 instance failed to initialize.", file=sys.stderr); sys.exit(1)
    main()
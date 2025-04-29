# Monad Custom Agent (MCP Server for Cursor)

**Submission for Monad MCP Madness - Mission 2**

## Overview

This project implements a custom Model Context Protocol (MCP) server designed to work seamlessly with AI-powered IDEs like Cursor and Claude Desktop. It allows users to interact with the Monad Testnet using natural language prompts within their IDE.

The agent leverages various tools and APIs to provide comprehensive information about the Monad ecosystem:

* **Direct Blockchain Interaction:** Uses `web3.py` to query the Monad Testnet RPC for core data like balances, transactions, and blocks.
* **Indexed Data via Zerion:** Utilizes the Zerion API for efficient fetching of ERC20 balances, transaction history analysis (used for contract interaction counts), and user NFT transaction history.
* **Marketplace Data via Magic Eden:** Integrates with the Magic Eden API to provide detailed statistics on NFT collections held by a user, specific NFT activity history, and trending collections on Monad Testnet.
* **Contract Metadata via Thirdweb:** Uses the Thirdweb Insight API to automatically fetch ABIs for verified contracts, simplifying contract interaction.

This project fulfills the mission requirements by using AI tools (Cursor/Claude + the MCP server itself acting as a tool bridge), working within the IDE, interacting with Monad Testnet, producing useful outputs, and demonstrating capability for complex actions via its toolset.

## Features / Implemented Tools

The MCP server exposes the following custom tools accessible via natural language prompts in Cursor/Claude:

* **`get_native_monad_balance_tool`**: Fetches the native MON balance for a Monad address.
* **`get_monad_erc20_balances_tool`**: Lists ERC20 tokens held by an address, including name and symbol (uses Zerion Positions API).
* **`get_monad_transaction_tool`**: Retrieves detailed information for a specific transaction hash (uses Web3.py).
* **`get_monad_block_tool`**: Retrieves detailed information for a specific block number or identifier like "latest" (uses Web3.py).
* **`read_contract_tool`**: Calls any read-only function on a specified contract. Automatically fetches the ABI from Thirdweb Insight if not provided by the user (requires `THIRDWEB_CLIENT_ID`).
* **`get_contract_interactions_tool`**: Analyzes recent transaction history (via Zerion Transactions API) to count unique smart contracts an address has interacted with (sent transactions to). Requires `ZERION_API_KEY`.
* **`get_nft_collection_stats_tool`**: Fetches detailed statistics (floor, top bid, volume, user count, etc.) for all NFT collections held by a wallet on Monad Testnet (uses Magic Eden Collections API). Requires `MAGIC_EDEN_API_KEY`.
* **`get_nft_activity_tool`**: Fetches the detailed activity history (transfers, listings, sales, bids) for a *specific* NFT on Monad Testnet (uses Magic Eden Token Activity API). Requires `MAGIC_EDEN_API_KEY`.
* **`get_trending_collections_tool`**: Fetches a list of currently trending NFT collections on Monad Testnet based on sales or volume over a defined period (uses Magic Eden Trending API). Requires `MAGIC_EDEN_API_KEY`.
* **`get_user_nft_transactions_tool`**: Fetches a general feed of NFT-related transactions (mints, transfers, sales involving NFTs) for a specific user address (uses Zerion Transactions API with NFT filter). Requires `ZERION_API_KEY`.
* **`get_contract_abi_tool`**: Directly fetches and returns the ABI for a verified contract from Thirdweb Insight. Requires `THIRDWEB_CLIENT_ID`.


## Technology Stack

* Python 3.11+
* MCP Server Framework (`mcp` library / `FastMCP`)
* Web3.py (for direct Monad RPC interaction)
* Zerion API (for indexed balances, transactions, interactions)
* Magic Eden API (for NFT stats, activity, trends)
* Thirdweb Insight API (for ABI fetching)
* python-dotenv (for environment variable management)
* httpx (for asynchronous API calls)
* click (for server CLI options)
* Cursor / Claude Desktop (as the MCP client/interface)

## Links

* **Demo Video:** [https://x.com/eccentrichealer/status/1917301085548515488]
* **Setup Instructions:** See [SETUP.md](SETUP.md)


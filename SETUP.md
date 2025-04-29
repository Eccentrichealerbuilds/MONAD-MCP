# Monad Custom Agent - Setup Guide

This guide explains how to set up the environment and configure Cursor IDE to run the Monad Custom Agent MCP server.

## Prerequisites

* Linux environment (tested on Ubuntu on AWS VPS)
* Python 3.11 or newer installed and available as `python3.11`
* `pip` for Python 3.11
* `git` (for cloning)
* Cursor IDE ([https://cursor.sh/](https://www.cursor.com)) or potentially Claude Desktop
* API Keys:
    * Zerion Developer API Key ([https://dev.zerion.io/](https://dev.zerion.io/))
    * Magic Eden Developer API Key ([https://docs.magiceden.io/reference/solana-api-keys](https://docs.magiceden.io/reference/solana-api-keys) - find EVM key process)
    * Thirdweb API Key (specifically need the **Client ID**) ([https://thirdweb.com/dashboard/settings/apikeys](https://thirdweb.com/dashboard/settings/apikeys))
* Monad Testnet RPC URL (e.g., from Alchemy, Infura)

## 1. Clone Repository

```bash
git clone [URL_OF_THIS_GITHUB_REPO]
cd [THIS_REPO_NAME] # e.g., cd MADNESS


# Create a virtual environment using Python 3.11
python3.11 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# OPTIONAL: Add local bin to PATH (if python3.11 or pip commands aren't found directly)
# Check if ~/.local/bin is in PATH. If not, add it to your ~/.bashrc or ~/.profile:
# nano ~/.bashrc
# # Add this line at the end:
# export PATH="$HOME/.local/bin:$PATH"
# # Save and exit, then run:
# source ~/.bashrc



## .env file contents

# Required for Zerion API tools
ZERION_API_KEY="zk_dev_YOUR_ZERION_KEY_HERE"

# Required for Magic Eden API tools
MAGIC_EDEN_API_KEY="YOUR_MAGIC_EDEN_KEY_HERE"

# Required for Thirdweb Insight API tools (ABI Fetching, Tx History)
THIRDWEB_CLIENT_ID="cid_YOUR_THIRDWEB_CLIENT_ID_HERE"

# Required for Web3.py connection to Monad Testnet
MONAD_TESTNET_RPC_URL="https://your_monad_testnet_rpc_url_here"

# Optional: Secret Key might be needed by some underlying thirdweb-ai functions
# THIRDWEB_SECRET_KEY="YOUR_SECRET_KEY_HERE"



###Configure Cursor IDE MCP Settings
 * Open Cursor IDE.
 * Go to Settings (File > Preferences > Settings or Cmd/Ctrl+,).
 * Search for "MCP" or "Model Context Protocol".
 * Find the setting to configure MCP Servers. This might involve editing a JSON file directly (~/.cursor/mcp.json or integrated into settings.json) or using a UI panel.
 * You need to define an stdio server. Add the following JSON object under the "mcpServers" key:
   {
  "mcpServers": {
    "my-monad-agent": {
      "command": "python3.11",
      "args": [
        "/home/ubuntu/MADNESS/mcp_server.py", // *** REPLACE WITH THE ACTUAL FULL ABSOLUTE PATH TO YOUR mcp_server.py ***
        "--chain-id",
        "10143"
      ],
      "env": {} // Leave empty - script loads .env
    }
  }
}

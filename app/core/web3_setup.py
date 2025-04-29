import os
import sys
from web3 import Web3
from typing import Optional
w3_instance: Optional[Web3] = None


def get_w3() ->Optional[Web3]:
    """
    Returns the globally initialized Web3 instance.
    Allows other modules to access the shared connection.
    """
    return w3_instance


def initialize_web3():
    """
    Initializes the Web3 connection using environment variables.
    Sets the global `w3` instance.
    """
    global w3_instance
    rpc_url = os.getenv('MONAD_TESTNET_RPC_URL')
    if not rpc_url:
        print('FATAL: MONAD_TESTNET_RPC_URL environment variable not set.',
            file=sys.stderr)
        w3_instance = None
        return
    try:
        print(f'Initializing Web3 connection to: {rpc_url}', file=sys.stderr)
        temp_w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout':
            90}))
        if not temp_w3.is_connected(show_traceback=True):
            print(
                'FATAL: Could not connect to Monad RPC (is_connected() failed). Check URL.'
                , file=sys.stderr)
            w3_instance = None
            return
        else:
            print(f'Web3 connection successful.', file=sys.stderr)
            w3_instance = temp_w3
            try:
                chain_id = w3_instance.eth.chain_id
                print(f'Monad Testnet Chain ID reported by node: {chain_id}',
                    file=sys.stderr)
            except Exception as chain_id_err:
                print(
                    f'Warning: Could not verify Chain ID via eth_chainId: {chain_id_err}'
                    , file=sys.stderr)
    except Exception as e:
        print(
            f'FATAL: An unexpected error occurred during Web3 initialization: {e}'
            , file=sys.stderr)
        w3_instance = None


initialize_web3()

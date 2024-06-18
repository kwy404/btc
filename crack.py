import subprocess
import sys
import os
import platform
import requests
import logging
import hashlib
from concurrent.futures import ProcessPoolExecutor
from dotenv import load_dotenv
from bip_utils import (
    Bip39MnemonicGenerator,
    Bip39SeedGenerator,
    Bip44,
    Bip44Coins,
    Bip44Changes,
    Bip39WordsNum,
)
import random

# Constants
LOG_FILE_NAME = "enigmacracker.log"
ENV_FILE_NAME = "EnigmaCracker.env"
WALLETS_FILE_NAME = "wallets_with_balance.txt"

# Global counter for the number of wallets scanned
wallets_scanned = 0

# Get the absolute path of the directory where the script is located
directory = os.path.dirname(os.path.abspath(__file__))
# Initialize directory paths
log_file_path = os.path.join(directory, LOG_FILE_NAME)
env_file_path = os.path.join(directory, ENV_FILE_NAME)
wallets_file_path = os.path.join(directory, WALLETS_FILE_NAME)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file_path),  # Log to a file
        logging.StreamHandler(sys.stdout),  # Log to standard output
    ],
)

# Load environment variables from .env file
load_dotenv(env_file_path)

# Environment variable validation
required_env_vars = ["ETHERSCAN_API_KEY"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Missing environment variables: {', '.join(missing_vars)}")

# Check if we've set the environment variable indicating we're in the correct CMD
if os.environ.get("RUNNING_IN_NEW_CMD") != "TRUE":
    # Set the environment variable for the new CMD session
    os.environ["RUNNING_IN_NEW_CMD"] = "TRUE"

    # Determine the operating system
    os_type = platform.system()

    # For Windows
    if os_type == "Windows":
        subprocess.run(f'start cmd.exe /K python "{__file__}"', shell=True)

    # For Linux
    elif os_type == "Linux":
        subprocess.run(f"gnome-terminal -- python3 {__file__}", shell=True)

    # Exit this run, as we've opened a new CMD
    sys.exit()


def update_cmd_title():
    # Update the CMD title with the current number of wallets scanned
    if platform.system() == "Windows":
        os.system(f"title EnigmaCracker.py - Wallets Scanned: {wallets_scanned}")


def generate_similar_mnemonic():
    # Exemplos de sementes BIP39 válidas que poderiam estar associadas a carteiras com alto saldo (apenas para fins educacionais)
    seed_examples = [
        "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about",
        "legal winner thank year wave sausage worth useful legal winner thank yellow",
        "ozone drill grab fiber curtain grace pudding thank cruise elder eight picnic",
        "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about",
        "scheme spot photo card baby mountain device kick cradle pact join borrow",
    ]
    
    # Escolher um exemplo de semente aleatoriamente
    return random.choice(seed_examples)

def bip44_BTC_seed_to_address(seed):
    # Generate the seed from the mnemonic
    seed_bytes = Bip39SeedGenerator(seed).Generate()

    # Generate the Bip44 object for Bitcoin derivation
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)

    # Generate the Bip44 address (account 0, change 0, address 0)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0)
    bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
    bip44_addr_ctx = bip44_chg_ctx.AddressIndex(0)

    # Return the address
    return bip44_addr_ctx.PublicKey().ToAddress()


def check_BTC_balance(address):
    try:
        response = requests.get(f"https://blockchain.info/balance?active={address}")
        response.raise_for_status()  # Raise error for non-2xx responses
        data = response.json()
        if address in data:
            balance = data[address]["final_balance"]
            return balance / 100000000  # Convert satoshi to bitcoin
        else:
            logging.error("Error: Address not found in blockchain.info response")
            return 0
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking BTC balance: {str(e)}")
        return 0


def write_to_file(seed, BTC_address, BTC_balance):
    # Write the seed, BTC address, and balance to a file in the script's directory
    with open(wallets_file_path, "a") as f:
        log_message = (
            f"Seed: {seed}\n"
            f"BTC Address: {BTC_address}\n"
            f"BTC Balance: {BTC_balance} BTC\n\n"
        )
        f.write(log_message)
        logging.info(f"Written to file: {log_message}")


def main():
    global wallets_scanned
    try:
        with ProcessPoolExecutor() as executor:
            while wallets_scanned < 1000:
                seed = generate_similar_mnemonic()

                # BTC
                BTC_address = bip44_BTC_seed_to_address(seed)
                future_btc = executor.submit(check_BTC_balance, BTC_address)

                # Wait for result
                BTC_balance = future_btc.result()

                logging.info(f"Seed: {seed}")
                logging.info(f"BTC address: {BTC_address}")
                logging.info(f"BTC balance: {BTC_balance} BTC")

                wallets_scanned += 1
                update_cmd_title()

                # Check if balance is greater than zero
                if BTC_balance > 0:
                    logging.info("(!) Wallet with balance found!")
                    write_to_file(seed, BTC_address, BTC_balance)
                else:
                    logging.info("No balance found for this wallet.")

    except KeyboardInterrupt:
        logging.info("Program interrupted by user. Exiting...")

if __name__ == "__main__":
    main()

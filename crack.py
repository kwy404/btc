import subprocess
import sys
import os
import platform
import requests
import logging
import time
from dotenv import load_dotenv
from bip_utils import (
    Bip39MnemonicGenerator,
    Bip39SeedGenerator,
    Bip44,
    Bip44Coins,
    Bip44Changes,
    Bip39WordsNum,
)
from concurrent.futures import ProcessPoolExecutor, as_completed

# Constants
LOG_FILE_NAME = "enigmacracker.log"
ENV_FILE_NAME = "EnigmaCracker.env"
WALLETS_FILE_NAME = "wallets_with_balance.txt"
NUM_WALLETS_TO_TEST = 50000  # Number of wallets to test per second

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


def generate_seed_and_private_key():
    # Generate a 12-word BIP39 mnemonic
    mnemonic = Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)

    # Generate the seed from the mnemonic
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()

    # Derive the private key for Bitcoin
    btc_priv_key = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN).PrivateKey().Raw().ToHex()

    return mnemonic, btc_priv_key


def bip44_BTC_seed_to_address(seed):
    # Generate the seed from the mnemonic
    seed_bytes = Bip39SeedGenerator(seed).Generate()

    # Generate the Bip44 object
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)

    # Generate the Bip44 address (account 0, change 0, address 0)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0)
    bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
    bip44_addr_ctx = bip44_chg_ctx.AddressIndex(0)

    # Return the address
    return bip44_addr_ctx.PublicKey().ToAddress()


def check_BTC_balance(address, retries=3, delay=5):
    # Check the balance of the address
    for attempt in range(retries):
        try:
            response = requests.get(f"https://blockchain.info/balance?active={address}")
            data = response.json()
            balance = data[address]["final_balance"]
            return balance / 100000000  # Convert satoshi to bitcoin
        except Exception as e:
            if attempt < retries - 1:
                logging.error(
                    f"Error checking balance, retrying in {delay} seconds: {str(e)}"
                )
                time.sleep(delay)
            else:
                logging.error("Error checking balance: %s", str(e))
                return 0


def write_to_file(seed, BTC_address, BTC_balance):
    # Define o valor mínimo desejado para o saldo em BTC
    min_balance = 0.1  # ou qualquer outro valor desejado, por exemplo, 0.00001

    if BTC_balance >= min_balance:
        # Write the seed, address, and balance to a file in the script's directory
        with open(wallets_file_path, "a") as f:
            log_message = f"Seed: {seed}\nAddress: {BTC_address}\nBalance: {BTC_balance} BTC\n\n"
            f.write(log_message)
            logging.info(f"Written to file: {log_message}")

def process_wallet(seed):
    try:
        BTC_address = bip44_BTC_seed_to_address(seed)
        BTC_balance = check_BTC_balance(BTC_address)
         # Define o valor mínimo desejado para o saldo em BTC
        min_balance = 0.1  # ou qualquer outro valor desejado, por exemplo, 0.00001
        logging.info("(!) Wallet with balance found!")
        logging.info(f"Seed: {seed}")
        logging.info(f"BTC address: {BTC_address}")
        logging.info(f"BTC balance: {BTC_balance} BTC")
        logging.info("")
        if BTC_balance > min_balance:
            write_to_file(seed, BTC_address, BTC_balance)

    except Exception as e:
        logging.error(f"Error processing wallet: {str(e)}")


def main():
    global wallets_scanned
    try:
        with ProcessPoolExecutor() as executor:
            futures = []

            # Start testing wallets
            while wallets_scanned < NUM_WALLETS_TO_TEST:
                seed, _ = generate_seed_and_private_key()
                futures.append(executor.submit(process_wallet, seed))
                wallets_scanned += 1
                update_cmd_title()

            # Wait for all tasks to complete
            for future in as_completed(futures):
                future.result()

    except KeyboardInterrupt:
        logging.info("Program interrupted by user. Exiting...")


if __name__ == "__main__":
    main()

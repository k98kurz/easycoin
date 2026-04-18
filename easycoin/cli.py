from sys import argv
import asyncio
import logging
from easycoin import models, node
from easycoin.config import get_config_manager
from easycoin.version import version
import os


def print_help():
    print("Usage: easycoin --setup_wallet")
    print("Usage: easycoin --query [coin|txn|utxo] [--id hex_id]")
    print("Usage: easycoin --daemon [--debug]")
    print("\tRuns the node in headless mode. Use --debug for verbose logging.")
    print("Usage: easycoin --interactive")
    print("\tRuns the node with Textual console UI (requires optional cui dependency)")
    print("Usage: easycoin --mine [--goal int_goal] [--wallet wallet_id]")
    print("\tMines until the goal EC⁻¹ are ready to spend. Default behavior is")
    print("\tto mine up to a balance of 100k EC⁻¹ in 10k coins for the first wallet")
    print("\tthat has a readable pubkey. Will error if there is no wallet available.")
    print("Usage: easycoin --help")
    print("Usage: easycoin --version")
    print("Aliases: -sw for --setup_wallet -q for --query; -d for --daemon;")
    print("-i for --interactive; -m for --mine; -h for --help")


def setup_wallet():
    print("Not yet implemented")


def query():
    print("Not yet implemented")


def daemon(debug = False):
    """Run node in headless daemon mode."""
    config = get_config_manager()
    config.load()
    db_path = config.get_db_path()
    migrations_path = config.path('migrations')
    os.makedirs(migrations_path, exist_ok=True)
    models.set_connection_info(db_path)
    models.publish_migrations(migrations_path)
    models.automigrate(migrations_path, db_path)

    logger = logging.getLogger("easycoin")
    if debug:
        logger.setLevel(logging.DEBUG)
    logger.info("Starting EasyCoin node in daemon mode")

    try:
        asyncio.run(node.run_node())
    except KeyboardInterrupt:
        logger.info("Shutting down daemon...")
        node.stop()
    except Exception as e:
        logger.error(f"Daemon error: {e}")
        raise


def interactive(debug = False):
    config = get_config_manager()
    config.load()
    db_path = config.get_db_path()
    migrations_path = config.path('migrations')
    os.makedirs(migrations_path, exist_ok=True)
    models.set_connection_info(db_path)
    models.publish_migrations(migrations_path)
    models.automigrate(migrations_path, db_path)

    try:
        from .cui import EasyCoinApp
    except ImportError as e:
        if debug:
            print(e)
        else:
            print("Error: the optional cui dependency is missing.")
            print("Install it with `pip install easycoin[cui]`.")
        exit(4)

    app = EasyCoinApp()
    app.run()


def mine():
    print("Not yet implemented")


def print_version():
    print(version())


def run():
    if '--setup_wallet' in argv or '-sw' in argv:
        setup_wallet()
        exit()

    if '--query' in argv or '-q' in argv:
        query()
        exit()

    if '--daemon' in argv or '-d' in argv:
        daemon('--debug' in argv)
        exit()

    if '--mine' in argv or '-m' in argv:
        mine()
        exit()

    if '--interactive' in argv or '-i' in argv:
        interactive('--debug' in argv)
        exit()

    if '--help' in argv or '-h' in argv:
        print_help()
        exit()

    if '--version' in argv:
        print_version()
        exit()

    if len(argv) > 1:
        print(f"Unrecognized argument: {argv[1]}")

    print("Select a mode (use --help or -h for help text).")


if __name__ == "__main__":
    run()


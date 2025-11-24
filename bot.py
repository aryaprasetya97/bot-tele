import logging
import requests
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ============ CONFIG ============

TOKEN = "8304468422:AAFNBF1pLP4j6CW2lqjpoSLLYjBzg5AMCCg"
RECEIVER_WALLET = "2cdmxtKgoEBS8bRbaWV3BKwzLCo861LbvQTwEgsuVZiJ"  # Your wallet to receive payments

# Public Solana RPC (you can replace with your own provider if needed)
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"

logging.basicConfig(level=logging.INFO)

# In-memory mapping: telegram_user_id -> solana_wallet_address
# For production, replace with a real database.
USER_WALLETS: dict[int, str] = {}


# ============ HELPERS ============

def get_sol_balance(address: str) -> Optional[float]:
    """
    Get SOL balance for an address using Solana RPC.
    Returns balance in SOL (not lamports).
    """
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [address],
        }
        resp = requests.post(SOLANA_RPC_URL, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        lamports = data["result"]["value"]
        sol = lamports / 1_000_000_000  # 1 SOL = 1e9 lamports
        return sol
    except Exception as e:
        logging.exception("Failed to fetch balance: %s", e)
        return None


# ============ COMMAND HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start command – show 2-step flow:
    Step 1: Connect wallet
    Step 2: Start the Magic
    """
    keyboard = [
        [InlineKeyboardButton("Connect Your Wallet", callback_data="connect")],
        [InlineKeyboardButton("Start the Magic", callback_data="magic")],
    ]

    text = (
        "✨ *Welcome to the Solana Magic Bot!* ✨\n\n"
        "Please follow these steps to get started:\n\n"
        "🔹 *Step 1:* Connect your wallet\n"
        "🔹 *Step 2:* Click *Start the Magic*\n\n"
        "Choose an option below to continue:"
    )

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def connectwallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /connectwallet YOUR_SOLANA_ADDRESS
    Save user's wallet and show current balance.
    """
    if len(context.args) != 1:
        await update.message.reply_text(
            "Usage:\n"
            "`/connectwallet YOUR_SOLANA_ADDRESS`\n\n"
            "Example:\n"
            "`/connectwallet 9xYourSolanaAddressHere...`",
            parse_mode="Markdown",
        )
        return

    address = context.args[0].strip()
    user_id = update.effective_user.id

    # Very simple validation – just length; you may improve this.
    if len(address) < 32 or len(address) > 60:
        await update.message.reply_text(
            "This doesn't look like a valid Solana address. "
            "Please double-check and try again."
        )
        return

    USER_WALLETS[user_id] = address

    balance = get_sol_balance(address)
    if balance is None:
        await update.message.reply_text(
            f"Your wallet has been saved:\n`{address}`\n\n"
            "However, I couldn't read the balance right now. Please try again later.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"Your wallet has been saved:\n`{address}`\n\n"
            f"Estimated balance: *{balance:.6f} SOL*",
            parse_mode="Markdown",
        )


# ============ CALLBACK HANDLER ============

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # STEP 1: Connect your wallet (show instructions)
    if data == "connect":
        text = (
            "To connect your wallet, please send the following command:\n\n"
            "`/connectwallet YOUR_SOLANA_ADDRESS`\n\n"
            "Example:\n"
            "`/connectwallet 9xYourSolanaAddressHere...`\n\n"
            "_Never share your seed phrase or private key. "
            "I only need your public address._"
        )
        await query.edit_message_text(text, parse_mode="Markdown")

    # STEP 2: Start the Magic
    elif data == "magic":
        address = USER_WALLETS.get(user_id)

        if not address:
            # User has not connected wallet yet
            text = (
                "✨ The magic is almost ready, but I don't see your wallet yet.\n\n"
                "Please connect your wallet first:\n"
                "`/connectwallet YOUR_SOLANA_ADDRESS`"
            )
            await query.edit_message_text(text, parse_mode="Markdown")
            return

        # If wallet is connected, show next options
        keyboard = [
            [InlineKeyboardButton("Pay with Phantom", callback_data="pay")],
            [InlineKeyboardButton("Check Wallet Balance", callback_data="check_balance")],
        ]
        text = (
            "✨ Magic mode activated!\n\n"
            f"Your connected wallet:\n`{address}`\n\n"
            "What would you like to do next?"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    # Pay with Phantom – open Phantom payment link to RECEIVER_WALLET
    elif data == "pay":
        # Example deep-link – you should verify the latest format from Phantom docs.
        phantom_link = (
            f"https://phantom.app/ul/send?"
            f"recipient={RECEIVER_WALLET}&amount=0.1&token=SOL"
        )

        keyboard = [
            [InlineKeyboardButton("Open Phantom", url=phantom_link)],
        ]
        text = (
            "Please click the button below to open Phantom and complete the payment.\n\n"
            f"Receiver wallet:\n`{RECEIVER_WALLET}`\n\n"
            "_Always verify the address inside Phantom before approving the transaction._"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    # Check balance of user's connected wallet
    elif data == "check_balance":
        address = USER_WALLETS.get(user_id)
        if not address:
            await query.edit_message_text(
                "You don't have a connected wallet yet.\n\n"
                "Please connect your wallet with:\n"
                "`/connectwallet YOUR_SOLANA_ADDRESS`",
                parse_mode="Markdown",
            )
            return

        balance = get_sol_balance(address)
        if balance is None:
            await query.edit_message_text(
                f"I couldn't read the balance for:\n`{address}`\n\n"
                "Please try again later.",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(
                f"Your connected wallet:\n`{address}`\n\n"
                f"Current SOL balance: *{balance:.6f} SOL*",
                parse_mode="Markdown",
            )


# ============ MAIN ============

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("connectwallet", connectwallet_cmd))
    app.add_handler(CallbackQueryHandler(button))

    app.run_polling()

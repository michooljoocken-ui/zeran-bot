import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime
from flask import Flask
from threading import Thread

# ==================== CONFIGURATION ====================
TOKEN = os.environ.get('DISCORD_TOKEN', 'PUT_YOUR_TOKEN_HERE')
DATA_FILE = 'balances.json'
CURRENCY_NAME = "Zeran"
CURRENCY_SYMBOL = "~~Z~~"
CURRENCY_EMOJI = "<:Banknote:1533566642750226463>"

# ==================== KEEP ALIVE SERVER ====================
app = Flask('')

@app.route('/')
def home():
    return "Zeran Banking Bot is alive!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ==================== DATA MANAGEMENT ====================
def load_balances():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            for uid, val in data.items():
                if isinstance(val, int):
                    data[uid] = {"balance": val, "transactions": []}
                elif "transactions" not in val:
                    data[uid]["transactions"] = []
            return data
        except:
            return {}
    return {}

def save_balances(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

balances = load_balances()

def get_user_data(user_id):
    uid = str(user_id)
    if uid not in balances:
        balances[uid] = {"balance": 0, "transactions": []}
        save_balances(balances)
    return balances[uid]

def set_balance(user_id, amount):
    uid = str(user_id)
    if uid not in balances:
        balances[uid] = {"balance": 0, "transactions": []}
    balances[uid]["balance"] = amount
    save_balances(balances)

def add_transaction(user_id, text):
    uid = str(user_id)
    if uid not in balances:
        balances[uid] = {"balance": 0, "transactions": []}
    balances[uid]["transactions"].insert(0, f"{datetime.now().strftime('%m/%d %H:%M')} - {text}")
    balances[uid]["transactions"] = balances[uid]["transactions"][:5]
    save_balances(balances)

# ==================== BOT SETUP ====================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ==================== HELPER FUNCTIONS ====================
def fmt(amount):
    return f"{CURRENCY_EMOJI} **{amount:,}** {CURRENCY_SYMBOL}"

# ==================== BOT EVENTS ====================
@bot.event
async def on_ready():
    print(f'✅ Bot logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'🔄 Synced {len(synced)} slash commands')
    except Exception as e:
        print(f'❌ Failed to sync commands: {e}')

# ==================== COMMANDS ====================

# -------- /give --------
@bot.tree.command(name="give", description="Give Zeran to another user")
@app_commands.describe(user="The person you want to send Zeran to", amount="How much Zeran to send")
async def give(interaction: discord.Interaction, user: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message(embed=discord.Embed(description="❌ Amount must be greater than 0!", color=discord.Color.red()), ephemeral=True)
        return
    if user.id == interaction.user.id:
        await interaction.response.send_message(embed=discord.Embed(description="❌ You can't send Zeran to yourself!", color=discord.Color.red()), ephemeral=True)
        return
    if user.bot:
        await interaction.response.send_message(embed=discord.Embed(description="❌ You can't send Zeran to a bot!", color=discord.Color.red()), ephemeral=True)
        return

    sender_data = get_user_data(interaction.user.id)
    if sender_data["balance"] < amount:
        await interaction.response.send_message(embed=discord.Embed(description=f"❌ Insufficient funds! You have {fmt(sender_data['balance'])} but tried to send {fmt(amount)}.", color=discord.Color.red()), ephemeral=True)
        return

    # Perform Transfer
    set_balance(interaction.user.id, sender_data["balance"] - amount)
    recipient_data = get_user_data(user.id)
    set_balance(user.id, recipient_data["balance"] + amount)

    # Log Transactions
    add_transaction(interaction.user.id, f"Sent {amount} to {user.display_name}")
    add_transaction(user.id, f"Received {amount} from {interaction.user.display_name}")

    embed = discord.Embed(description=f"💸 **{interaction.user.display_name}** sent {fmt(amount)} to **{user.display_name}**", color=discord.Color.green())
    embed.add_field(name="Your Balance", value=fmt(get_user_data(interaction.user.id)['balance']), inline=True)
    embed.add_field(name="Their Balance", value=fmt(get_user_data(user.id)['balance']), inline=True)
    embed.set_footer(text="Zeran Banking System")
    await interaction.response.send_message(embed=embed)

# -------- /balance --------
@bot.tree.command(name="balance", description="Check your Zeran balance or someone else's")
@app_commands.describe(user="Whose balance to check (leave empty for your own)")
async def balance(interaction: discord.Interaction, user: discord.Member = None):
    if user is None: user = interaction.user
    bal = get_user_data(user.id)["balance"]
    
    if bal >= 0:
        color, status = discord.Color.gold(), "✅ Good Standing"
    else:
        color, status = discord.Color.red(), "⚠️ In Debt"

    embed = discord.Embed(description=f"🏦 **{user.display_name}**\nBalance: {fmt(bal)}\nStatus: {status}", color=color)
    embed.set_footer(text="Zeran Banking System")
    await interaction.response.send_message(embed=embed)

# -------- /add (Admin) --------
@bot.tree.command(name="add", description="[ADMIN] Pay a user for their contributions/salary")
@app_commands.describe(user="The user to pay", amount="How much Zeran to add", reason="Why you are paying them")
async def add(interaction: discord.Interaction, user: discord.Member, amount: int, reason: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(embed=discord.Embed(description="🔒 You need **Administrator** permissions!", color=discord.Color.red()), ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message(embed=discord.Embed(description="❌ Amount must be greater than 0!", color=discord.Color.red()), ephemeral=True)
        return

    new_balance = get_user_data(user.id)["balance"] + amount
    set_balance(user.id, new_balance)
    add_transaction(user.id, f"Admin {interaction.user.display_name} added {amount} ({reason})")

    embed = discord.Embed(title="💼 Payment Processed", color=discord.Color.green())
    embed.add_field(name="User", value=user.mention, inline=True)
    embed.add_field(name="Amount", value=fmt(amount), inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="New Balance", value=fmt(new_balance), inline=False)
    embed.set_footer(text=f"Approved by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

# -------- /remove (Admin) --------
@bot.tree.command(name="remove", description="[ADMIN] Remove Zeran from a user's account")
@app_commands.describe(user="The user to remove Zeran from", amount="How much Zeran to remove", reason="Why you are removing it")
async def remove(interaction: discord.Interaction, user: discord.Member, amount: int, reason: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(embed=discord.Embed(description="🔒 You need **Administrator** permissions!", color=discord.Color.red()), ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message(embed=discord.Embed(description="❌ Amount must be greater than 0!", color=discord.Color.red()), ephemeral=True)
        return

    old_balance = get_user_data(user.id)["balance"]
    new_balance = old_balance - amount
    set_balance(user.id, new_balance)
    add_transaction(user.id, f"Admin {interaction.user.display_name} removed {amount} ({reason})")

    embed = discord.Embed(title="➖ Zeran Removed", color=discord.Color.orange())
    embed.add_field(name="User", value=user.mention, inline=True)
    embed.add_field(name="Amount", value=fmt(amount), inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="New Balance", value=fmt(new_balance), inline=False)
    
    if new_balance < 0:
        embed.color = discord.Color.red()
        embed.description = "⚠️ **WARNING: This user is now in DEBT!**"
        
    embed.set_footer(text=f"Approved by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

# -------- /leaderboard --------
@bot.tree.command(name="leaderboard", description="See the top 10 wealthiest users")
async def leaderboard(interaction: discord.Interaction):
    sorted_users = sorted(balances.items(), key=lambda x: x[1].get("balance", 0), reverse=True)
    
    desc = ""
    rank = 1
    for uid, data in sorted_users:
        if rank > 10: break
        try:
            member = await bot.fetch_user(int(uid))
            name = member.display_name
        except:
            name = f"Unknown User"
        
        bal = data.get("balance", 0)
        desc += f"**{rank}.** {name} — {fmt(bal)}\n"
        rank += 1

    if not desc:
        desc = "No data available yet."

    embed = discord.Embed(title="🏆 Zeran Leaderboard", description=desc, color=discord.Color.gold())
    embed.set_footer(text="Zeran Banking System")
    await interaction.response.send_message(embed=embed)

# -------- /transactions --------
@bot.tree.command(name="transactions", description="View your recent transaction history")
@app_commands.describe(user="View someone else's transactions (Admin only)")
async def transactions(interaction: discord.Interaction, user: discord.Member = None):
    if user is not None and user.id != interaction.user.id:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(embed=discord.Embed(description="🔒 You can only view your own transactions unless you are an Admin.", color=discord.Color.red()), ephemeral=True)
            return
    else:
        user = interaction.user

    user_data = get_user_data(user.id)
    history = user_data.get("transactions", [])

    if not history:
        desc = "No transactions found yet."
    else:
        desc = "\n".join([f"• {t}" for t in history])

    embed = discord.Embed(title="📜 Transaction History", description=f"**{user.display_name}**\n{desc}", color=discord.Color.blue())
    embed.set_footer(text="Zeran Banking System")
    await interaction.response.send_message(embed=embed)

# -------- /zeranhelp --------
@bot.tree.command(name="zeranhelp", description="View all Zeran banking commands")
async def zeranhelp(interaction: discord.Interaction):
    embed = discord.Embed(title="🏦 Zeran Banking System", description=f"The official **{CURRENCY_NAME}** {CURRENCY_EMOJI} banking system commands:", color=discord.Color.blue())
    
    embed.add_field(name="💸 /give `<user> <amount>`", value="Send Zeran to another user.", inline=False)
    embed.add_field(name="🏦 /balance `[user]`", value="Check a balance.", inline=False)
    embed.add_field(name="📜 /transactions `[user]`", value="View last 5 transactions.", inline=False)
    embed.add_field(name="🏆 /leaderboard", value="See the top 10 users.", inline=False)
    embed.add_field(name="➕ /add `<user> <amount> <reason>` 🔒", value="[Admin] Pay a user.", inline=False)
    embed.add_field(name="➖ /remove `<user> <amount> <reason>` 🔒", value="[Admin] Remove Zeran.", inline=False)

    embed.set_footer(text="Zeran Banking System")
    await interaction.response.send_message(embed=embed)

# ==================== RUN ====================
if __name__ == "__main__":
    if 'PUT_YOUR_TOKEN_HERE' in TOKEN or not TOKEN:
        print("❌ NO BOT TOKEN FOUND! Add DISCORD_TOKEN to Render Environment Variables.")
    else:
        keep_alive()
        bot.run(TOKEN)

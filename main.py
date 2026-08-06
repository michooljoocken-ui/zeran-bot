import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import random
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# ==================== CONFIGURATION ====================
TOKEN = os.environ.get('DISCORD_TOKEN', 'PUT_YOUR_TOKEN_HERE')
DATA_FILE = 'balances.json'
ALLOWED_GUILDS_FILE = 'allowed_guilds.json'
CURRENCY_NAME = "Zeran"
CURRENCY_SYMBOL = "~~Z~~"
CURRENCY_EMOJI = "<:Banknote:1533566642750226463>"
CREATOR_ID = 1376575230784311447

# ==================== KEEP ALIVE SERVER ====================
app = Flask('')

@app.route('/')
def home():
    return "Zeran Banking Bot is alive!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run).start()

# ==================== DATA MANAGEMENT ====================
DEFAULT_USER = {
    "balance": 0,
    "transactions": [],
    "streak": 0,
    "last_daily": None,
    "total_earned": 0,
    "total_lost": 0,
    "wins": 0,
    "losses": 0
}

def load_balances():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            for uid, val in data.items():
                if isinstance(val, int):
                    data[uid] = {**DEFAULT_USER, "balance": val}
                else:
                    merged = {**DEFAULT_USER, **val}
                    if "transactions" not in val:
                        merged["transactions"] = []
                    data[uid] = merged
            return data
        except Exception:
            return {}
    return {}

def save_balances(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

balances = load_balances()

# ==================== ALLOWED GUILDS MANAGEMENT ====================
def load_allowed_guilds():
    if os.path.exists(ALLOWED_GUILDS_FILE):
        try:
            with open(ALLOWED_GUILDS_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_allowed_guilds(data):
    with open(ALLOWED_GUILDS_FILE, 'w') as f:
        json.dump(list(data), f)

allowed_guilds = load_allowed_guilds()

def get_user_data(user_id):
    uid = str(user_id)
    if uid not in balances:
        balances[uid] = {**DEFAULT_USER}
        save_balances(balances)
    return balances[uid]

def set_balance(user_id, amount):
    uid = str(user_id)
    if uid not in balances:
        balances[uid] = {**DEFAULT_USER}
    balances[uid]["balance"] = amount
    save_balances(balances)

def add_transaction(user_id, text):
    uid = str(user_id)
    if uid not in balances:
        balances[uid] = {**DEFAULT_USER}
    balances[uid]["transactions"].insert(0, f"{datetime.now().strftime('%m/%d %H:%M')} — {text}")
    balances[uid]["transactions"] = balances[uid]["transactions"][:5]
    save_balances(balances)

# ==================== WEALTH TIERS ====================
TIERS = [
    (0,         "🪨 Beggar",     discord.Color.dark_gray()),
    (100,       "🌾 Peasant",    discord.Color.green()),
    (1_000,     "🗡️ Commoner",  discord.Color.teal()),
    (10_000,    "⚖️ Merchant",  discord.Color.blue()),
    (50_000,    "🎩 Noble",      discord.Color.purple()),
    (200_000,   "👑 Baron",      discord.Color.magenta()),
    (1_000_000, "💎 Duke",       discord.Color.gold()),
    (10_000_000,"🐉 Legend",     discord.Color.red()),
    (100_000_000,"🌌 Ascended",  discord.Color.from_rgb(255, 215, 0)),
]

def get_tier(balance):
    current = TIERS[0]
    nxt = None
    for i, t in enumerate(TIERS):
        if balance >= t[0]:
            current = t
            nxt = TIERS[i+1] if i+1 < len(TIERS) else None
    return current, nxt

def progress_bar(current, target, length=10):
    if target <= 0:
        return "▰" * length
    filled = min(int((current / target) * length), length)
    return "▰" * filled + "▱" * (length - filled)

# ==================== BOT SETUP ====================
intents = discord.Intents.default()
intents.members = True  # Required for fetching user data in leaderboards
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ==================== HELPER FUNCTIONS ====================
def fmt(amount):
    return f"{CURRENCY_EMOJI} **{amount:,}** {CURRENCY_SYMBOL}"

TRANSFER_PHRASES = [
    "wired the cash",
    "slipped some bills",
    "passed the dough",
    "transferred the loot",
    "deposited the goods",
    "handed over the stash",
]

# ==================== BOT EVENTS ====================
@bot.event
async def on_ready():
    print(f'✅ Bot logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'🔄 Synced {len(synced)} slash commands')
    except Exception as e:
        print(f'❌ Failed to sync commands: {e}')

@bot.event
async def on_guild_join(guild: discord.Guild):
    """Check if the creator invited the bot to the new guild."""
    if guild.id in allowed_guilds:
        return
        
    try:
        if guild.me.guild_permissions.view_audit_log:
            async for entry in guild.audit_logs(limit=20, action=discord.AuditLogAction.bot_add):
                if entry.target and entry.target.id == bot.user.id:
                    if entry.user.id == CREATOR_ID:
                        allowed_guilds.add(guild.id)
                        save_allowed_guilds(allowed_guilds)
                        print(f"✅ Auto-allowed guild {guild.name} (Creator invited)")
                    break
    except Exception as e:
        print(f"Could not check audit logs for {guild.name}: {e}")

# ==================== GLOBAL ACCESS CONTROL ====================
@bot.tree.check
async def global_access_check(interaction: discord.Interaction) -> bool:
    # 1. Creator can use it anywhere
    if interaction.user.id == CREATOR_ID:
        return True
        
    # 2. DMs are blocked for non-creators
    if interaction.guild is None:
        return False
        
    # 3. Check if guild is already whitelisted
    if interaction.guild_id in allowed_guilds:
        return True
        
    # 4. Attempt to dynamically check audit logs if we couldn't on join
    if interaction.guild.me.guild_permissions.view_audit_log:
        try:
            async for entry in interaction.guild.audit_logs(limit=20, action=discord.AuditLogAction.bot_add):
                if entry.target and entry.target.id == bot.user.id:
                    if entry.user.id == CREATOR_ID:
                        allowed_guilds.add(interaction.guild_id)
                        save_allowed_guilds(allowed_guilds)
                        return True
                    break # Found who added the bot, but it wasn't creator
        except:
            pass

    # 5. Block if conditions aren't met
    locked_embed = discord.Embed(
        title="🔒 Bot Locked",
        description="This bot is globally restricted.\nIt can only be used if the owner (`1376575230784311447`) invited it to this server.\n\n*If the owner recently invited the bot, they can use `/allowserver` to unlock it.*",
        color=discord.Color.dark_red()
    )
    await interaction.response.send_message(embed=locked_embed, ephemeral=True)
    return False

# ==================== COMMANDS ====================

# -------- /allowserver (Creator Only) --------
@bot.tree.command(name="allowserver", description="[OWNER ONLY] Manually allow this server to use the bot")
async def allowserver(interaction: discord.Interaction):
    # Bypasses the global check automatically because user is CREATOR_ID
    if interaction.guild_id in allowed_guilds:
        await interaction.response.send_message("✅ This server is already allowed.", ephemeral=True)
        return
        
    allowed_guilds.add(interaction.guild_id)
    save_allowed_guilds(allowed_guilds)
    
    embed = discord.Embed(
        title="✅ Server Unlocked",
        description=f"**{interaction.guild.name}** has been added to the allowed list.\nMembers can now use Zeran commands.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# -------- /give --------
@bot.tree.command(name="give", description="Send Zeran to another user")
@app_commands.describe(user="Recipient", amount="How much Zeran to send")
async def give(interaction: discord.Interaction, user: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message(embed=discord.Embed(description="❌ Amount must be greater than 0!", color=discord.Color.red()), ephemeral=True); return
    if user.id == interaction.user.id:
        await interaction.response.send_message(embed=discord.Embed(description="❌ You can't send Zeran to yourself!", color=discord.Color.red()), ephemeral=True); return
    if user.bot:
        await interaction.response.send_message(embed=discord.Embed(description="❌ Bots don't have bank accounts!", color=discord.Color.red()), ephemeral=True); return

    sender_data = get_user_data(interaction.user.id)
    if sender_data["balance"] < amount:
        await interaction.response.send_message(embed=discord.Embed(description=f"❌ Insufficient funds! You have {fmt(sender_data['balance'])} but tried to send {fmt(amount)}.", color=discord.Color.red()), ephemeral=True); return

    set_balance(interaction.user.id, sender_data["balance"] - amount)
    recipient_data = get_user_data(user.id)
    set_balance(user.id, recipient_data["balance"] + amount)
    balances[str(user.id)]["total_earned"] += amount
    balances[str(interaction.user.id)]["total_lost"] += amount
    save_balances(balances)

    add_transaction(interaction.user.id, f"📤 Sent {amount:,} to {user.display_name}")
    add_transaction(user.id, f"📥 Received {amount:,} from {interaction.user.display_name}")

    embed = discord.Embed(
        description=f"💸 **{interaction.user.display_name}** {random.choice(TRANSFER_PHRASES)} to **{user.display_name}**",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="💼 Your Balance", value=fmt(get_user_data(interaction.user.id)['balance']), inline=True)
    embed.add_field(name="💼 Their Balance", value=fmt(get_user_data(user.id)['balance']), inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text="Zeran Banking System", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# -------- /balance --------
@bot.tree.command(name="balance", description="Check Zeran balance + tier")
@app_commands.describe(user="Whose balance (defaults to you)")
async def balance(interaction: discord.Interaction, user: discord.Member = None):
    if user is None: user = interaction.user
    bal = get_user_data(user.id)["balance"]
    tier, nxt = get_tier(bal)
    status = "✅ Good Standing" if bal >= 0 else "⚠️ In Debt"

    embed = discord.Embed(title="🏦 Zeran Account", color=tier[2], timestamp=datetime.now())
    embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    embed.add_field(name="💰 Balance", value=fmt(bal), inline=True)
    embed.add_field(name="🏆 Tier", value=tier[1], inline=True)
    embed.add_field(name="📊 Status", value=status, inline=True)
    if nxt:
        prog = progress_bar(bal - tier[0], nxt[0] - tier[0])
        pct = (bal - tier[0]) / (nxt[0] - tier[0]) * 100
        embed.add_field(name=f"➡️ Next: {nxt[1]}", value=f"`{prog}` {pct:.1f}%", inline=False)
    embed.set_footer(text="Zeran Banking System")
    await interaction.response.send_message(embed=embed)

# -------- /profile --------
@bot.tree.command(name="profile", description="View full economic profile")
@app_commands.describe(user="Whose profile to view")
async def profile(interaction: discord.Interaction, user: discord.Member = None):
    if user is None: user = interaction.user
    ud = get_user_data(user.id)
    bal = ud["balance"]
    tier, _ = get_tier(bal)
    total_bets = ud.get("wins", 0) + ud.get("losses", 0)
    wr = (ud.get("wins", 0) / total_bets * 100) if total_bets else 0

    embed = discord.Embed(title="📊 Zeran Profile", color=tier[2], timestamp=datetime.now())
    embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="💰 Balance", value=fmt(bal), inline=True)
    embed.add_field(name="🏆 Tier", value=tier[1], inline=True)
    embed.add_field(name="🔥 Daily Streak", value=f"{ud.get('streak', 0)} days", inline=True)
    embed.add_field(name="📈 Total Earned", value=fmt(ud.get('total_earned', 0)), inline=True)
    embed.add_field(name="📉 Total Spent", value=fmt(ud.get('total_lost', 0)), inline=True)
    embed.add_field(name="🎰 Casino W/L", value=f"{ud.get('wins',0)}W / {ud.get('losses',0)}L ({wr:.0f}%)", inline=True)
    embed.set_footer(text="Zeran Banking System")
    await interaction.response.send_message(embed=embed)

# -------- /daily --------
@bot.tree.command(name="daily", description="Claim your daily Zeran reward")
async def daily(interaction: discord.Interaction):
    ud = get_user_data(interaction.user.id)
    now = datetime.now()
    last_str = ud.get("last_daily")

    if last_str:
        last = datetime.fromisoformat(last_str)
        elapsed = now - last
        if elapsed < timedelta(hours=24):
            rem = timedelta(hours=24) - elapsed
            h, r = divmod(int(rem.total_seconds()), 3600)
            m = r // 60
            await interaction.response.send_message(embed=discord.Embed(
                description=f"⏳ Come back in **{h}h {m}m** for your next daily reward.",
                color=discord.Color.orange()
            ), ephemeral=True); return
        ud["streak"] = ud.get("streak", 0) + 1 if elapsed < timedelta(hours=48) else 1
    else:
        ud["streak"] = 1

    base = 100
    bonus = min(ud["streak"] * 25, 500)
    total = base + bonus

    ud["balance"] += total
    ud["last_daily"] = now.isoformat()
    ud["total_earned"] += total
    save_balances(balances)
    add_transaction(interaction.user.id, f"🎁 Daily +{total:,} (streak {ud['streak']})")

    embed = discord.Embed(
        title="🎁 Daily Reward Claimed!",
        color=discord.Color.gold(),
        timestamp=now
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="💰 Base", value=fmt(base), inline=True)
    embed.add_field(name="🔥 Streak Bonus", value=f"+{bonus:,} (Day {ud['streak']})", inline=True)
    embed.add_field(name="💼 Total", value=fmt(total), inline=False)
    embed.add_field(name="🏦 Balance", value=fmt(ud['balance']), inline=False)
    embed.set_footer(text="Zeran Banking System")
    await interaction.response.send_message(embed=embed)

# -------- /coinflip --------
@bot.tree.command(name="coinflip", description="Gamble Zeran on a coin flip")
@app_commands.describe(choice="Heads or Tails", amount="Bet amount")
@app_commands.choices(choice=[
    app_commands.Choice(name="🦅 Heads", value="heads"),
    app_commands.Choice(name="🐉 Tails", value="tails"),
])
async def coinflip(interaction: discord.Interaction, choice: app_commands.Choice[str], amount: int):
    if amount <= 0:
        await interaction.response.send_message(embed=discord.Embed(description="❌ Bet must be positive!", color=discord.Color.red()), ephemeral=True); return
    ud = get_user_data(interaction.user.id)
    if ud["balance"] < amount:
        await interaction.response.send_message(embed=discord.Embed(description="❌ You can't afford that bet!", color=discord.Color.red()), ephemeral=True); return

    result = random.choice(["heads", "tails"])
    win = (choice.value == result)
    emoji = "🦅" if result == "heads" else "🐉"

    if win:
        ud["balance"] += amount
        ud["total_earned"] += amount
        ud["wins"] += 1
        add_transaction(interaction.user.id, f"🪙 Coinflip won: +{amount:,}")
        embed = discord.Embed(title="🪙 Coin Flip", description=f"{emoji} Result: **{result.title()}** — You won!", color=discord.Color.green(), timestamp=datetime.now())
        embed.add_field(name="💰 Winnings", value=f"+{fmt(amount)}", inline=True)
    else:
        ud["balance"] -= amount
        ud["total_lost"] += amount
        ud["losses"] += 1
        add_transaction(interaction.user.id, f"🪙 Coinflip lost: -{amount:,}")
        embed = discord.Embed(title="🪙 Coin Flip", description=f"{emoji} Result: **{result.title()}** — You lost!", color=discord.Color.red(), timestamp=datetime.now())
        embed.add_field(name="💸 Lost", value=f"-{fmt(amount)}", inline=True)
    embed.add_field(name="💼 Balance", value=fmt(ud['balance']), inline=True)
    save_balances(balances)
    embed.set_footer(text="Zeran Casino")
    await interaction.response.send_message(embed=embed)

# -------- /dice --------
@bot.tree.command(name="dice", description="Roll a die — hit a 6 for a 2x payout")
@app_commands.describe(amount="Bet amount")
async def dice(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message(embed=discord.Embed(description="❌ Bet must be positive!", color=discord.Color.red()), ephemeral=True); return
    ud = get_user_data(interaction.user.id)
    if ud["balance"] < amount:
        await interaction.response.send_message(embed=discord.Embed(description="❌ You can't afford that bet!", color=discord.Color.red()), ephemeral=True); return

    roll = random.randint(1, 6)
    win = (roll == 6)

    if win:
        ud["balance"] += amount
        ud["total_earned"] += amount
        ud["wins"] += 1
        add_transaction(interaction.user.id, f"🎲 Dice hit 6: +{amount:,}")
        embed = discord.Embed(title="🎲 Dice Roll", description=f"🎲 You rolled a **6**!\n🎉 Jackpot! 2x payout!", color=discord.Color.gold(), timestamp=datetime.now())
        embed.add_field(name="💰 Winnings", value=f"+{fmt(amount)}", inline=True)
    else:
        ud["balance"] -= amount
        ud["total_lost"] += amount
        ud["losses"] += 1
        add_transaction(interaction.user.id, f"🎲 Dice rolled {roll}: -{amount:,}")
        embed = discord.Embed(title="🎲 Dice Roll", description=f"🎲 You rolled a **{roll}**.\nBetter luck next time!", color=discord.Color.red(), timestamp=datetime.now())
        embed.add_field(name="💸 Lost", value=f"-{fmt(amount)}", inline=True)
    embed.add_field(name="💼 Balance", value=fmt(ud['balance']), inline=True)
    save_balances(balances)
    embed.set_footer(text="Zeran Casino")
    await interaction.response.send_message(embed=embed)

# -------- /leaderboard --------
@bot.tree.command(name="leaderboard", description="Top 10 wealthiest users")
async def leaderboard(interaction: discord.Interaction):
    sorted_users = sorted(balances.items(), key=lambda x: x[1].get("balance", 0), reverse=True)
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    desc = ""
    for i, (uid, data) in enumerate(sorted_users[:10]):
        try:
            member = await bot.fetch_user(int(uid))
            name = member.display_name
        except Exception:
            name = "Unknown"
        bal = data.get("balance", 0)
        tier, _ = get_tier(bal)
        desc += f"{medals[i]} **{name}** — {fmt(bal)} {tier[1]}\n"
    if not desc:
        desc = "No data available yet."

    embed = discord.Embed(title="🏆 Zeran Leaderboard", description=desc, color=discord.Color.gold(), timestamp=datetime.now())
    embed.set_footer(text="Zeran Banking System")
    await interaction.response.send_message(embed=embed)

# -------- /transactions --------
@bot.tree.command(name="transactions", description="View recent transactions")
@app_commands.describe(user="View someone else's (Admin only)")
async def transactions(interaction: discord.Interaction, user: discord.Member = None):
    if user is not None and user.id != interaction.user.id:
        if not interaction.user.guild_permissions.administrator:
    

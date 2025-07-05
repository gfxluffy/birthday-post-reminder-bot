import discord
from discord.ext import tasks
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import pytz
import os
import json

manila_tz = pytz.timezone('Asia/Manila')

# from keep_alive import keep_alive

# keep_alive()  # This starts the Flask web server

# === CONFIG ===
SHEET_NAME = 'LD Volunteer Birthdays'
# JSON_KEYFILE = 'service_account.json'
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
CHANNEL_ID = int(os.getenv['DISCORD_CHANNEL_ID'])  # Replace with your channel ID
GUILD_ID = int(os.getenv['DISCORD_SERVER_ID'])  # Replace with your server ID
TOKEN = os.getenv['DISCORD_TOKEN']  # Set in Replit secrets

# === Google Sheets Setup ===
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

creds_dict = json.loads(GOOGLE_CREDS_JSON)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(creds)
sheet = gc.open(SHEET_NAME).sheet1

# === Discord Setup ===
intents = discord.Intents.default()
intents.guilds = True
bot = discord.Bot(intents=intents)


# === Daily Task: Reset Reminders ===
@tasks.loop(minutes=60)
async def reset_reminders():
    now = datetime.datetime.now(manila_tz)
    if now.hour == 0:  # Midnight reset
        records = sheet.get_all_records()
        for idx in range(2, len(records) + 2):
            sheet.update_cell(idx, 3, 'FALSE')
        print("[INFO] Reset all reminders to FALSE")


# === Daily Task: Birthday Reminder ===
@tasks.loop(minutes=60)
async def birthday_reminder():
    now = datetime.datetime.now(manila_tz)

    if now.hour == 10:  # 10 AM reminder
        today = now.strftime('%m-%d')
        records = sheet.get_all_records()
        channel = bot.get_channel(CHANNEL_ID)

        for idx, row in enumerate(records, start=2):
            name = row['name']
            birthday = row['birthday']
            reminded = str(row['reminded']).lower()
            if birthday == today and reminded != 'true':
                await channel.send(
                    f"🎉 Hey team! Don’t forget to create a birthday post for **{name}**!"
                )
                sheet.update_cell(idx, 3, 'TRUE')


# === Slash Command: /birthdays today ===
@bot.slash_command(guild_ids=[GUILD_ID], description="List birthdays today")
async def birthdays_today(ctx: discord.ApplicationContext):
    today = datetime.datetime.now(manila_tz).strftime('%m-%d')
    records = sheet.get_all_records()
    birthday_names = [
        row['name'] for row in records if row['birthday'] == today
    ]

    if birthday_names:
        names = ', '.join(birthday_names)
        await ctx.respond(f"🎉 Today is the birthday of: **{names}**")
    else:
        await ctx.respond("No birthdays today!")


# === Slash Command: /birthdays upcoming ===
@bot.slash_command(guild_ids=[GUILD_ID],
                   description="List upcoming birthdays in the next 7 days")
async def birthdays_upcoming(ctx: discord.ApplicationContext):
    today = datetime.datetime.now(manila_tz)
    upcoming_names = []

    records = sheet.get_all_records()
    for row in records:
        name = row['name']
        birthday_str = row['birthday']

        # Convert MM-DD to a date in the current year
        try:
            birthday_date = datetime.datetime.strptime(
                f"{today.year}-{birthday_str}", "%Y-%m-%d")
            birthday_date = manila_tz.localize(birthday_date)
        except ValueError:
            continue  # Skip invalid entries

        # Handle year wraparound (e.g., Dec 30 to Jan 2)
        days_until = (birthday_date - today).days
        if 0 < days_until <= 7:
            upcoming_names.append(
                f"**{name}** – {birthday_date.strftime('%b %d')}")

    if upcoming_names:
        msg = "🎈 Upcoming birthdays in the next 7 days:\n" + "\n".join(
            upcoming_names)
    else:
        msg = "No upcoming birthdays in the next 7 days."

    await ctx.respond(msg)


# === Ready Event ===
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')

    # Access channel inside on_ready
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print("⚠️ Channel not found!")
    else:
        await channel.send("Bot is now online!")

    birthday_reminder.start()
    reset_reminders.start()


bot.run(TOKEN)

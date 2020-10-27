import discord
import json
import sys

client = discord.Client()

credentials = json.load(open("credentials.json"))
bot_info = json.load(open("bot-info.json"))
db = json.load(open("database.json"))

def write_db():
    json.dump(db, open("database.json", 'w'))

@client.event
async def on_ready():
    print(f"Logged in as {client.user} in {len(client.guilds)} guild(s)")

@client.event
async def on_guild_join(guild):
    global db
    while guild.me.display_name != db["bot"]["display-name"]:
        try:
            await guild.me.edit(nick = db["bot"]["display-name"])
        except discord.DiscordException:
            continue
    
    db["guilds"][str(guild.id)] = {"prefix": bot_info["default-prefix"]}
    write_db()

@client.event
async def on_message(message):
    global db
    if message.content.lower().startswith(db["guilds"][str(message.guild.id)]["prefix"]):
        print(f"Command issued by {message.author}" + (f" in {message.guild}" if message.guild != None else "") + f": {message.content}")
        args = message.content[len(db["guilds"][str(message.guild.id)]["prefix"]):].split(" ")
        if message.guild == None:
            await message.channel.send("You can only use my commands in a server!")
        else:
            if args[0].lower() == "help":
                if len(args) not in range(1, 3):
                    await message.channel.send("Incorrect number of arguments!")
                else:
                    if len(args) == 1:
                        channel = message.channel
                    else:
                        if args[1].lower() == 'server':
                            channel = message.channel
                        elif args[1].lower() == 'dm':
                            message.author.create_dm()
                            channel = message.author.dm_channel
                    embed = discord.Embed(title = f"{db['bot']['display-name']} command list")
                    for name, value in bot_info["help-embed-fields"].items():
                        embed.add_field(name = db["guilds"][str(message.guild.id)]["prefix"] + name, value = value, inline = False)
                    await channel.send(embed = embed)

            elif args[0].lower() == "prefix":
                if len(args) != 2:
                    await message.channel.send("Incorrect number of arguments!")
                else:
                    if not message.author.guild_permissions.manage_guild:
                        await message.channel.send("Only server moderators can do that! They need to have the Manage Server permission.")
                    else:
                        db["guilds"][str(message.guild.id)]["prefix"] = args[1]
                        write_db()
                        await message.channel.send(f"Prefix successfully changed to {args[1]}.")

            elif args[0].lower() == "renamebot":
                if len(args) < 2:
                    await message.channel.send("Incorrect number of arguments!")
                else:
                    if message.author.id == 299591245976829952:
                        for guild in client.guilds:
                            await guild.me.edit(nick = ' '.join(args[1:]))
                        db["bot"]["display-name"] = ' '.join(args[1:])
                        write_db()
                        await message.channel.send("Nickname successfully changed in all guilds.")
                    else:
                        await message.channel.send("Only my creator can do that!")

            elif args[0].lower() == "shutdownbot":
                if len(args) != 1:
                    await message.channel.send("Incorrect number of arguments!")
                else:
                    if message.author.id == 299591245976829952:
                        await message.channel.send("Shutting down...")
                        sys.exit(0)
                    else:
                        await message.channel.send("Only my creator can do that!")

            else:
                await message.channel.send(f"Invalid command! Use {db['guilds'][str(message.guild.id)]['prefix']}help to see all commands.")

client.run(credentials["discord-bot-token"])

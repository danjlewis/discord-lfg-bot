import discord
import json
import sys
import collections
import datetime
import asyncio

client = discord.Client()

credentials = json.load(open("credentials.json"))
bot_info = json.load(open("bot-info.json"))
db = json.load(open("database.json"))

command_cache = []
reaction_cache = []
command_blocked_users = []
reaction_blocked_users = []

def write_db():
    global db
    db["requests"] = list(filter(lambda x : (datetime.datetime.now() - datetime.datetime.strptime(x["time"], "%d%m%Y%H%M%S") \
                                    < datetime.timedelta(hours = 24)) and bool(x["active"]), db["requests"]))
    with open("database.json", 'w') as f:
        json.dump(db, f, indent = 4)

async def cache_reset():
    global command_cache, reaction_cache, command_blocked_users, reaction_blocked_users
    while True:
        freq = dict(collections.Counter(command_cache)).items()
        block = [(x[0], datetime.datetime.now()) for x in filter(lambda x : x[1] >= bot_info["command-block-threshold"], freq)]
        command_blocked_users += block
        for user_id, _ in block:
            user = client.get_user(user_id)
            try:
                if user.dm_channel == None:
                    await user.create_dm()
                await user.dm_channel.send(f"Stop sending me so many commands! You'll be able to use my commands again in 60 seconds.")
            except discord.Forbidden:
                pass
        command_cache = []
        freq = dict(collections.Counter(reaction_cache)).items()
        block = [(x[0], datetime.datetime.now()) for x in filter(lambda x : x[1] >= bot_info["reaction-block-threshold"], freq)]
        reaction_blocked_users += block
        for user_id, _ in block:
            user = client.get_user(user_id)
            try:
                if user.dm_channel == None:
                    await user.create_dm()
                await user.dm_channel.send(f"Stop reacting to so many LFG requests! You'll be able to react to them again in 60 seconds.")
            except discord.Forbidden:
                pass
        reaction_cache = []
        await asyncio.sleep(10)

async def block_reset():
    global command_blocked_users, reaction_blocked_users
    while True:
        for user, time in command_blocked_users:
            if datetime.datetime.now() - time >= datetime.timedelta(minutes = 1):
                command_blocked_users = list(filter(lambda x : x[0] != user, command_blocked_users))
        for user, time in reaction_blocked_users:
            if datetime.datetime.now() - time >= datetime.timedelta(minutes = 1):
                reaction_blocked_users = list(filter(lambda x : x[0] != user, reaction_blocked_users))
        await asyncio.sleep(5)

@client.event
async def on_ready():
    print(f"Logged in as {client.user} in {len(client.guilds)} guild(s)")
    await client.change_presence(activity = discord.Game(f"{bot_info['default-prefix']}help | {len(client.guilds)} servers"))
    loop = asyncio.get_event_loop()
    loop.create_task(cache_reset())
    loop.create_task(block_reset())

@client.event
async def on_guild_join(guild):
    global db
    await client.change_presence(activity = discord.Game(f"{bot_info['default-prefix']}help | {len(client.guilds)} servers"))
    for _ in range(1800):
        if guild.me.display_name != db["bot"]["display-name"]:
            try:
                await guild.me.edit(nick = db["bot"]["display-name"])
            except discord.Forbidden:
                await asyncio.sleep(1)
        else:
            break

    db["guilds"][str(guild.id)] = {"prefix": bot_info["default-prefix"], "modonly": 0, "dmnotify": 0}
    write_db()

@client.event
async def on_guild_remove(guild):
    await client.change_presence(activity = discord.Game(f"{bot_info['default-prefix']}help | {len(client.guilds)} servers"))

@client.event
async def on_raw_reaction_add(payload):
    global db
    if payload.user_id != bot_info["bot-id"]:
        if payload.message_id in [x["message"] for x in db["requests"]]:
            reaction_cache.append(payload.user_id)
            if payload.user_id not in [x[0] for x in reaction_blocked_users]:
                for index, request in enumerate(db["requests"]):
                    if request["active"] == 1:
                        channel = client.get_channel(request["channel"])
                        try:
                            message = await channel.fetch_message(request["message"])
                        except (discord.NotFound, discord.Forbidden, AttributeError):
                            db["requests"][index]["active"] = 0
                            continue

                        reactions = message.reactions
                        matching = list(filter(lambda x : x.emoji == "👍", reactions))
                        if len(matching) < 1:
                            db["requests"][index]["active"] = 0
                            continue
                        else:
                            thumbsup = matching[0]

                        db["requests"][index]["current-players"] = thumbsup.count - 1
                        if db["requests"][index]["current-players"] >= request["min-players"]:
                            db["requests"][index]["active"] = 0
                            users = await thumbsup.users().flatten()
                            if db["guilds"][str(channel.guild.id)]["dmnotify"]:
                                for client_user in users:
                                    try:
                                        user = client.get_user(client_user.id)
                                        if user.dm_channel == None:
                                            await user.create_dm()
                                        await user.dm_channel.send(f"{client.get_user(request['author']).name}'s {request['game']} group in {channel.guild.name} has enough players!")
                                    except (discord.Forbidden, AttributeError, discord.NotFound):
                                        pass
                            else:
                                try:
                                    await channel.send(f"{client.get_user(request['author']).name}'s {request['game']} group has enough players! " + \
                                        ' '.join([x.mention for x in list(filter(lambda x : x.id != bot_info["bot-id"], users))]))
                                except discord.Forbidden:
                                    pass
                write_db()

@client.event
async def on_message(message):
    global db
    if message.author.id != bot_info["bot-id"]:
        if message.guild == None:
            await message.channel.send("You can only use my commands in a server!")
        else:
            if message.content.lower().startswith(db["guilds"][str(message.guild.id)]["prefix"]):
                command_cache.append(message.author.id)
                if message.author.id not in [x[0] for x in command_blocked_users]:
                    try:
                        print(f"Command issued by {message.author}" + (f" in {message.guild}" if message.guild != None else "") + f": {message.content}")
                        args = message.content[len(db["guilds"][str(message.guild.id)]["prefix"]):].split(" ")
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
                                        if message.author.dm_channel == None:
                                            await message.author.create_dm()
                                        channel = message.author.dm_channel
                                embed = discord.Embed(title = f"{db['bot']['display-name']} by {client.get_user(bot_info['creator-id'])}")
                                for name, value in bot_info["help-embed-fields"].items():
                                    embed.add_field(name = db["guilds"][str(message.guild.id)]["prefix"] + name, value = value, inline = False)
                                await channel.send(embed = embed)
                        
                        elif args[0].lower() == "invite":
                            if len(args) != 1:
                                await message.channel.send("Incorrect number of arguments!")
                            else:
                                await message.channel.send(bot_info["invite-link"])

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
                                if message.author.id == bot_info["creator-id"]:
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
                                if message.author.id == bot_info["creator-id"]:
                                    await message.channel.send("Shutting down...")
                                    sys.exit(0)
                                else:
                                    await message.channel.send("Only my creator can do that!")

                        elif args[0].lower() == "create":
                            if len(args) not in range(3, 5):
                                await message.channel.send("Incorrect number of arguments!")
                            else:
                                if db["guilds"][str(message.guild.id)]["modonly"] == 1 and not message.author.guild_permissions.manage_guild:
                                    await message.channel.send("Moderator only mode is on, so you need the Manage Server permission to do that!")
                                else:
                                    if not args[2].isdigit():
                                        await message.channel.send("The number of players must be a positive non-zero number!")
                                    elif int(args[2]) <= 0:
                                        await message.channel.send("The number of players must be a positive non-zero number!")
                                    elif "@everyone" in message.content or "@here" in message.content:
                                        await message.channel.send("You can't mention everyone through the bot!")
                                    else:
                                        min_players = int(args[2])
                                        mention = None
                                        if len(args) == 4 and len(message.role_mentions) == 0:
                                            await message.channel.send("You didn't mention a role, but you did add a third argument! You need to mention a role if you have 3 arguments.")
                                        elif len(args) == 4 and len(message.role_mentions) == 1 or len(args) == 3:
                                            if len(args) == 4:
                                                mention = message.role_mentions[0].mention

                                            request = await message.channel.send(f"{message.author.display_name} wants to play {args[1].replace(',', ' ')} with at least {min_players} people (when {min_players + 1} users have reacted)! " + \
                                                                        "If you want to play, react thumbs up on this message! This request will stay open for 24 hours.")

                                            await message.delete()
                                            if mention != None:
                                                await request.edit(content = request.content + f" {mention}")
                                            await request.add_reaction("👍")

                                            db["requests"].append({"author": message.author.id, "message": request.id, "channel": request.channel.id, "current-players": 0, "min-players": min_players,
                                                                    "game": args[1].replace(',', ' '), "time": datetime.datetime.strftime(datetime.datetime.now(), "%d%m%Y%H%M%S"), "active": 1})
                                            write_db()

                        elif args[0].lower() == "togglemodonly":
                            if len(args) != 1:
                                await message.channel.send("Incorrect number of arguments!")
                            else:
                                if not message.author.guild_permissions.manage_guild:
                                    await message.channel.send("You need the Manage Server permission to do that!")
                                else:
                                    modonly = int(not bool(db["guilds"][str(message.guild.id)]["modonly"]))
                                    db["guilds"][str(message.guild.id)]["modonly"] = modonly
                                    write_db()
                                    await message.channel.send("Successfully enabled moderator only mode." if modonly else "Successfully disabled moderator only mode.")

                        elif args[0].lower() == "toggledmnotify":
                            if len(args) != 1:
                                await message.channel.send("Incorrect number of arguments!")
                            else:
                                if not message.author.guild_permissions.manage_guild:
                                    await message.channel.send("You need the Manage Server permission to do that!")
                                else:
                                    dmnotify = int(not bool(db["guilds"][str(message.guild.id)]["dmnotify"]))
                                    db["guilds"][str(message.guild.id)]["dmnotify"] = dmnotify
                                    write_db()
                                    await message.channel.send("Successfully enabled DM notification mode." if dmnotify else "Successfully disabled DM notification mode.")

                        else:
                            await message.channel.send(f"Invalid command! Use {db['guilds'][str(message.guild.id)]['prefix']}help to see all commands.")
                    except discord.Forbidden:
                        try:
                            await message.channel.send("I don't have the required permissions!")
                        except discord.Forbidden:
                            pass

client.run(credentials["discord-bot-token"])

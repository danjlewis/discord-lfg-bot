import discord
import json
import sys
import asyncio

client = discord.Client()

credentials = json.load(open("credentials.json"))
bot_info = json.load(open("bot-info.json"))
db = json.load(open("database.json"))

def write_db():
    with open("database.json", 'w') as f:
        json.dump(db, f, indent = 4)

@client.event
async def on_ready():
    print(f"Logged in as {client.user} in {len(client.guilds)} guild(s)")

@client.event
async def on_guild_join(guild):
    global db
    for _ in range(1800):
        if guild.me.display_name != db["bot"]["display-name"]:
            try:
                await guild.me.edit(nick = db["bot"]["display-name"])
            except discord.Forbidden:
                await asyncio.sleep(1)
        else:
            break

    db["guilds"][str(guild.id)] = {"prefix": bot_info["default-prefix"], "modonly": 0}
    write_db()

@client.event
async def on_raw_reaction_add(payload):
    global db
    if payload.user_id != 770631890122178560:
        for index, request in enumerate(db["requests"]):
            if request["active"] == 1:
                channel = client.get_channel(int(request["channel"]))
                try:
                    message = await channel.fetch_message(request["message"])
                except (discord.NotFound, discord.Forbidden):
                    db["requests"][index]["active"] = 0
                    write_db()
                    continue

                reactions = message.reactions
                matching = list(filter(lambda x : x.emoji == "👍", reactions))
                if len(matching) < 1:
                    db["requests"][index]["active"] = 0
                    write_db()
                    continue
                else:
                    thumbsup = matching[0]

                db["requests"][index]["current-players"] = thumbsup.count - 1
                if db["requests"][index]["current-players"] >= request["min-players"]:
                    db["requests"][index]["active"] = 0
                    users = await thumbsup.users().flatten()
                    try:
                        await channel.send(f"{client.get_user(request['author']).display_name}'s {request['game']} group has enough players! " + \
                            ' '.join([x.mention for x in list(filter(lambda x : x.id != 770631890122178560, users))]))
                    except discord.Forbidden:
                        pass
                write_db()

@client.event
async def on_message(message):
    global db
    if message.guild == None:
        await message.channel.send("You can only use my commands in a server!")
    else:
        if message.content.lower().startswith(db["guilds"][str(message.guild.id)]["prefix"]):
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
                            else:
                                min_players = int(args[2])
                                mention = None
                                if len(args) == 4 and len(message.role_mentions) == 0:
                                    await message.channel.send("You didn't mention a role, but you did add a third argument! You need to mention a role if you have 3 arguments.")
                                elif len(args) == 4 and len(message.role_mentions) == 1 or len(args) == 3:
                                    if len(args) == 4:
                                        mention = message.role_mentions[0].mention

                                    request = await message.channel.send(f"{message.author.display_name} wants to play {args[1].replace(',', ' ')} with at least {min_players} people (when {min_players + 1} users have reacted)! " + \
                                                                "If you want to play, react thumbs up on this message!")

                                    await message.delete()
                                    if mention != None:
                                        await request.edit(content = request.content + f" {mention}")
                                    await request.add_reaction("👍")

                                    db["requests"].append({"author": message.author.id, "message": request.id, "channel": request.channel.id, "current-players": 0, "min-players": min_players, "game": args[1].replace(',', ' '), "active": 1})
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
                else:
                    await message.channel.send(f"Invalid command! Use {db['guilds'][str(message.guild.id)]['prefix']}help to see all commands.")
            except discord.Forbidden:
                try:
                    await message.channel.send("I don't have the required permissions!")
                except discord.Forbidden:
                    pass

client.run(credentials["discord-bot-token"])

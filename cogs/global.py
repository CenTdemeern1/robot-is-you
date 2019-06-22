import discord
import numpy     as np

from discord.ext import commands
from itertools   import chain
from json        import load
from os          import listdir
from os.path     import isfile
from PIL         import Image
from subprocess  import call


# Custom exceptions

class InvalidTile(commands.UserInputError):
    pass

class TooManyTiles(commands.UserInputError):
    pass

class StackTooHigh(commands.UserInputError):
    pass

# Takes a list of tile names and generates a gif with the associated sprites
async def magickImages(wordGrid, width, height, palette):
    # For each animation frame
    for fr in range(3):
        # Efficiently converts the grid back into a list of words
        wordList = chain.from_iterable(wordGrid)
        # Opens each image
        paths = [[["empty.png" if word == "-" else "color/%s/%s-%s-.png" % (palette, word, fr) for word in stack] for stack in row] for row in wordGrid]
        imgs = [[[Image.open(fp) for fp in stack] for stack in row] for row in paths]

        # Get new image dimensions
        totalWidth = len(paths[0]) * 24
        totalHeight = len(paths) * 24

        # Montage image
        renderFrame = Image.new("RGBA", (totalWidth, totalHeight))

        # Pastes each image onto the image
        # For each row
        yOffset = 0
        for row in imgs:
            # For each image
            xOffset = 0
            for stack in row:
                for tile in stack:
                    renderFrame.paste(tile, (xOffset, yOffset), tile)
                xOffset += 24
            yOffset += 24

        # Saves the final image
        renderFrame.save(f"renders/{fr}.png")

        # # Merges the images with imagemagick
        # cmd =["magick", "montage", "-geometry", "200%+0+0", "-background", "none",
        # "-colors", "255", "-tile", "%sx%s" % (width, height)]
        # cmd.extend(paths) 
        # cmd.append("renders/render_%s.png" % fr)
        # call(cmd)
    # Joins each frame into a .gif
    fp = open(f"renders/render.gif", "w")
    fp.truncate(0)
    fp.close()
    call(["magick", "convert", "renders/*.png", "-scale", "200%", "-set", "delay", "20", 
        "-set", "dispose", "2", "renders/render.gif"])


class globalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Check if the bot is loading, and that the current guild is not r/surrealmemes 
    async def cog_check(self, ctx):
        return self.bot.get_cog("ownerCog").notLoading and ctx.channel.guild.id != 294479294040768524

    @commands.command()
    @commands.cooldown(2, 10, type=commands.BucketType.channel)
    async def custom(self, ctx):
        msg = discord.Embed(title="Custom Tiles?", description="Want custom tiles added to the bot? " + \
            "DM @RocketRace#0798 about it! \nI can help you if you send me:\n * **The sprites you want added**, " + \
            "preferably in an archived file (without any color, and in 24x24)\n * **The color of the sprites**, " + \
            "an (x,y) coordinate on the default Baba color palette.\nFor examples of this, check the `values.lua` " + \
            "file in your Baba Is You local files!", color=0x00ffff)
        ctx.send(" ", embed=msg)

    # Searches for a tile that matches the string provided
    @commands.command()
    @commands.cooldown(2, 10, type=commands.BucketType.channel)
    async def search(self, ctx, *, query: str):
        matches = []
        # How many results will be shown
        limit = 20
        # For substrings
        cutoff = len(query)
        try:
            # Searches through a list of the names of each tile
            for name in [tile["name"] for tile in self.bot.get_cog("ownerCog").tileColors]:
                match = False
                # If the name starts with {query}, match succeeds
                if name[:cutoff] == query:
                    match = True
                # If the name starts with "text_{query}", match succeeds
                if name[:5] == "text_":
                    if name[5:cutoff + 5] == query:
                        match = True
                if match:
                    if len(matches) >= limit:
                        raise Exception
                    else:
                        matches.append(name)
        except:
            matches.insert(0, f"Found more than {limit} results, showing only first {limit}:")
        else:
            count = len(matches)
            if count == 0:
                await ctx.send(f"Found no results for \"{query}\".")
            else:
                matches.insert(0, f"Found {len(matches)} results for \"{query}\":")
                content = "\n".join(matches)
                await ctx.send(content)

    @commands.cooldown(2, 10, type=commands.BucketType.channel)
    @commands.command(name="list")
    async def listTiles(self, ctx):
        fp = discord.File("tilelist.txt")
        await ctx.send("List of all valid tiles:", file=fp)

    # Generates an animated gif of the tiles provided, using (TODO) the default palette
    @commands.command(aliases=["rule"])
    @commands.cooldown(2, 10, type=commands.BucketType.channel)
    async def tile(self, ctx, pal: str,  *, content: str = ""):
        async with ctx.typing():
            # Determines which palette to use
            # If the argument is not of the format, it is prepended to the tile list
            palette = ""
            tiles = ""
            if pal.startswith("palette:"):
                palette = pal[8:]
                if "".join([palette, ".png"]) not in listdir("palettes"):
                    raise commands.ArgumentParsingError()
                tiles = content
            else:
                palette = "default"
                tiles = " ".join([pal, content])
            
            # Determines if this should be a spoiler
            spoiler = tiles.replace("|", "") != tiles

            # Determines if the command should use text tiles.
            rule = ctx.invoked_with == "rule"

            # Split input into lines
            if spoiler:
                wordRows = tiles.replace("|", "").lower().splitlines()
            else:
                wordRows = tiles.lower().splitlines()
            
            # Split each row into words
            wordGrid = [row.split() for row in wordRows]
            
            # Splits the "text_x,y,z..." shortcuts into "text_x", "text_y", ...
            if not rule:
                for row in wordGrid:
                    toAdd = []
                    for i, word in enumerate(row):
                        if "," in word:
                            each = word.split(",")
                            expanded = [each[0]]
                            expanded.extend(["text_" + segment for segment in each[1:]])
                            toAdd.append((i, expanded))
                    for change in reversed(toAdd):
                        row[change[0]:change[0] + 1] = change[1]

            # Splits "&"-joined words into stacks
            for row in wordGrid:
                for i,stack in enumerate(row):
                    if "&" in stack:
                        row[i] = stack.split("&")
                    else:
                        row[i] = [stack]
                    # Limit how many tiles can be rendered in one space
                    height = len(row[i])
                    if height > 3 and ctx.author.id != self.bot.owner_id:
                        raise StackTooHigh(str(height))

            # Prepends "text_" to words if invoked under the rule command
            if rule:
                wordGrid = [[[word if word == "-" else "text_" + word for word in stack] for stack in row] for row in wordGrid]

            # Get the dimensions of the grid
            lengths = [len(row) for row in wordGrid]
            width = max(lengths)
            height = len(wordRows)

            # Don't proceed if the request is too long.
            # (It shouldn't be that long to begin with because of Discord's 2000 character limit)
            area = width * height
            if area > 50 and ctx.author.id != self.bot.owner_id:
                raise TooManyTiles(str(area))

            # Pad the word rows from the end to fit the dimensions
            [row.extend([["-"]] * (width - len(row))) for row in wordGrid]
            # Finds the associated image sprite for each word in the input
            # Throws an exception which sends an error message if a word is not found.
            try:
                # Each row
                for row in wordGrid:
                    # Each stack
                    for stack in row:
                        # Each word
                        for word in stack:
                            # Checks for the word by attempting to open
                            # If not present, trows an exception.
                            if word != "-":
                                if not isfile(f"color/{palette}/{word}-0-.png"):
                                    raise InvalidTile(word)
            except:
                pass
            else:
                # Merges the images found
                await magickImages(wordGrid, width, height, palette) # Previously used mergeImages()
                # Sends the image through discord
                await ctx.send(content=ctx.author.mention, file=discord.File("renders/render.gif", spoiler=spoiler))

    @tile.error
    async def tileError(self, ctx, error):
        print(error)
        if isinstance(error, InvalidTile):
            word = error.args[0]
            await ctx.send(f"⚠️ Could not find a tile for \"{word}\".")
        elif isinstance(error, TooManyTiles):
            await ctx.send(f"⚠️ Too many tiles ({error.args[0]}). You may only render up to 50 tiles at once, including empty tiles.")
        elif isinstance(error, StackTooHigh):
            await ctx.send(f"⚠️ Stack too high ({error.args[0]}). You may only stack up to 3 tiles on one space.")

    @commands.command()
    @commands.cooldown(2, 5, commands.BucketType.channel)
    async def about(self, ctx):
        content = "ROBOT - Bot for Discord based on the indie game Baba Is You." + \
            "\nDeveloped by RocketRace#0798 (156021301654454272) using the discord.py library." + \
            "\n[Github repository](https://github.com/RocketRace/robot-is-you)" + \
            "\nGuilds: %s" % (len(self.bot.guilds))
        aboutEmbed = discord.Embed(title="About", type="rich", colour=0x00ffff, description=content)
        await ctx.send(" ", embed=aboutEmbed)

    @commands.command()
    @commands.cooldown(2,5, commands.BucketType.channel)
    async def help(self, ctx):
        content = "".join(["Commands:\n", 
            "`+help` : Displays this.\n", 
            "`+about` : Displays bot info.\n",
            "`+tile [palette\\*] [tiles]` : Renders the input tiles. `palette` is an optional argument and ",
            "must be of the format `palette:[name]`. ",
            "Text tiles must be prefixed with \"text\\_\".",
            "Use hyphens to render empty tiles.\n",
            "`+rule [palette\\*] [words]` : Like `+tile`, but only takes word tiles as input. ",
            "Same parameters apply. ",
            "Words do *not* need to be prefixed by \"text\\_\".\n",
            "`+search [query]` : Searches through valid tiles and returns matching tiles.\n",
            "`+list` : Lists every tile useable for the `tile` and `rule` commands."])
        helpEmbed = discord.Embed(title = "Help", type="rich", colour=0x00ffff, description=content)
        await ctx.send(" ", embed=helpEmbed)

def setup(bot):
    bot.add_cog(globalCog(bot))


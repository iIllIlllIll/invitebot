import discord
from discord.ext import commands
from discord.ui import Button, View, Select
import aiosqlite
import json
import re
# 봇 설정
TOKEN = ''
GUILD_ID = ''
CHECK_CHANNEL_ID = ''
REWARD_CHANNEL_ID = ''
INVITE_LOGGER_BOT_ID = ''  # InviteLogger 봇의 ID


intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True  # 추가된 인텐트

client = discord.Client(intents=intents)

async def init_db():
    async with aiosqlite.connect("invites.db") as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS invites (user_id INTEGER PRIMARY KEY, invites INTEGER)"
        )
        await db.commit()

async def get_rewards():
    with open("rewards.json", "r") as file:
        return json.load(file)

@client.event
async def on_ready():
    print(f'봇으로 로그인됨: {client.user}')
    await init_db()
    guild = client.get_guild(int(GUILD_ID))
    reward_channel = guild.get_channel(int(REWARD_CHANNEL_ID))
    if reward_channel:
        embed = discord.Embed(
            title="보상받기",
            description=(
                "🥉 **Bronze**: 5명\n"
                "🥈 **Silver**: 10명\n"
                "🥇 **Gold**: 20명\n"
                "💎 **Diamond**: 40명\n\n"
                "초대확인은 <#{}> 채널에서 확인하세요."
            ).format(CHECK_CHANNEL_ID),
            color=0x00ff00
        )

        view = RewardView()
        await reward_channel.send(embed=embed, view=view)

@client.event
async def on_message(message):
    if message.channel.id == int(CHECK_CHANNEL_ID) and message.author.bot:
        if message.embeds:
            for embed in message.embeds:
                print(f'초기 임베드 메시지 제목: {embed.title}')
                print(f'초기 임베드 메시지 설명: {embed.description}')

@client.event
async def on_message_edit(before, after):
    if after.channel.id == int(CHECK_CHANNEL_ID) and after.author.bot:
        if after.embeds:
            for embed in after.embeds:
                print(f'수정된 임베드 메시지 제목: {embed.title}')
                print(f'수정된 임베드 메시지 설명: {embed.description}')
                if embed.author:
                    print(f'수정된 임베드 작성자: {embed.author.name}')
                if embed.url:
                    print(f'수정된 임베드 URL: {embed.url}')
                for field in embed.fields:
                    print(f'수정된 임베드 필드 이름: {field.name}, 내용: {field.value}')

                description = embed.description

                # 초대 수 추출
                invites_match = re.search(r'You have \*\*(\d+)\*\* invites', description)
                if invites_match:
                    invites = int(invites_match.group(1))
                    
                    # 작성자 찾기
                    author_name = embed.author.name if embed.author else None
                    print(f'임베드 작성자: {author_name}')  # 디버깅용 출력
                    if author_name:
                        user = discord.utils.find(lambda m: m.name == author_name, after.guild.members)
                        if user:
                            async with aiosqlite.connect("invites.db") as db:
                                await db.execute(
                                    "INSERT OR REPLACE INTO invites (user_id, invites) VALUES (?, ?)",
                                    (user.id, invites),
                                )
                                await db.commit()
                            await after.channel.send(f'{user.mention}, 초대 수가 {invites}로 업데이트되었습니다.')
                        else:
                            await after.channel.send(f'사용자 {author_name}를 찾을 수 없습니다.')
                    else:
                        await after.channel.send('임베드에 작성자 정보가 없습니다.')
                else:
                    await after.channel.send('메시지에서 초대 수를 찾을 수 없습니다.')

class RewardView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="정보", style=discord.ButtonStyle.gray, custom_id="check_invites")
    async def check_invites_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect("invites.db") as db:
            async with db.execute("SELECT invites FROM invites WHERE user_id = ?", (interaction.user.id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    invites = row[0]
                    rewards = await get_rewards()
                    current_reward = None
                    for reward in rewards:
                        if invites >= reward["invites"]:
                            current_reward = reward["name"]
                    await interaction.response.send_message(f'현재 초대 수는 {invites}회입니다. 현재 받을 수 있는 보상: {current_reward}.', ephemeral=True)
                else:
                    await interaction.response.send_message('초대 수 데이터를 찾을 수 없습니다.', ephemeral=True)

    @discord.ui.button(label="보상받기", style=discord.ButtonStyle.gray, custom_id="claim_reward")
    async def claim_reward_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        rewards = await get_rewards()
        options = [discord.SelectOption(label=reward["name"], value=reward["name"]) for reward in rewards]
        await interaction.response.send_message("받을 보상을 선택하세요:", view=RewardSelectView(options), ephemeral=True)

    @discord.ui.button(label="미리보기", style=discord.ButtonStyle.gray, custom_id="preview_channels")
    async def preview_channels_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        rewards = await get_rewards()
        options = [discord.SelectOption(label=reward["name"], value=reward["name"]) for reward in rewards]
        await interaction.response.send_message("미리볼 보상을 선택하세요:", view=PreviewSelectView(options), ephemeral=True)

class RewardSelectView(View):
    def __init__(self, options):
        super().__init__(timeout=None)
        self.add_item(RewardSelect(options))

class RewardSelect(Select):
    def __init__(self, options):
        super().__init__(placeholder="받을 보상을 선택하세요...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        reward_name = self.values[0]
        rewards = await get_rewards()
        selected_reward = next((reward for reward in rewards if reward["name"] == reward_name), None)
        if selected_reward:
            async with aiosqlite.connect("invites.db") as db:
                async with db.execute("SELECT invites FROM invites WHERE user_id = ?", (interaction.user.id,)) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0] >= selected_reward["invites"]:
                        role = interaction.guild.get_role(int(selected_reward["role_id"]))
                        if role:
                            await interaction.user.add_roles(role)
                            await interaction.response.send_message(f'축하합니다! {reward_name} 보상을 받았으며, 역할 {role.name}을(를) 받았습니다.', ephemeral=True)
                        else:
                            await interaction.response.send_message(f'보상에 대한 역할을 찾을 수 없습니다: {reward_name}.', ephemeral=True)
                    else:
                        await interaction.response.send_message('이 보상을 받기 위한 초대 수가 충분하지 않습니다.', ephemeral=True)

class PreviewSelectView(View):
    def __init__(self, options):
        super().__init__(timeout=None)
        self.add_item(PreviewSelect(options))

class PreviewSelect(Select):
    def __init__(self, options):
        super().__init__(placeholder="미리볼 보상을 선택하세요...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        reward_name = self.values[0]
        rewards = await get_rewards()
        selected_reward = next((reward for reward in rewards if reward["name"] == reward_name), None)
        if selected_reward:
            category_id = selected_reward["category_id"]
            category = interaction.guild.get_channel(int(category_id))
            if category and isinstance(category, discord.CategoryChannel):
                channels = [channel.name for channel in category.text_channels]
                channels_list = "\n".join(channels)
                await interaction.response.send_message(f'{reward_name} 카테고리의 채널 목록:\n{channels_list}', ephemeral=True)
            else:
                await interaction.response.send_message(f'보상에 대한 카테고리를 찾을 수 없습니다: {reward_name}.', ephemeral=True)

client.run(TOKEN)
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from mautrix.types import MediaMessageEventContent, MessageType, TextMessageEventContent, VideoInfo
from maubot import Plugin, MessageEvent
from maubot.handlers import command
from aiohttp.client_exceptions import InvalidURL
import magic

from typing import Type
from random import randint


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("whitelist")
        helper.copy("command")
        helper.copy("urls")
        helper.copy("video_height")
        helper.copy("video_width")


class ResponseBot(Plugin):
    async def start(self) -> None:
        self.config.load_and_update()

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    def get_command_name(self) -> str:
        return self.config["command"]

    # TODO: Make these configurable?
    def get_upload_web_name(self) -> str:
        return "upload-url"

    def get_dump_mxc_name(self) -> str:
        return "dump-mxc"

    @command.new(name=get_command_name, require_subcommand=False)
    async def bot_command(self, evt: MessageEvent) -> None:
        url = self.config["urls"][randint(0, len(self.config["urls"]) - 1)]
        # This whole thing is such a sodding bodge. Why doesn't matrix store any metadata with its MXC :(
        video = await self.client.download_media(url=url)
        mime_type = magic.from_buffer(video, mime=True)
        content = MediaMessageEventContent(
            url=url,
            body="Response.mp4",
            msgtype=MessageType.VIDEO,
            info=VideoInfo(
                mimetype=mime_type,
                size=len(video),
                width=self.config["video_width"],
                height=self.config["video_height"],
            ),
        )
        await evt.reply(content)

    @bot_command.subcommand(name=get_dump_mxc_name, help="Admin only: Print the full list of media MXC URLs to this channel")
    async def dump_mxc(self, evt: MessageEvent) -> None:
        if evt.sender in self.config["whitelist"]:
            message = TextMessageEventContent(
                msgtype=MessageType.TEXT,
                body=f"MXCs:\n\r{'\n\r'.join(self.config["urls"])}",
            )
            await evt.reply(message)
        else:
            await evt.react("lol no")

    @bot_command.subcommand(name=get_upload_web_name, help="Admin only: Add a new response from a URL")
    @command.argument("url", pass_raw=True, required=True)
    async def upload_web(self, evt: MessageEvent, url: str) -> None:
        if evt.sender in self.config["whitelist"]:
            try:
                resp = await self.http.get(url)
            except InvalidURL:
                await evt.reply("Failed: Invalid URL")
                return
            if resp.status == 200:
                data = await resp.read()
                file_name = url.split("/")[-1]
                mime_type = magic.from_buffer(data, mime=True)
                if "video" in mime_type:
                    uri = await self.client.upload_media(
                        data, mime_type=mime_type, filename=file_name
                    )
                    if not self.config["urls"]:
                        self.config["urls"] = []
                    self.config["urls"].append(uri)
                    self.config.save()
                    await evt.reply(f"Added to config. MXC: {uri}")
                else:
                    await evt.reply("Failed: URL not a video!")
            else:
                await evt.reply(f"Failed: Got Response {resp.status}")
        else:
            await evt.react("lol no")

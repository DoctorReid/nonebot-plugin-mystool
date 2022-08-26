"""
### 帮助相关
### 参考了nonebot-plugin-help
"""
import nonebot.plugin
from nonebot import get_driver, on_command
from nonebot.adapters.onebot.v11 import PrivateMessageEvent
from nonebot.adapters.onebot.v11.message import Message
from nonebot.matcher import Matcher
from nonebot.params import Arg, CommandArg

from .config import mysTool_config as conf

helper = on_command(conf.COMMAND_START+"help", priority=1,
                    aliases={conf.COMMAND_START+"帮助"})
command = list(get_driver().config.command_start)[0] + conf.COMMAND_START

helper.__help_name__ = '帮助'
helper.__help_info__ = f'''\
    欢迎使用米游社小助手帮助系统！\
    \n{command}帮助 -> 获取米游社小助手可调用帮助\
    \n{command}帮助 <功能名> -> 调取目标功能帮助信息\
'''.strip()
plugin = nonebot.plugin.get_plugin('mysTool')


@helper.handle()
async def handle_first_receive(event: PrivateMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if args:
        matcher.set_arg("content", args)
    else:
        await matcher.finish(plugin.metadata.name + plugin.metadata.description + "具体用法：\n" + plugin.metadata.usage.replace('/', command) + '\n' + plugin.metadata.extra)


@helper.got('content')
async def get_result(event: PrivateMessageEvent, content: Message = Arg()):
    arg = content.extract_plain_text().strip()
    if arg == '登陆':
        arg == '登录'
    matchers = plugin.matcher
    for matcher in matchers:
        try:
            if arg.lower() == matcher.__help_name__:
                await helper.finish(f"{command}{matcher.__help_name__}：\n{matcher.__help_info__}")
        except AttributeError:
            continue
    await helper.finish("⚠️未查询到相关功能，请重新尝试")
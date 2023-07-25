"""
### QQ好友相关
"""
import asyncio
from uuid import uuid4

from nonebot import get_driver, on_request, on_command
from nonebot.adapters.onebot.v11 import (Bot, FriendRequestEvent,
                                         GroupRequestEvent, RequestEvent)
from nonebot.internal.matcher import Matcher
from nonebot.params import CommandArg, Command

from .plugin_data import PluginDataManager, write_plugin_data
from .utils import logger, GeneralMessageEvent, COMMAND_BEGIN, get_last_command_sep, uuid4_validate
from ..mys_goods_tool.user_data import UserData

_conf = PluginDataManager.plugin_data
_driver = get_driver()
friendRequest = on_request(priority=1, block=True)


@friendRequest.handle()
async def _(bot: Bot, event: RequestEvent):
    command_start = list(get_driver().config.command_start)[0]
    # 判断为加好友事件
    if isinstance(event, FriendRequestEvent):
        if _conf.preference.add_friend_accept:
            logger.info(f'{_conf.preference.log_head}已添加好友{event.user_id}')
            await bot.set_friend_add_request(flag=event.flag, approve=True)
            if _conf.preference.add_friend_welcome:
                # 等待腾讯服务器响应
                await asyncio.sleep(1.5)
                await bot.send_private_msg(user_id=event.user_id,
                                           message=f'欢迎使用米游社小助手，请发送『{command_start}帮助』查看更多用法哦~')
    # 判断为邀请进群事件
    elif isinstance(event, GroupRequestEvent):
        logger.info(f'{_conf.preference.log_head}已加入群聊 {event.group_id}')


user_binding = on_command(
    _conf.preference.command_start + '用户绑定',
    aliases={
        _conf.preference.command_start + '用户关联',
        _conf.preference.command_start + '数据关联'
    },
    priority=5,
    block=True
)
user_binding.name = '用户绑定'
user_binding.usage = '通过UUID绑定关联其他聊天平台或者其他账号的用户数据，以免去重新登录等操作'
user_binding.extra_usage = """\
具体用法：
{HEAD}用户绑定{SEP}UUID ➢ 查看用于绑定的当前用户数据的UUID密钥
{HEAD}用户绑定{SEP}查询 ➢ 查看当前用户的绑定情况
{HEAD}用户绑定{SEP}还原 ➢ 清除当前用户的绑定关系，使当前用户数据成为空白数据
{HEAD}用户绑定{SEP}刷新UUID ➢ 重新生成当前用户的UUID密钥，原先与您绑定的用户将无法访问您当前的用户数据
{HEAD}用户绑定 <UUID> ➢ 绑定目标UUID的用户数据，当前用户的所有数据将被目标用户覆盖
『{SEP}』为分隔符，使用NoneBot配置中的其他分隔符亦可\
"""


def _recursive_reset_binding(user_id: str):
    """
    递归重置绑定关系，将重置目标用户下的所有绑定关系
    如 A->B->C->D，刷新B的UUID将导致C、D的绑定关系被重置，C、D的用户数据将会是空白数据

    :param user_id: 目标用户ID
    """
    for src, dst in _conf.user_bind.items():
        if dst == user_id:
            del _conf.user_bind[src]
            _conf.users[src] = UserData()
            _recursive_reset_binding(src)


def _recursive_search_binding(user_id: str):
    """
    递归搜索绑定关系链，如 A->B->C->D

    :param user_id: 目标用户ID
    """
    for src, dst in _conf.user_bind.items():
        if dst == user_id:
            yield src
            _recursive_reset_binding(src)


@user_binding.handle()
async def _(
        event: GeneralMessageEvent,
        matcher: Matcher,
        command=Command(),
        command_arg=CommandArg()
):
    user_id = event.get_user_id()
    user = _conf.users.get(user_id)
    if len(command) > 1:
        if user is None:
            await matcher.finish("⚠️您的用户数据不存在，只有进行登录操作以后才会生成用户数据")
        elif command[1] in ["UUID", "uuid"]:
            await matcher.send(
                "🔑您的UUID密钥为：\n"
                f"{user.uuid.upper()}\n"
                "可用于其他聊天平台进行数据绑定，请不要泄露给他人"
            )

        elif command[1] in ["查看", "查询"]:
            if user_id in _conf.user_bind:
                await matcher.send(
                    "🖇️目前您绑定关联了用户：\n"
                    f"{_conf.user_bind[user_id]}\n"
                    "您的任何操作都将会影响到目标用户的数据"
                )
            else:
                await matcher.send(
                    "🖇️目前有以下用户绑定了您的数据：\n"
                    f"{', '.join(_recursive_search_binding(user_id))}"
                )

        elif command[1] in ["还原", "清除"]:
            if user_id not in _conf.user_bind:
                await matcher.finish("⚠️您当前没有绑定任何用户数据")
            else:
                del _conf.user_bind[user_id]
                _conf.users[user_id] = UserData()
                write_plugin_data()
                await matcher.send("✔已清除当前用户的绑定关系，当前用户数据已是空白数据")

        elif command[1] in ["刷新UUID", "刷新uuid"]:
            _recursive_reset_binding(user_id)
            user.uuid = str(uuid4())
            write_plugin_data()
            await matcher.send(
                "✔已刷新UUID密钥，原先绑定的用户将无法访问当前用户数据\n"
                f"🔑新的UUID密钥：{user.uuid.upper()}\n"
                "可用于其他聊天平台进行数据绑定，请不要泄露给他人"
            )

        else:
            await matcher.reject(
                '⚠️您的输入有误，二级命令不正确\n\n'
                f'{matcher.extra_usage.format(HEAD=COMMAND_BEGIN, SEP=get_last_command_sep())}'
            )
    elif not command_arg:
        await matcher.send(
            f"『{COMMAND_BEGIN}{matcher.name}』- 使用说明\n"
            f"{matcher.usage.format(HEAD=COMMAND_BEGIN)}\n"
            f'{matcher.extra_usage.format(HEAD=COMMAND_BEGIN, SEP=get_last_command_sep())}'
        )
    else:
        uuid = str(command_arg).lower()
        if not uuid4_validate(uuid):
            await matcher.finish("⚠️您输入的UUID密钥格式不正确")
        elif uuid == user.uuid:
            await matcher.finish("⚠️您不能绑定自己的UUID密钥")
        else:
            user_filter = filter(lambda x: x[1].uuid == uuid, _conf.users.items())
            dst_user_item = next(user_filter, None)
            if not dst_user_item:
                await matcher.finish("⚠️找不到此UUID密钥对应的用户数据")
            else:
                dst_user_id, _ = dst_user_item
                _conf.do_user_bind(user_id, dst_user_id)
                await matcher.send(f"✔已绑定用户 {dst_user_id} 的用户数据")

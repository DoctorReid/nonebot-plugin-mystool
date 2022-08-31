"""
### 米游社商品兑换前端以及计划任务相关
"""
import asyncio
from datetime import datetime

from nonebot import get_bot, get_driver, on_command
from nonebot.adapters.onebot.v11 import (MessageEvent, MessageSegment,
                                         PrivateMessageEvent)
from nonebot.adapters.onebot.v11.message import Message
from nonebot.matcher import Matcher
from nonebot.params import Arg, ArgPlainText, CommandArg, T_State
from nonebot_plugin_apscheduler import scheduler

from .config import mysTool_config as conf
from .data import UserData
from .exchange import *
from .gameSign import GameInfo
from .utils import NtpTime

driver = get_driver()

COMMAND = list(get_driver().config.command_start)[0] + conf.COMMAND_START

myb_exchange_plan = on_command(
    conf.COMMAND_START+'兑换', aliases={conf.COMMAND_START+'myb_exchange', conf.COMMAND_START+'米游币兑换', conf.COMMAND_START+'米游币兑换计划', conf.COMMAND_START+'兑换计划', conf.COMMAND_START+'兑换'}, priority=4, block=True)
myb_exchange_plan.__help_name__ = "兑换"
myb_exchange_plan.__help_info__ = f"跟随指引，配置米游币商品自动兑换计划。添加计划之前，请先前往米游社设置好收货地址，并使用『{COMMAND}地址』选择你要使用的地址。所需的商品ID可通过命令『{COMMAND}商品』获取。注意，不限兑换时间的商品将不会在此处显示。"
myb_exchange_plan.__help_msg__ = """\
具体用法：
{0}兑换 + <商品ID> ➢ 新增兑换计划
{0}兑换 - <商品ID> ➢ 删除兑换计划
{0}商品 ➢ 查看米游社商品\
""".format(COMMAND)


@myb_exchange_plan.handle()
async def _(event: PrivateMessageEvent, matcher: Matcher, state: T_State, args=CommandArg()):
    """
    主命令触发
    """
    qq_account = int(event.user_id)
    user_account = UserData.read_account_all(qq_account)
    if not user_account:
        await myb_exchange_plan.finish("⚠️你尚未绑定米游社账户，请先进行登录")
    state['qq_account'] = qq_account
    state['user_account'] = user_account

    # 如果使用了二级命令 + - 则跳转进下一步，通过phone选择账户进行设置
    if args:
        matcher.set_arg("content", args)
        if len(user_account) == 1:
            matcher.set_arg('phone', str(user_account[0].phone))
        else:
            phones = [str(user_account[i].phone)
                      for i in range(len(user_account))]
            msg = "您有多个账号，您要配置以下哪个账号的兑换计划？\n"
            msg += "📱" + "\n📱".join(phones)
            await matcher.send(msg)
    # 如果未使用二级命令，则进行查询操作，并结束交互
    else:
        msg = ""
        for account in user_account:
            for plan in account.exchange:
                good = await get_good_detail(plan[0])
                if not good:
                    await matcher.finish("⚠️获取商品详情失败，请稍后再试")
                msg += """\
-- 商品 {0}
- 🔢商品ID：{1}
- 💰商品价格：{2}
- 📅兑换时间：{3}
- 📱账户：{4}\n\n""".format(good.name, good.goodID,
                        good.price, time.strftime("%Y-%m-%d %H:%M:%S",
                                                  time.localtime(good.time)), account.phone)
        if not msg:
            msg = '您还没有兑换计划哦~\n\n'
        await matcher.finish(msg + myb_exchange_plan.__help_msg__)


@myb_exchange_plan.got('phone')
async def _(event: PrivateMessageEvent, matcher: Matcher, state: T_State, phone=Arg()):
    """
    请求用户输入手机号以对账户设置兑换计划
    """
    if isinstance(phone, Message):
        phone = phone.extract_plain_text().strip()
    user_account: List[UserAccount] = state['user_account']

    if phone == '退出':
        await matcher.finish('已成功退出')
    try:
        state["account"] = list(
            filter(lambda account: account.phone == int(phone), user_account))[0]
    except IndexError:
        myb_exchange_plan.reject('⚠️您发送的账号不在以上账号内，请重新发送')


@myb_exchange_plan.got('content')
async def _(event: PrivateMessageEvent, matcher: Matcher, state: T_State):
    """
    处理三级命令，即商品ID
    """
    content = matcher.get_arg('content').extract_plain_text().strip()
    account: UserAccount = state['account']
    arg = [content[0], content[1:].strip()]
    good_dict = {
        'bh3': await get_good_list('bh3'),
        'ys': await get_good_list('ys'),
        'bh2': await get_good_list('bh2'),
        'wd': await get_good_list('wd'),
        'bbs': await get_good_list('bbs')
    }
    Flag = True
    break_flag = False
    good: Good = None
    game: str = None
    for game, good_list in good_dict.items():
        for good in good_list:
            if good.goodID == arg[1]:
                Flag = False
                break_flag = True
                break
        if break_flag:
            break
    if Flag:
        await matcher.finish('⚠️您发送的商品ID不在可兑换的商品列表内，程序已退出')
    state['good'] = good
    if arg[0] == '+':
        uids = []
        if good.time:
            # 若为实物商品，也进入下一步骤，但是传入uid为None
            if good.isVisual:
                game_records = await get_game_record(account)
                await matcher.send("您兑换的是虚拟物品，请发送想要接收奖励的游戏账号UID：")
                if isinstance(game_records, int):
                    pass
                else:
                    msg = f'您米游社账户下的『{list(filter(lambda abbr: abbr[0] == game, GameInfo.ABBR_TO_ID.values()))[0][1]}』账号：'
                    for record in game_records:
                        if GameInfo.ABBR_TO_ID[record.gameID][0] == game:
                            msg += f'\n🎮 {record.regionName}·{record.nickname} - UID {record.uid}'
                        uids.append(record.uid)
                    await matcher.send(msg)
            else:
                matcher.set_arg('uid', None)
            state['uids'] = ['uids']
        else:
            await matcher.finish(f'⚠️该商品暂时不可以兑换，请重新设置')

    elif arg[0] == '-':
        if account.exchange:
            for exchange_good in account.exchange:
                if exchange_good[0] == good.goodID:
                    account.exchange.remove(exchange_good)
                    UserData.set_account(account, event.user_id, account.phone)
                    scheduler.remove_job(job_id=str(
                        account.phone)+'_'+good.goodID)
                    await matcher.finish('兑换计划删除成功')
            await matcher.finish(f"您没有设置商品ID为 {good.goodID} 的兑换哦")
        else:
            await matcher.finish("您还没有配置兑换计划哦")
    else:
        matcher.finish('⚠️您的输入有误，请重新输入')


@myb_exchange_plan.got('uid')
async def _(event: PrivateMessageEvent, matcher: Matcher, state: T_State, uid=ArgPlainText()):
    """
    初始化商品兑换任务，如果传入UID为None则为实物商品，仍可继续
    """
    account: UserAccount = state['account']
    good: Good = state['good']
    uids: List[str] = state['uids']
    if uid:
        if uid == '退出':
            await matcher.finish('已成功退出')
        if uid not in uids:
            await matcher.reject('⚠️您输入的uid不在上述账号内，请重新输入')
    if not account.address:
        await matcher.finish('⚠️您还没有配置地址哦，请先配置地址')

    if account.exchange and (good.goodID, uid) in account.exchange:
        await matcher.send('⚠️您已经配置过该商品的兑换哦！但兑换任务仍会再次初始化。')
    else:
        account.exchange.append((good.goodID, uid))

    # 初始化兑换任务
    exchange_plan = await Exchange(account, good.goodID, uid).async_init()
    if exchange_plan.result == -1:
        await matcher.finish(f"⚠️账户 {account.phone} 登录失效，请重新登录")
    elif exchange_plan.result == -2:
        await matcher.finish("⚠️商品 {} 为游戏内物品，由于未配置stoken，放弃兑换".format(good.goodID))
    elif exchange_plan.result == -3:
        await matcher.finish("⚠️商品 {} 为游戏内物品，由于stoken为\"v2\"类型，且未配置mid，放弃兑换".format(good.goodID))
    elif exchange_plan.result == -4:
        await matcher.finish("⚠️暂不支持商品 {} 所属的游戏，放弃兑换".format(good.goodID))
    elif exchange_plan.result == -5:
        await matcher.finish("⚠️获取商品 {} 的信息时，网络连接失败或服务器返回不正确，放弃兑换".format(good.goodID))
    elif exchange_plan.result == -6:
        await matcher.finish("⚠️获取商品 {} 的信息时，获取用户游戏账户数据失败，放弃兑换".format(good.goodID))
    else:
        scheduler.add_job(id=str(account.phone)+'_'+good.goodID, replace_existing=True, trigger='date', func=exchange,
                          args=(exchange_plan, event.user_id), next_run_time=datetime.fromtimestamp(good.time))

    UserData.set_account(account, event.user_id, account.phone)

    await matcher.finish(f'🎉设置兑换计划成功！将于 {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(good.time))} 开始兑换，到时将会私聊告知您兑换结果')


async def exchange(exchange_plan: Exchange, qq: str):
    """
    执行兑换，并进行通知
    """
    bot = get_bot()
    for i in range(5):
        results = []
        flag = False
        result = await exchange_plan.start()
        results.append(result)
        await asyncio.sleep(0.1)
    for result in results:
        if result[0]:
            flag = True
            break
    if flag:
        await bot.send_private_msg(user_id=qq, message=f"🎉商品 {exchange_plan.goodID} 兑换成功，可前往米游社查看")
    else:
        await bot.send_private_msg(user_id=qq, message=f"⚠️商品 {exchange_plan.goodID} 兑换失败\n{result[1]}")
    for exchange_plan__ in exchange_plan.account.exchange:
        if exchange_plan__[0] == exchange_plan.goodID:
            exchange_plan.account.exchange.remove(exchange_plan__)
    UserData.set_account(exchange_plan.account, qq,
                         exchange_plan.account.phone)


get_good_image = on_command(
    conf.COMMAND_START+'商品列表', aliases={conf.COMMAND_START+'商品图片', conf.COMMAND_START+'米游社商品列表', conf.COMMAND_START+'米游币商品图片', conf.COMMAND_START+'商品'}, priority=4, block=True)
get_good_image.__help_name__ = "商品"
get_good_image.__help_info__ = "获取当日米游币商品信息。添加自动兑换计划需要商品ID，请记下您要兑换的商品的ID。"


@get_good_image.handle()
async def _(event: MessageEvent, matcher: Matcher, arg: Message = CommandArg()):
    # 若有使用二级命令，即传入了想要查看的商品类别，则跳过询问
    if arg:
        matcher.set_arg("content", arg)


@get_good_image.got("content", prompt="""\
        \n请发送您要查看的商品类别:\
        \n- 崩坏3\
        \n- 原神\
        \n- 崩坏2\
        \n- 未定事件簿\
        \n- 米游社\
        \n—— 发送“退出”以结束""".strip())
async def _(event: MessageEvent, matcher: Matcher, arg: Message = ArgPlainText('content')):
    """
    根据传入的商品类别，发送对应的商品列表图片
    """
    if arg == '退出':
        await matcher.finish('已成功退出')
    elif arg in ['原神', 'ys']:
        arg = ('ys', '原神')
    elif arg in ['崩坏3', '崩坏三', '崩3', '崩三', '崩崩崩', '蹦蹦蹦', 'bh3']:
        arg = ('bh3', '崩坏3')
    elif arg in ['崩坏2', '崩坏二', '崩2', '崩二', '崩崩', '蹦蹦', 'bh2']:
        arg = ('bh2', '崩坏2')
    elif arg in ['未定', '未定事件簿', 'wd']:
        arg = ('wd', '未定事件簿')
    elif arg in ['大别野', '米游社']:
        arg = ('bbs', '米游社')
    else:
        await get_good_image.finish('⚠️您的输入有误，请重新输入')
    good_list = await get_good_list(arg[0])
    if good_list:
        img_path = time.strftime(
            f'file:///{conf.goodListImage.SAVE_PATH}/%m-%d-{arg[0]}.jpg', time.localtime())
        await get_good_image.finish(MessageSegment.image(img_path))
    else:
        await get_good_image.finish(f"{arg[1]} 部分目前没有可兑换商品哦~")


@driver.on_startup
async def load_exchange_data():
    """
    启动机器人时自动初始化兑换任务
    """
    all_accounts = UserData.read_all()
    for qq in all_accounts.keys():
        accounts = UserData.read_account_all(qq)
        for account in accounts:
            exchange_list = account.exchange
            for exchange_good in exchange_list:
                good_detail = await get_good_detail(exchange_good[0])
                if good_detail.time < NtpTime.time():
                    # 若重启时兑换超时则删除该兑换
                    account.exchange.remove(exchange_good)
                else:
                    exchange_plan = await Exchange(account, exchange_good[0], exchange_good[1]).async_init()
                    scheduler.add_job(id=str(account.phone)+'_'+exchange_good[0], replace_existing=True, trigger='date', func=exchange, args=(
                        exchange_plan, qq), next_run_time=datetime.fromtimestamp(good_detail.time))

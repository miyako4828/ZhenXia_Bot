import asyncio
from asyncio import TimerHandle
from typing import Dict
from nonebot import require,on_message
from nonebot.rule import Rule
from nonebot.matcher import Matcher
from nonebot.adapters import Event
from nonebot.params import EventPlainText

require("Index_user_management")
require("nonebot_plugin_wordle")

from nonebot_plugin_wordle import Wordle,GuessResult,random_word
from ..Index_user_management import *

import re,random

wordles = []
timers: Dict[str, TimerHandle] = {}
class Enermy():
    def __init__(self,type,target:User,participate:list,object:Wordle) -> None:
        self.type = type
        self.target = target
        self.participate:list = participate
        self.object = object
async def stop_game(matcher: Matcher, event:Event,session: str,user:User):
    timers.pop(session, None)
    gid = event.get_session_id().split("_")[0]
    for i in range(len(wordles)):
        if wordles[i]['session']==session:
            e:Enermy = wordles[i]['enermy']
            wordles.pop(i)
            msg = "猜单词超时，游戏结束！"
            moneyDesc = None
            if len(e.object.guessed_words) >= 1:
                dict = {}
                for u in e.participate:
                    dict[u] = dict.get(u, 0) + 1
                for key,val in dict.items():
                    money = (e.object.length-len(e.object.guessed_words)+5)*val/len(e.object.guessed_words)
                    if key==e.participate[-1]:money*=2
                    moneyDesc += MessageSegment.at(key)+f" 被抢走{-round(money,2)}火币!\n"
                    u = Group(gid).find_user_by_qid(key).add_money(money)
                msg += f"\n{e.object.result}"
            await matcher.finish(msg+"\n"+moneyDesc)

def set_timeout(matcher: Matcher,event, session: str, user:User,timeout: float = 300):
    timer = timers.get(session, None)
    if timer:
        timer.cancel()
    loop = asyncio.get_running_loop()
    timer = loop.call_later(
        timeout, lambda: asyncio.ensure_future(stop_game(matcher,event,session,user))
    )
    timers[session] = timer
def wordle_battle(matcher:Matcher,event:Event,user:User,enermy:Enermy):
    set_timeout(matcher,event,event.get_session_id(),user)
    for w in wordles:
        if w['enermy']==enermy:
            word = event.get_plaintext()
            if '提示'==word:
                hint = enermy.object.get_hint()
                if not hint.replace("*", ""):
                    return 'noHint',enermy
                else: return 'hint',enermy
            elif '投降'==word:
                return GuessResult.LOSS,enermy
            if len(word) != enermy.object.length:
                return 'noLength',enermy
            state = enermy.object.guess(word)
            wordles[wordles.index(w)]['enermy'] = enermy
    return state,enermy
def game_running(event: Event) -> bool:
    for wd in wordles:
        if wd['session'].split("_")[0]==event.get_session_id().split("_")[0]:
            return True
    return False
def get_word_input(msg: str = EventPlainText()) -> bool:
    if re.fullmatch(r"^[a-zA-Z]{3,8}$", msg) or msg=='投降' or msg=='提示':
        return True
    return False

wordle = on_command("wordle",aliases={"沃兜"},priority=12,block=True)
@wordle.handle()
async def wordle_action(event:Event):
    gid = event.get_session_id().split("_")[0]
    u = Group(gid).find_user_by_qid(event.get_user_id())
    if not u:
        await wordle.finish("你还没注册呢！发送注册来让小霞认识一下你吧！")
    else:
        for w in wordles:
            if w['session'].split("_")[0]==gid:
                await wordle.finish("有一个沃兜在进行哦")
        if random.random()<=0.2:
            word,meaning = random_word("CET6",random.randint(4,7))
            e = Enermy('精英',u,[],Wordle(word,meaning))
            wordles.append({'session':event.get_session_id(),'enermy':e,'from':'explore'})
            await wordle.finish(MessageSegment.image(e.object.draw())+f"\n你遇到了精英沃兜！\n你有{e.object.rows}次机会猜出单词，单词长度为{e.object.length}，请发送单词")
        else:
            word,meaning = random_word("CET4",random.choice([5,5,5,5,6]))
            e = Enermy('野生',u,[],Wordle(word,meaning))
            wordles.append({'session':event.get_session_id(),'enermy':e,'from':'explore'})
            await wordle.finish(MessageSegment.image(e.object.draw())+f"\n你遇到了野生沃兜！\n你有{e.object.rows}次机会猜出单词，单词长度为{e.object.length}，请发送单词")
wordMatcher = on_message(Rule(game_running) & get_word_input, block=True, priority=12)
@wordMatcher.handle()
async def _(event: Event):
    gid = event.get_session_id().split("_")[0]
    u = Group(gid).find_user_by_qid(event.get_user_id())
    if not u:
        await wordle.finish("你还没注册呢！发送注册来让小霞认识一下你吧！")
    else:
        for w in wordles:
            gid = event.get_session_id().split("_")[0]
            if gid==w['session'].split("_")[0]:
                user = Group(gid).find_user_by_qid(event.get_user_id())
                state,e = wordle_battle(wordle,event,user,w['enermy'])
                if state==GuessResult.WIN or state==GuessResult.LOSS:
                    e.participate.append(user.qid)
                    wordles[wordles.index(w)]['enermy'] = e
                    wordles.pop(wordles.index(w))
                    if state==GuessResult.LOSS:
                        dict = {}
                        for u in e.participate:
                            dict[u] = dict.get(u, 0) + 1
                        moneyDesc = None
                        for key,val in dict.items():
                            money = (-e.object.length)*val/len(e.object.guessed_words)
                            if key==e.participate[-1]:money*=2
                            moneyDesc += MessageSegment.at(key)+f" 被抢走{-round(money,2)}火币!\n"
                            u = Group(gid).find_user_by_qid(key).add_money(money)
                        await wordle.finish(MessageSegment.image(e.object.draw())+f'\n{e.object.result}\n'+moneyDesc)
                    elif state==GuessResult.WIN:
                        dict = {}
                        for u in e.participate:
                            dict[u] = dict.get(u, 0) + 1
                        moneyDesc = None
                        for key,val in dict.items():
                            money = (e.object.length-len(e.object.guessed_words)+5)*(val/len(e.object.guessed_words))
                            if key==e.participate[-1]:money*=2
                            moneyDesc += MessageSegment.at(key)+f" 获得{round(money,2)}火币!\n"
                            u = Group(gid).find_user_by_qid(key).add_money(money)
                        await wordle.finish(MessageSegment.image(e.object.draw())+f'\n{e.object.result}\n战斗胜利！\n'+moneyDesc)
                else:
                    if state=='noHint':
                        await wordle.send("\n你还没有猜对过一个字母哦~再猜猜吧~")
                    elif state=='hint':
                        hint = e.object.get_hint()
                        await wordle.send(MessageSegment.image(e.object.draw_hint(hint)))
                    elif state=='noLength':
                        pass
                    elif state==GuessResult.DUPLICATE:
                        await wordle.send("你已经猜过这个单词了呢")
                    elif state==GuessResult.ILLEGAL:
                        await wordle.send(f"你确定 {event.get_plaintext()} 是一个合法的单词吗？")
                    else:
                        e.participate.append(user.qid)
                        wordles[wordles.index(w)]['enermy'] = e
                        await wordle.send(MessageSegment.image(e.object.draw()))
                break
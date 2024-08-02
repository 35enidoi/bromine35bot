import os
import subprocess
import asyncio
from uuid import uuid4
from random import randint
from datetime import timedelta
import logging
from functools import partial
from typing import NoReturn, Union, Callable, Coroutine, Any
import random

from misskey import (
    Misskey,
    exceptions as MiExceptions,
)
import requests

import core as BrCore
from reversi import reversi_sys


TESTMODE = False
MY_USER_ID = "9iipvideci"
instance = "misskey.io"
token = os.environ["MISSKEY_BOT_TOKEN"]
HOST_USER_ID = "9gwek19h00"

LIST_DETECT_JYOPA = (":_zi::_lyo::_pa:", "じょぱ",
                     ":_ma::_lu::_a::_wave:", "まぅあ～",
                     ":zyopa_kuti_kara_daeki_to_iq_ga_ahure_deru_oto:")


class Bromine_withmsk(BrCore.Bromine):
    def __init__(self,
                 instance: str,
                 token: str,
                 *,
                 msk_loglevel: int = logging.DEBUG) -> None:
        """misskey.py付きになったBromine(お得！)"""
        super().__init__(instance, token)

        # 変数作成
        self.INSTANCE = instance
        self.TOKEN = token
        self.__pendings: list[Callable[[], Coroutine[Any, Any, NoReturn]]] = []

        # misskey.pyインスタンス作成
        self.mk = Misskey(address=self.INSTANCE, i=self.TOKEN)

        # logger作成
        self.__logger = logging.getLogger("Br_msk")
        self.__log = partial(self.__logger.log, msk_loglevel)

    def add_pending(self, func: Callable[[], Coroutine[Any, Any, NoReturn]]) -> None:
        if asyncio.iscoroutinefunction(func):
            if self.is_running:
                raise ValueError("メイン関数が実行中なので追加不可能です。")
            else:
                self.__pendings.append(func)
        else:
            raise TypeError("関数はコルーチンでなければなりません。")

    async def main(self) -> NoReturn:
        pendings = asyncio.gather(*(i() for i in self.__pendings), return_exceptions=True)
        try:
            await super().main()
        finally:
            pendings.cancel()
            try:
                await pendings
            except asyncio.CancelledError:
                pass

    async def api_post(self, endp: str, wttime: int, **dicts) -> requests.Response:
        """misskey.pyが対応していないエンドポイントなどに対して使うやつ
        endp: エンドポイント
        wttime: timeoutまで待つ時間"""
        url = f"https://{self.INSTANCE}/api/"+endp
        dicts["i"] = self.TOKEN
        return await asyncio.to_thread(requests.post, url, json=dicts, timeout=wttime)

    async def create_reaction(self, id: str, reaction: str, Instant: bool = False) -> None:
        """リアクションを作成するやつ
        id: ノートid
        reaction: リアクションの名前
        Instance: 即時にリアクションするかどうか"""
        if not Instant:
            await asyncio.sleep(random.randint(3, 5))
        try:
            await asyncio.to_thread(self.mk.notes_reactions_create, id, reaction)
            self.__log(f"create reaction success:{reaction}")
        except Exception as e:
            self.__log(f"create reaction fail:{e}")

    async def create_follow(self, id: str) -> None:
        """リアクションを作成する関数
        id: フォローするユーザーID"""
        try:
            await asyncio.to_thread(self.mk.following_create, id)
            self.__log("follow create success")
        except Exception as e:
            self.__log(f"follow create fail:{e}")

    async def create_note(self, **kargs) -> Union[dict, None]:
        """Misskey().notes_createのラッパー"""
        try:
            note = await asyncio.to_thread(self.mk.notes_create, **kargs)
            self.__log(f"note create success. noteid: {note['createdNote']['id']}")
            return note
        except (
            MiExceptions.MisskeyAPIException,
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
        ) as e:
            # misskey.pyのAPI側で例外が発生したとき
            self.__log(f"note create fail: {e}")
            return None


class zyanken_system:
    """じゃんけんしすてむ"""
    def __init__(self, id_: str, fin_time_: int, br: Bromine_withmsk) -> None:
        self.br = br
        self.noteid = id_
        self.fintime = fin_time_
        choice = randint(0, 2)
        choices = ("グー", "チョキ", "パー")
        self.zyanken_txt = f"じゃんけんぽん！\n私は{choices[choice]}を出したぞ！！！"

    async def fin_timer(self):
        await asyncio.sleep(self.fintime)
        await self.br.create_note(text=self.zyanken_txt, renote_id=self.noteid)


class Bromine35:
    def __init__(self, br: Bromine_withmsk, bakuhaevent: asyncio.Event) -> None:
        self.notes_queue = asyncio.Queue()
        self.bakuha = bakuhaevent
        self.br = br
        self.TESTMODE = TESTMODE
        self.MY_USER_ID = MY_USER_ID
        # cpuwatchは今使ってない
        br.add_pending(self.zyanken_starter)
        br.add_pending(self.local_speed_watch)
        # br.add_pending(cpuwatch)
        br.add_comeback(self.detect_not_follow)
        br.ws_connect("main", self.onnotify)
        br.ws_connect("localTimeline", self.onnote)
        br.ws_connect("reversi", self.onreversi)

    async def zyanken_starter(self):
        """じゃんけんするのを開始する奴"""
        interval = 120
        randominterval = True
        zyanken_start_mes = "じゃんけんするぞ:blobcat_mudamudamuda:"
        fintime = 60*5
        random_haba = 50
        while True:
            await asyncio.sleep(60*(interval + (randint(0, random_haba) if randominterval else 0)))
            note = await self.br.create_note(
                text=zyanken_start_mes,
                poll_choices=("グー", "チョキ", "パー"),
                poll_expired_after=timedelta(seconds=fintime)
            )
            if note is not None:
                zksys = zyanken_system(note["createdNote"]["id"], fintime, self.br)
                await zksys.fin_timer()

    async def local_speed_watch(self):
        interval = 61
        while True:
            await asyncio.sleep(60*interval)
            notes = 0
            re_notes = 0
            while not self.notes_queue.empty():
                if await self.notes_queue.get() == "note":
                    notes += 1
                else:
                    re_notes += 1
            # print(f"local speed notes;{notes}, renotes;{re_notes}")
            # print("per second notes;{} re_notes;{}".format(round(notes/(60*interval), 2), round(re_notes/(60*interval), 2)))
            notetext = "ローカルの流速です:eyes_fidgeting:\n ノートの数;{}個 {}毎秒".format(notes, round(notes/(60*interval), 2))
            notetext += "\n リノートの数;{}個 {}毎秒\n インターバル;{}分".format(re_notes, round(re_notes/(60*interval), 2), interval)
            await self.br.create_note(text=notetext)

    async def cpuwatch(self):
        while True:
            cpu_temp = []
            for _ in range(120):
                cpu_temp += await self.cpuwatch_short()
            print("watched cpu!\n{} {} {:.2f}".format(max(cpu_temp),
                                                      min(cpu_temp),
                                                      sum(cpu_temp)/len(cpu_temp)))
            await self.br.create_note(
                text="ラズパイ君の温度です！\n最大温度;{} 最小温度;{} 平均温度;{:.2f}".format(
                                                                            max(cpu_temp),
                                                                            min(cpu_temp),
                                                                            sum(cpu_temp)/len(cpu_temp)),
                visibility="specified",
                visible_user_ids=["9gwek19h00"]
                                                                            )

    async def cpuwatch_short(self, reply=None, directs=None):
        cpu_temp = []
        if reply is not None:
            await self.br.create_reaction(reply, ":murakamisan_nurukopoppu_tyottotoorimasuyo2:")
        for _ in range(60):
            cpu_temp.append(float((subprocess.run("vcgencmd measure_temp",
                                                  shell=True,
                                                  stdin=subprocess.PIPE,
                                                  stdout=subprocess.PIPE,
                                                  text=True).stdout.split("="))[1].replace("\n", "").replace("'C", "")))
            await asyncio.sleep(1)
        if reply is not None:
            await self.br.create_reaction(reply, ":blobcat_ok_sign:")
            await self.br.create_note(text="ラズパイ君の温度です！\n最大温度;{} 最小温度;{} 平均温度;{:.2f}".format(
                                            max(cpu_temp),
                                            min(cpu_temp),
                                            sum(cpu_temp)/len(cpu_temp)
                                        ),
                                      reply_id=reply,
                                      visibility="specified",
                                      visible_user_ids=directs
                                      )
        else:
            return cpu_temp

    async def detect_not_follow(self):
        try:
            followers = await asyncio.to_thread(self.br.mk.users_followers, user_id=MY_USER_ID)
            not_in = []
            for i in followers:
                if not i["follower"]["isFollowing"] and not i["follower"]["hasPendingFollowRequestFromYou"]:
                    not_in.append(i["followerId"])
            for i in not_in:
                print(f"detect not follow! id:{i}")
                await self.br.create_follow(i)
                await asyncio.sleep(10)
        except Exception as e:
            print(f"detect not follow error:{e}")
            await asyncio.sleep(10)
            asyncio.create_task(self.detect_not_follow)

    async def onnote(self, note: dict):
        note = note["body"]
        if note.get("text"):
            text_ = note["text"]
            if note["user"]["isBot"]:
                pass
            elif note["cw"] is not None:
                pass
            elif any(char in text_ for char in map(str, LIST_DETECT_JYOPA)):
                print(f"jyopa detect noteid;{note['id']}")
                asyncio.create_task(self.br.create_reaction(note["id"], ":blobcat_frustration:"))
        # ノートはlocal_speed_watchに流す
        if note.get("renoteId"):
            await self.notes_queue.put("renote")
        else:
            await self.notes_queue.put("note")

    async def onnotify(self, note):
        print("notification coming")
        if note["type"] == "followed":
            print("follow coming")
            print(note["body"]["name"])
            asyncio.create_task(self.br.create_follow(note["body"]["id"]))
        elif note["type"] == "mention":
            print("mention coming")
            if note["body"]["userId"] == HOST_USER_ID:
                print("host notify coming")
                if note["body"].get("text"):
                    if "cpuwatch" in note["body"]["text"]:
                        if note["body"]["visibility"] == "specified":
                            visible = [note["body"]["userId"]]
                        else:
                            visible = None
                        asyncio.create_task(self.cpuwatch_short(note["body"]["id"], visible))
                        return
                    elif "explosion" in note["body"]["text"]:
                        print("explosion!!!")
                        await self.br.create_reaction(note["body"]["id"], ":explosion:", Instant=True)
                        if not TESTMODE:
                            await self.br.create_note(text="bot、爆発します。:explosion:")
                        self.bakuha.set()
                    elif "invite" in note["body"]["text"]:
                        print("reversi invite comming")
                        print(note["body"]["text"].split(" ")[-1])
                        res = await self.br.api_post("reversi/match", 30, userId=str(note["body"]["text"].split("\n")[-1]))
                        print(res.status_code)
                        asyncio.create_task(self.br.create_reaction(note["body"]["id"], "🆗", Instant=True))
                        return
            if note["body"]["user"]["isBot"]:
                print("mention bot detected")
                print(note["body"]["user"]["name"])
            elif "ping" in note["body"]["text"]:
                print("ping coming")
                asyncio.create_task(self.br.create_note(text="bomb!:explosion:", reply_id=note["body"]["id"]))
                asyncio.create_task(self.br.create_reaction(note["body"]["id"], "💣", Instant=True))
            elif "怪文書" in note["body"]["text"]:
                print("kaibunsyo coming")
                asyncio.create_task(self.kaibunsyo(note["body"]["id"]))
            else:
                print("mention coming")
                asyncio.create_task(self.br.create_reaction(note["body"]["id"], "❤️"))

    async def onreversi(self, info):
        if info["type"] == "invited":
            if TESTMODE:
                print("invite!")
            if not (userid := info["body"]["user"]["id"]) in reversi_sys.playing_user_list:
                # プレイ中のuseridのリストにぶち込む
                reversi_sys.playing_user_list.append(userid)
                res = await self.br.api_post("reversi/match", 30, userId=userid)
                id_ = str(uuid4())
                rv = reversi_sys(self, res.json(), id_)
                self.br.add_comeback(func=rv.comeback, id=rv.socketid, block=True)
                self.br.ws_connect("reversiGame", rv.interface, id_, gameId=rv.game_id)
                # フォームは今のところ未対応みたい

                # # フォーム送信
                # form = [{"id":i, "type":v[0], "label":v[1], "value":v[2]}for i, v in rv._form.items()]
                # self.br.ws_send("channel", {id:rv.socketid, type:"init-form", body:form})
        elif info["type"] == "matched":
            game = info["body"]["game"]
            userid = game[f"user{2 if game['user1Id'] == MY_USER_ID else 1}"]["id"]
            if TESTMODE:
                print("matched!")
            if userid not in reversi_sys.playing_user_list:
                # プレイ中のuseridのリストにぶち込む
                reversi_sys.playing_user_list.append(userid)
                id_ = str(uuid4())
                rv = reversi_sys(self, game, id_)
                self.br.add_comeback(func=rv.comeback, id=rv.socketid, block=True)
                self.br.ws_connect("reversiGame", rv.interface, id_, gameId=rv.game_id)
        else:
            print("reversi anything comming")
            print(info)

    async def kaibunsyo(self, noteid: str):
        kaibunsyo = ""
        try:
            notes = await asyncio.to_thread(self.br.mk.notes_local_timeline, randint(5, 15))
        except MiExceptions.MisskeyAPIException:
            return
        for i in notes:
            if i["cw"] is not None:
                pass
            elif i["text"] is not None:
                kaibunsyo += i["text"].replace("\n", "")[0:randint(0, len(i["text"]) if len(i["text"]) <= 15 else 15)]
        await self.br.create_note(text=kaibunsyo.replace("#", "＃").replace("@", "*"), reply_id=noteid)

    async def setup(self):
        await self.br.create_note(text="bot、動きます。:ablobblewobble:")
        await self.br.create_reaction("9iisgwj3rf", "✅")

    async def fin(self, yoteigai: bool, is_explosion: bool):
        if is_explosion:
            # 爆破した時
            print("爆破された...")
        else:
            if yoteigai:
                await self.br.create_note(text="bot異常終了します:ablobcatcryingcute:\n@iodine53 異常終了したから調査しろ:blobhai:")
            else:
                await self.br.create_note(text="botとまります:blob_hello:")
        await self.br.create_reaction("9iisgwj3rf", "❌", Instant=True)


async def main():
    # bakuha_eventを待つ関数
    async def __bakuha_daemon(brm_: asyncio.Task[None], bakuha_ev: asyncio.Event):
        await bakuha_ev.wait()
        # 爆破イベントが発火した場合、キャンセルする。
        brm_.cancel()

    # ログの設定
    logformat = "%(levelname)-9s %(asctime)s [%(name)s](%(funcName)s) %(message)a"
    level = logging.INFO
    br_level = logging.INFO
    br_mk_level = logging.INFO
    logpath = "botlog.txt"

    logging.basicConfig(format=logformat,
                        filename=os.path.abspath(os.path.join(os.path.dirname(__file__), f'./{logpath}')),
                        encoding="utf-8",
                        level=level)

    # 変数を作る
    isyoteigai = True
    br = Bromine_withmsk(instance, token, msk_loglevel=br_mk_level)
    br.loglevel = br_level
    bakuha_event = asyncio.Event()
    brm = Bromine35(br, bakuha_event)
    # 一応爆破イベントdaemonが作られる前に停止されたとき用に初期化
    bakuha_wait_d: Union[asyncio.Task, None] = None
    if not TESTMODE:
        await brm.setup()
    try:
        print("start...")
        main_ = asyncio.create_task(br.main())
        bakuha_wait_d = asyncio.create_task(__bakuha_daemon(main_, bakuha_event))
        await main_
    except asyncio.CancelledError:
        isyoteigai = False
    else:
        isyoteigai = False
    finally:
        if bakuha_wait_d is not None:
            # 爆破イベントdaemonの処理
            bakuha_wait_d.cancel()
            try:
                await bakuha_wait_d
            except asyncio.CancelledError:
                pass

        if TESTMODE:
            # テストモード時は特に何もしない
            pass
        else:
            # テストモードじゃない時、終了処理
            await brm.fin(isyoteigai, bakuha_event.is_set())

        print("Fin...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("stopped!")

import os
import subprocess
import asyncio
from uuid import uuid4
from random import randint
from datetime import timedelta

from misskey import exceptions

import core
from reversi import reversi_sys


TESTMODE = False
instance = "misskey.io"
token = os.environ["MISSKEY_BOT_TOKEN"]
HOST_USER_ID = "9gwek19h00"

LIST_DETECT_JYOPA = (":_zi::_lyo::_pa:", "じょぱ",
                     ":_ma::_lu::_a::_wave:", "まぅあ～",
                     ":zyopa_kuti_kara_daeki_to_iq_ga_ahure_deru_oto:")


class zyanken_system:
    """じゃんけんしすてむ"""
    def __init__(self, id_: str, fin_time_: int, br: core.Bromine) -> None:
        self.br = br
        self.noteid = id_
        self.fintime = fin_time_
        choice = randint(0, 2)
        choices = ("グー", "チョキ", "パー")
        self.zyanken_txt = f"じゃんけんぽん！\n私は{choices[choice]}を出したぞ！！！"

    async def fin_timer(self):
        await asyncio.sleep(self.fintime)
        await asyncio.to_thread(self.br.safe_wrap_retbool,
                                self.br.mk.notes_create,
                                text=self.zyanken_txt,
                                renote_id=self.noteid)


class Bromine35:
    def __init__(self, br: core.Bromine, bakuhaevent: asyncio.Event) -> None:
        self.notes_queue = asyncio.Queue()
        self.bakuha = bakuhaevent
        self.br = br
        # cpuwatchは今使ってない
        br.add_pending(self.zyanken_starter)
        br.add_pending(self.local_speed_watch)
        # br.add_pending(cpuwatch)
        br.on_comebacker(func=self.detect_not_follow)
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
            note = await asyncio.to_thread(self.br.safe_wrap,
                                           self.br.mk.notes_create,
                                           text=zyanken_start_mes,
                                           poll_choices=("グー", "チョキ", "パー"),
                                           poll_expired_after=timedelta(seconds=fintime))
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
            await self.br.create_note(notetext)

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
                                                                            sum(cpu_temp)/len(cpu_temp)), direct=["9gwek19h00"]
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
            await self.br.create_note("ラズパイ君の温度です！\n最大温度;{} 最小温度;{} 平均温度;{:.2f}".format(
                max(cpu_temp),
                min(cpu_temp),
                sum(cpu_temp)/len(cpu_temp)), reply=reply, direct=directs)
        else:
            return cpu_temp

    async def detect_not_follow(self):
        try:
            followers = await asyncio.to_thread(self.br.mk.users_followers, user_id=self.br.MY_USER_ID)
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
                            await self.br.create_note("bot、爆発します。:explosion:")
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
                if note["body"]["visibility"] == "specified":
                    asyncio.create_task(self.br.create_note("bomb!:explosion:",
                                                            reply=note["body"]["id"],
                                                            direct=[note["body"]["userId"]]))
                else:
                    asyncio.create_task(self.br.create_note("bomb!:explosion:", reply=note["body"]["id"]))
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
                rv = reversi_sys(self.br, res.json(), id_, TESTMODE)
                self.br.on_comebacker(rv.socketid, rv.comeback, block=True)
                self.br.ws_connect("reversiGame", rv.interface, id_, gameId=rv.game_id)
                # フォームは今のところ未対応みたい

                # # フォーム送信
                # form = [{"id":i, "type":v[0], "label":v[1], "value":v[2]}for i, v in rv._form.items()]
                # self.br.ws_send("channel", {id:rv.socketid, type:"init-form", body:form})
        elif info["type"] == "matched":
            game = info["body"]["game"]
            userid = game[f"user{2 if game['user1Id'] == self.br.MY_USER_ID else 1}"]["id"]
            if TESTMODE:
                print("matched!")
            if userid not in reversi_sys.playing_user_list:
                # プレイ中のuseridのリストにぶち込む
                reversi_sys.playing_user_list.append(userid)
                id_ = str(uuid4())
                rv = reversi_sys(self.br, game, id_, TESTMODE)
                self.br.on_comebacker(rv.socketid, rv.comeback, block=True)
                self.br.ws_connect("reversiGame", rv.interface, id_, gameId=rv.game_id)
        else:
            print("reversi anything comming")
            print(info)

    async def kaibunsyo(self, noteid: str):
        kaibunsyo = ""
        try:
            notes = await asyncio.to_thread(self.br.mk.notes_local_timeline, randint(5, 15))
        except exceptions.MisskeyAPIException:
            return
        for i in notes:
            if i["cw"] is not None:
                pass
            elif i["text"] is not None:
                kaibunsyo += i["text"].replace("\n", "")[0:randint(0, len(i["text"]) if len(i["text"]) <= 15 else 15)]
        await self.br.create_note(kaibunsyo.replace("#", "＃").replace("@", "*"), reply=noteid)

    async def setup(self):
        await self.br.create_note("bot、動きます。:ablobblewobble:")
        await self.br.create_reaction("9iisgwj3rf", "✅")

    async def fin(self, yoteigai: bool):
        if yoteigai:
            await self.br.create_note("bot異常終了します:ablobcatcryingcute:\n@iodine53 異常終了したから調査しろ:blobhai:")
        else:
            await self.br.create_note("botとまります:blob_hello:")
        await self.br.create_reaction("9iisgwj3rf", "❌", Instant=True)


async def main():
    br = core.Bromine(instance, token)
    bakuha_event = asyncio.Event()
    brm = Bromine35(br, bakuha_event)
    if not TESTMODE:
        await brm.setup()
    try:
        main_ = asyncio.create_task(br.main())
        await bakuha_event.wait()
        main_.cancel()
        try:
            await main_
        except asyncio.CancelledError:
            print("Explosioned.")
    except Exception:
        isyoteigai = True
    except asyncio.CancelledError:
        print("oni")
        isyoteigai = False
    else:
        isyoteigai = False
    finally:
        if TESTMODE:
            print("Fin...")
        elif bakuha_event.is_set():
            print("bakuhasareta...")
        else:
            await brm.fin(isyoteigai)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("stopped!")

from misskey import Misskey, exceptions
import requests
import websockets
import json
import asyncio
from datetime import datetime
import uuid
import subprocess
import random
import os

from reversi import reversi_sys

BOT_LOG_FILE = "botlog.txt"
TESTMODE = True

class bromine35:

    class Explosion(Exception):
        pass

    def __init__(self) -> None:
        self.TESTMODE = TESTMODE
        self.V = 1.1
        self.TOKEN = os.environ["MISSKEY_BOT_TOKEN"]
        self.channels = {}
        self.on_comeback = {}
        self.send_queue = asyncio.Queue()

        self.INSTANCE = "misskey.io"
        self.mk = Misskey(self.INSTANCE, i=self.TOKEN)
        self.WS_URL = f'wss://{self.INSTANCE}/streaming?i={self.TOKEN}'
        self.MY_USER_ID = self.mk.i()["id"]

        self.HOST_USER_ID = "9gwek19h00"
        self.explosion = False
        self.LIST_DETECT_JYOPA = (":_zi::_lyo::_pa:","じょぱ",
                                  ":_ma::_lu::_a::_wave:","まぅあ～",
                                  ":zyopa_kuti_kara_daeki_to_iq_ga_ahure_deru_oto:")

    async def main(self):
        print("main start")
        self.notes_queue = asyncio.Queue()
        pendings = [self.local_speed_watch()]
        other = asyncio.gather(*pendings, return_exceptions=True)
        try:
            await asyncio.create_task(self.runner())
        except Exception as e:
            raise e
        finally:
            other.cancel()
            try:
                await other
            except asyncio.exceptions.CancelledError:
                print("catch")
            print("main finish")

    async def connect_check(self):
        while True:
            try:
                async with websockets.connect(self.WS_URL):
                    pass
                print("connect checked")
            except asyncio.exceptions.TimeoutError:
                print("timeout")
                textworkput( "timeout at {}".format(datetime.now().strftime("%Y/%m/%d %H:%M:%S")))
                await asyncio.sleep(30)
            except websockets.exceptions.WebSocketException as e:
                print(f"websocket error: {e}")
                textworkput( "websocket error;{} at {}".format(e,datetime.now().strftime("%Y/%m/%d %H:%M:%S")))
                await asyncio.sleep(40)
            except Exception as e:
                print(f"yoteigai error:{e}")
                textworkput( "yoteigai error;{} at {}".format(e,datetime.now().strftime("%Y/%m/%d %H:%M:%S")))
                await asyncio.sleep(60)
            else:
                break
        await asyncio.sleep(2)

    async def runner(self):
        __CONST_CHANNEL = ("main", "localTimeline", "reversi")
        __CONST_FUNCS = (self.onnotify, self.onnote, self.onreversi)
        # データ構造
        # uuid4 : (接続するチャンネル, 受け取り関数(async), params)
        # dict(uuid4 : tuple(channel, coroutinefunc, params))
        self.channels = {str(uuid.uuid4()):(v, __CONST_FUNCS[i], {}) for i, v in enumerate(__CONST_CHANNEL)}
        # このwsdは最初に接続失敗すると未定義になるから保険のため
        wsd = None
        while True:
            try:
                asyncio.create_task(self.detect_not_follow())
                print("connect start")
                async with websockets.connect(self.WS_URL) as ws:
                    wsd = asyncio.create_task(self.ws_send_d(ws))
                    for i in self.on_comeback.values():
                        await i()
                    print(self.channels.keys(),"connect")
                    while True:
                        data = json.loads(await ws.recv())
                        if self.explosion:
                            raise self.Explosion("BOOM!!!!!!")
                        if data['type'] == 'channel':
                            for i, v in self.channels.items():
                                if data["body"]["id"] == i:
                                    asyncio.create_task(v[1](data["body"]))
                                    break
                            else:
                                print("謎のチャンネルからのデータが来ました")
                                print(data)
                        else:
                            print("channel以外からのデータが来ました")
                            print(data["type"])
                            print(data)

            except (websockets.exceptions.WebSocketException, asyncio.exceptions.TimeoutError) as e:
                print("error occured")
                print(e)
                textworkput("error occured:{} at {}".format(e,datetime.now().strftime("%Y/%m/%d %H:%M:%S")))
                await asyncio.sleep(2)
                await self.connect_check()
                continue

            except Exception as e:
                print(e, e.args)
                textworkput(f"fatal Error; {e}")
                break
            
            finally:
                if type(wsd) == asyncio.Task:
                    wsd.cancel()
                    try:
                        await wsd
                    except asyncio.CancelledError:
                        pass

    def on_comebacker(self, id:str, func=None, rev:bool=False):
        """comebackを作る
        
        delの時はfuncいらない"""
        if rev:
            del self.on_comeback[id]
        else:
            if not asyncio.iscoroutinefunction(func):
                raise ValueError("与える関数はコルーチンでなければなりません")
            self.on_comeback[id] = func

    async def ws_send_d(self, ws:websockets.WebSocketClientProtocol):
        __PRIORITY_TYPES = ("connect", "disconnect")
        for i, v in self.channels.items():
            await ws.send(json.dumps({        
            "type": "connect",
            "body": {
                "channel": v[0],
                "id": i,
                "params": v[2]
            }
            }))
        # queueの中身の初期化兼disconnect等を処理
        while not self.send_queue.empty():
            getter = await self.send_queue.get()
            if any(getter["type"] is i for i in __PRIORITY_TYPES):
                await ws.send(json.dumps({        
                "type": getter[0],
                "body": getter[1]
                }))
                if TESTMODE:
                    print(f"putted:{getter}")
        while True:
            # 型:tuple(type:str, body:dict)
            getter = await self.send_queue.get()
            await ws.send(json.dumps({        
            "type": getter[0],
            "body": getter[1]
            }))
            if TESTMODE:
                print(f"putted:{getter}")

    def ws_send(self, type_:str, body:dict) -> None:
        """ウェブソケットへsendするdaemonのqueueに送る奴"""
        self.send_queue.put_nowait((type_, body))

    def ws_connect(self, channel:str, func_, id_:str=None, **params) -> str:
        """channelに接続するときに使う関数 idを返す"""
        if not asyncio.iscoroutinefunction(func_):
            raise ValueError("func_がコルーチンじゃないです。")
        if id_ is None:
            id_ = str(uuid.uuid4())
        self.channels[id_] = (channel, func_, params)
        body = {
            "channel" : channel,
            "id" : id_,
            "params" : params
        }
        self.ws_send("connect", body)
        return id_

    def ws_disconnect(self, id_:str) -> None:
        """channelの接続解除に使う関数"""
        self.channels.pop(id_)
        body = {"id":id_}
        self.ws_send("disconnect", body)

    async def detect_not_follow(self):
        try:
            followers = await asyncio.to_thread(self.mk.users_followers, user_id=self.MY_USER_ID)
            not_in = []
            for i in followers:
                if not i["follower"]["isFollowing"] and not i["follower"]["hasPendingFollowRequestFromYou"]:
                    not_in.append(i["followerId"])
            for i in not_in:
                print(f"detect not follow! id:{i}")
                await self.create_follow(i)
                await asyncio.sleep(10)

        except exceptions.MisskeyAPIException as e:
            print(f"detect not follow error:{e}")
            await asyncio.sleep(10)
            asyncio.create_task(self.detect_not_follow)

    async def onnote(self, note):
        note = note["body"]
        if note.get("text"):
            text_ = note["text"]
            if note["user"]["isBot"]:
                pass
            elif note["cw"] is not None:
                pass
            elif any(char in text_ for char in map(str, self.LIST_DETECT_JYOPA)):
                print(f"jyopa detect noteid;{note['id']}")
                asyncio.create_task(self.create_reaction(note["id"], ":blobcat_frustration:"))
        if note.get("renoteId"):
            await self.notes_queue.put(("renote",note["userId"]))
        else:
            await self.notes_queue.put(("note",note["userId"]))

    async def onnotify(self, note):
        print("notification coming")
        if note["type"] == "followed":
            print("follow coming")
            print(note["body"]["name"])
            asyncio.create_task(self.create_follow(note["body"]["id"]))
        elif note["type"] == "mention":
            print("mention coming")
            if note["body"]["userId"] == self.HOST_USER_ID:
                print("host notify coming")
                if note["body"].get("text"):
                    if "cpuwatch" in note["body"]["text"]:
                        if note["body"]["visibility"] == "specified":
                            visible = [note["body"]["userId"]]
                        else:
                            visible = None
                        asyncio.create_task(self.cpuwatch_short(note["body"]["id"],visible))
                        return
                    elif "explosion" in note["body"]["text"]:
                        print("explosion!!!")
                        await self.create_reaction(note["body"]["id"],":explosion:",Instant=True)
                        if not TESTMODE:
                            await self.create_note("bot、爆発します。:explosion:")
                        self.explosion = True
                        return
                    elif "invite" in note["body"]["text"]:
                        print("reversi invite comming")
                        print(note["body"]["text"].split(" ")[-1])
                        res = await self.api_post("reversi/match", 30, userId=str(note["body"]["text"].split("\n")[-1]))
                        print(res.status_code)
                        asyncio.create_task(self.create_reaction(note["body"]["id"],"🆗",Instant=True))
                        return
            if note["body"]["user"]["isBot"]:
                print("mention bot detected")
                print(note["body"]["user"]["name"])
            elif "ping" in note["body"]["text"]:
                print("ping coming")
                if note["body"]["visibility"] == "specified":
                    asyncio.create_task(self.create_note("bomb!:explosion:", reply=note["body"]["id"], direct=[note["body"]["userId"]]))
                else:
                    asyncio.create_task(self.create_note("bomb!:explosion:", reply=note["body"]["id"]))
                asyncio.create_task(self.create_reaction(note["body"]["id"],"💣",Instant=True))
            elif "怪文書" in note["body"]["text"]:
                print("kaibunsyo coming")
                asyncio.create_task(self.kaibunsyo(note["body"]["id"]))
            else:
                print("mention coming")
                asyncio.create_task(self.create_reaction(note["body"]["id"],"❤️"))

    async def onreversi(self, info):
        if info["type"] == "invited":
            if TESTMODE:
                print("invite!")
            if not (userid := info["body"]["user"]["id"]) in reversi_sys.playing_user_list:
                # プレイ中のuseridのリストにぶち込む
                reversi_sys.playing_user_list.append(userid)
                res = await self.api_post("reversi/match", 30, userId=userid)
                id_ = str(uuid.uuid4())
                rv = reversi_sys(self, res.json(), id_)
                self.on_comebacker(rv.socketid, rv.comeback)
                await self.ws_connect("reversiGame", rv.interface, id_, gameId=rv.game_id)
                # フォームは今のところ未対応みたい

                # # フォーム送信
                # form = [{"id":i, "type":v[0], "label":v[1], "value":v[2]}for i, v in rv._form.items()]
                # await self.ws_send("channel", {id:rv.socketid, type:"init-form", body:form})
        elif info["type"] == "matched":
            game = info["body"]["game"]
            if TESTMODE:
                print("matched!")
            if not (userid := game[f"user{2 if game['user1Id'] == self.MY_USER_ID else 1}"]["id"]) in reversi_sys.playing_user_list:
                # プレイ中のuseridのリストにぶち込む
                reversi_sys.playing_user_list.append(userid)
                id_ = str(uuid.uuid4())
                rv = reversi_sys(self, game, id_)
                self.on_comebacker(rv.socketid, rv.comeback)
                await self.ws_connect("reversiGame", rv.interface, id_, gameId=rv.game_id)
        else:
            print("reversi anything comming")
            print(info)

    async def local_speed_watch(self):
        interval = 61
        while True:
            await asyncio.sleep(60*interval)
            notes = 0
            re_notes = 0
            userdetect = {}
            while not self.notes_queue.empty():
                notesinfo = await self.notes_queue.get()
                if notesinfo[0] == "note":
                    notes += 1
                else:
                    re_notes += 1
                if notesinfo[1] not in userdetect.keys():
                    userdetect[notesinfo[1]] = 1
                else:
                    userdetect[notesinfo[1]] += 1
            userdetect = sorted(userdetect.items(), key=lambda x:x[1], reverse=True)
            for i in range(10 if len(userdetect) >= 10 else len(userdetect)):
                print(f"{i+1}; {userdetect[i]}")
            print(f"local speed notes;{notes}, renotes;{re_notes}")
            print("per second notes;{} re_notes;{}".format(round(notes/(60*interval), 2), round(re_notes/(60*interval), 2)))
            await self.create_note("ローカルの流速です:eyes_fidgeting:\n ノートの数;{}個 {}毎秒\n リノートの数;{}個 {}毎秒\n インターバル;{}分".format(notes, round(notes/(60*interval), 2), re_notes, round(re_notes/(60*interval), 2), interval))

    async def kaibunsyo(self, noteid):
        kaibunsyo = ""
        try:
            notes = await asyncio.to_thread(self.mk.notes_local_timeline, random.randint(5,15))
        except exceptions.MisskeyAPIException:
            return
        for i in notes:
            if i["cw"] is not None:
                pass
            elif i["text"] is not None:
                kaibunsyo += i["text"].replace("\n", "")[0:random.randint(0,len(i["text"]) if len(i["text"]) <= 15 else 15)]
        await self.create_note(kaibunsyo.replace("#", "＃").replace("@","*"),reply=noteid)

    async def api_post(self, endp:str, wttime:int, **dicts) -> requests.Response:
        url = f"https://{self.INSTANCE}/api/"+endp
        dicts["i"] = self.TOKEN
        return await asyncio.to_thread(requests.post, url, json=dicts, timeout=wttime)

    async def create_reaction(self, id, reaction, Instant=False):
        if not Instant:
            await asyncio.sleep(random.randint(3,5))
        try:
            await asyncio.to_thread(self.mk.notes_reactions_create, id, reaction)
            print("create reaction", reaction)
        except Exception as e:
            print("create reaction fail")
            print(e)

    async def create_follow(self, id):
        try:
            await asyncio.to_thread(self.mk.following_create, id)
            print(f"follow create success id;{id}")
        except Exception as e:
            print(f"follow fail;{e}")

    async def create_note(self, text, cw=None, direct=None, reply=None):
        if direct == None:
            notevisible = "public"
        else:
            notevisible = "specified"
        try:
            await asyncio.to_thread(self.mk.notes_create, text, cw=cw,visibility=notevisible,visible_user_ids=direct,reply_id=reply)
            print("note create")
        except Exception as e:
            print(f"note create fail:{e}")

    async def cpuwatch(self):
        while True:
            cpu_temp = []
            for _ in range(120):
                cpu_temp += await self.cpuwatch_short()
            print("watched cpu!\n{} {} {:.2f}".format(max(cpu_temp),min(cpu_temp),sum(cpu_temp)/len(cpu_temp)))
            await self.create_note(text="ラズパイ君の温度です！\n最大温度;{} 最小温度;{} 平均温度;{:.2f}".format(max(cpu_temp),min(cpu_temp),sum(cpu_temp)/len(cpu_temp)), direct=["9gwek19h00"])

    async def cpuwatch_short(self, reply=None, directs=None):
        cpu_temp = []
        if reply != None:
            await self.create_reaction(reply,":murakamisan_nurukopoppu_tyottotoorimasuyo2:")
        for _ in range(60):
            cpu_temp.append(float((subprocess.run("vcgencmd measure_temp", shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True).stdout.split("="))[1].replace("\n", "").replace("'C", "")))
            await asyncio.sleep(1)
        if reply != None:
            await self.create_reaction(reply,":blobcat_ok_sign:")
            await self.create_note("ラズパイ君の温度です！\n最大温度;{} 最小温度;{} 平均温度;{:.2f}".format(max(cpu_temp),min(cpu_temp),sum(cpu_temp)/len(cpu_temp)),reply=reply,direct=directs)
        else:
            return cpu_temp

def textworkput(text):
    filepath = os.path.abspath(os.path.join(os.path.dirname(__file__),f'./{BOT_LOG_FILE}'))
    with open(filepath,"a") as f:
        f.write(text+"\n")

def main():
    if not TESTMODE:
        textworkput("bot start at {}".format(datetime.now().strftime("%Y/%m/%d %H:%M:%S")))
    print("start")
    try:
        br = bromine35()
        if not TESTMODE:
            asyncio.run(br.create_note("bot、動きます。:ablobblewobble:"))
            asyncio.run(br.create_reaction("9iisgwj3rf", "✅"))
        asyncio.run(br.main())
    except KeyboardInterrupt as e:
        print("break!!!")
        if len(e.args) == 0:
            if not TESTMODE:
                asyncio.run(br.create_note("botとまります:blob_hello:"))
    except br.Explosion:
        if not TESTMODE:
            asyncio.run(br.create_note("botとまります:blob_hello:"))
    else:
        if not TESTMODE:
            asyncio.run(br.create_note("bot異常終了します:ablobcatcryingcute:\n@iodine53 異常終了したから調査しろ:blobhai:"))
    finally:
        print("finish")
        if not TESTMODE:
            asyncio.run(br.create_reaction("9iisgwj3rf", "❌", Instant=True))
            textworkput("bot stop at {}".format(datetime.now().strftime("%Y/%m/%d %H:%M:%S")))

if __name__ == "__main__":
    main()
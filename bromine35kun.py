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

BOT_LOG_FILE = "botlog.txt"
TESTMODE = False

class bromine35:
    def __init__(self) -> None:
        self.V = 1.1
        self.TOKEN = os.environ["MISSKEY_BOT_TOKEN"]
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
        await self.connect_check()
        if not TESTMODE:
            await self.create_note("bot、動きます。:ablobblewobble:")
            self.mk.notes_reactions_create("9iisgwj3rf", "✅")
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
        self.send_queue = asyncio.Queue()
        self.channels = {str(uuid.uuid4()):(v, __CONST_FUNCS[i], {}) for i, v in enumerate(__CONST_CHANNEL)}
        self.on_comeback = {}
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
                            raise KeyboardInterrupt
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
        for i, v in self.channels.items():
            await ws.send(json.dumps({        
            "type": "connect",
            "body": {
                "channel": v[0],
                "id": i,
                "params": v[2]
            }
            }))
        while True:
            # 型:tuple(type:str, body:dict)
            getter = await self.send_queue.get()
            await ws.send(json.dumps({        
            "type": getter[0],
            "body": getter[1]
            }))
            if TESTMODE:
                print(f"putted:{getter}")

    async def ws_send(self, type_:str, channel:str=None, id_:str=None, func_=None, **dicts) -> str:
        """ウェブソケットへsendして場合によっては記憶したりするもの
        type_:str
        channel:str
        id_:str|None
        func_:coroutinefunction
        ```
        if type_ == "connect":
            チャンネルを記憶
            func_が必要
            idがNoneの場合idを自動生成する
            idを返す
            body = {
                "channel" : channel,
                "id" : id_,
                "params" : dicts
            }
        else:
            Noneを返す
            if type_ == "disconnect:
                チャンネルを記憶から削除
                body = {
                    "id" : id_
                }
            else:
                body = dicts
        ```"""
        if type_ == "connect":
            if not asyncio.iscoroutinefunction(func_):
                raise ValueError("func_がコルーチンじゃないです。")
            if id_ is None:
                ret = str(uuid.uuid4())
            else:
                ret = id_
            body = {
                "channel" : channel,
                "id" : id_,
                "params" : dicts
            }
            self.channels[ret] = (channel, func_, dicts)
        else:
            ret = None
            if type_ == "disconnect":
                self.channels.pop(id_)
                body = {
                    "id" : id_
                }
            else:
                body = dicts
        await self.send_queue.put((type_, body))
        return ret

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
            if not (userid := info["body"]["user"]["id"]) in self.reversi_sys.playing_user_list:
                # プレイ中のuseridのリストにぶち込む
                self.reversi_sys.playing_user_list.append(userid)
                res = await self.api_post("reversi/match", 30, userId=userid)
                id_ = str(uuid.uuid4())
                rv = self.reversi_sys(self, res.json(), id_)
                await self.ws_send("connect", func_=rv.interface, channel="reversiGame", id_=id_, gameId=rv.game_id)
                # フォームは今のところ未対応みたい

                # # フォーム送信
                # form = [{"id":i, "type":v[0], "label":v[1], "value":v[2]}for i, v in rv._form.items()]
                # await self.ws_send("channel", id=rv.socketid, type="init-form", body=form)
        elif info["type"] == "matched":
            game = info["body"]["game"]
            if TESTMODE:
                print("matched!")
            if not (userid := game[f"user{2 if game['user1Id'] == self.MY_USER_ID else 1}"]["id"]) in self.reversi_sys.playing_user_list:
                # プレイ中のuseridのリストにぶち込む
                self.reversi_sys.playing_user_list.append(userid)
                id_ = str(uuid.uuid4())
                rv = self.reversi_sys(self, game, id_)
                await self.ws_send("connect", func_=rv.interface, channel="reversiGame", id_=id_, gameId=rv.game_id)
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

    class reversi_sys:

        # ゲームのダブりを防ぐためのリスト
        playing_user_list = []

        def __init__(self, br, content:dict, socketid:str) -> None:
            """reversi system"""
            # reversi version
            self.RV = 2.0
            # bromine35の保存
            self.br = br
            # id保存
            self.game_id = content["id"]
            self.socketid = socketid
            # comebackの作成
            self.br.on_comebacker(self.socketid, self.comeback)

            # ゲーム設定
            # ループボードの時はめんどいのでokの値をFalseにして承認しない
            self.ok:bool = True

            # user1であるかどうか
            self.user1:bool = content["user1Id"] == self.br.MY_USER_ID
            self.enemyid = content[f"user{2 if self.user1 else 1}Id"]

            self.llotheo:bool = False
            self.put_everywhere:bool = False
            # self.revstrange:bool = False

            # formは今のところ未対応みたい

            # # 内部の分岐用のフォーム
            # # dict[id : tuple[type, label, default, val]]
            # self._form = {
            #     "revstrange" : ("switch",
            #                     "Botが駒を押すときに一番少ないものを選ぶようになります",
            #                     False,
            #                     self.revstrange)
            # }
            # # フォーム
            # form = [{"id":i, "type":v[0], "label":v[1], "value":v[2]}for i, v in self._form.items()]
            # self.br.ws_send("channel", id=self.socketid, type="init-form", body=form)

            # テストモードならリバーシシステムが準備完了なことを言う
            if TESTMODE:
                print("reversi system on ready", f"gameid:{self.game_id}")

        async def comeback(self):
            res = await self.br.api_post("reversi/show-game", 30, gameId=self.game_id)
            if res.status_code == 200:
                ds = res.json()
                if ds["isEnded"]:
                    await self.disconnect()
                else:
                    if ds["isStarted"]:
                        self.create_banmen(ds["map"])
                        for i in ds["logs"][:-1]:
                            self.set_point(i[3], rev=(bool(i[1]) != self.colour))
                        if bool((last := ds["logs"][-1])[1]) != self.colour:
                            # 処理めんどいのでinterfaceに流す
                            await self.interface({"type":"log", "body":{"player":(not self.colour), "pos":last[3]}})
                        else:
                            self.set_point(last[3])

        async def interface(self, info):
            """ここにウェブソケットをつなげる"""
            # print(info)
            if (type_ := info["type"]) == "canceled":
                await self.disconnect()
            elif type_ == "updateSettings":
                body = info["body"]
                if (key := body["key"]) == "isLlotheo":
                    self.llotheo = body["value"]
                elif key == "loopedBoard":
                    self.ok = not body["value"]
                elif key == "canPutEverywhere":
                    self.put_everywhere = body["value"]
            elif type_ == "changeReadyStates":
                if info["body"][f"user{1 if self.user1 else 2}"] is self.ok:
                    pass
                else:
                    if info["body"][f"user{2 if self.user1 else 1}"]:
                        await self.br.ws_send("channel", id=self.socketid, type="ready", body=self.ok)
            else:
                if type_ == "ended":
                    print("finish reversi gameid:", self.game_id)
                    await self.disconnect()
                    if not TESTMODE:
                        url = f"https://{self.br.INSTANCE}/reversi/g/{self.game_id} \n"
                        enemyname = info["body"]["game"][f"user{2 if self.user1 else 1}"]["name"]
                        if info["body"]["game"].get("winnerId"):
                            if info["body"]["game"]["winnerId"] == self.br.MY_USER_ID:
                                txt = "に勝ちました:nullcatchan_nope:"
                            else:
                                txt = "に負けました:oyoo:"
                        elif info["body"]["game"].get("surrenderedUserId"):
                            txt = "に投了されました:thinknyan:"
                        else:
                            txt = "との戦いで引き分けになりました:taisen_arigatou_gozaimasita:"
                        # await self.br.create_note(url+enemyname+txt)
                elif type_ == "started":
                    print("start reversi! gameid:", self.game_id)
                    self.colour = (bool(info["body"]["game"]["black"]-1) is not self.user1)
                    self.create_banmen(info["body"]["game"]["map"])
                    if TESTMODE:
                        print("どこでも置ける:", self.put_everywhere)
                        print("ロセオ:", self.llotheo)
                        print("色:", self.colour)
                    else:
                        url = f"https://{self.br.INSTANCE}/reversi/g/{self.game_id} \n"
                        enemyname = info["body"]["game"][f"user{2 if self.user1 else 1}"]["name"]
                        txt = "と対戦を開始しました:taisen_yorosiku_onegaisimasu:"
                        # await self.br.create_note(url+enemyname+txt)
                    if self.colour:
                        pts = self.search_point()
                        if len(pts) != 0:
                            if self.llotheo:
                                mpts = [i for i in pts if i[0] == min(pts, key=lambda x:x[0])[0]]
                            else:
                                mpts = [i for i in pts if i[0] == max(pts, key=lambda x:x[0])[0]]
                            pt = mpts[random.randint(0, len(mpts)-1)]
                            self.set_point(pos := self.postoyx(pt[1], rev=True))
                            await self.br.ws_send("channel", id=self.socketid, type="putStone", body={"pos":pos})
                elif type_ == "log":
                    body = info["body"]
                    is_this_me = (body["player"]==self.colour)
                    if not is_this_me:
                        self.set_point(body["pos"], rev=True)
                        if self.RV < 2:
                            # V1
                            pts = self.search_point()
                        elif self.RV < 3:
                            # V2
                            pts = self.search_point_v2()
                        elif self.RV < 4:
                            ... # V3
                        if len(pts) != 0:
                            if self.llotheo:
                                mpts = [i for i in pts if i[0] == min(pts, key=lambda x:x[0])[0]]
                            else:
                                mpts = [i for i in pts if i[0] == max(pts, key=lambda x:x[0])[0]]
                            pt = mpts[random.randint(0, len(mpts)-1)]
                            self.set_point(pos := self.postoyx(pt[1], rev=True))
                            await self.br.ws_send("channel", id=self.socketid, type="putStone", body={"pos":pos})
                            # 相手が打てないときの処理を忘れていた
                            pt = self.search_point(True)
                            if len(pt) == 0:
                                if self.check_valid_koma() != 0:
                                    await self.interface({"type":"enemycantput"})
                        elif self.put_everywhere:
                            # どこにも置けるモードの時
                            canput = []
                            for y, i in enumerate(self.banmen):
                                for x, r in enumerate(i):
                                    if r == 0:
                                        canput.append((y, x))
                            if len(canput) != 0:
                                self.set_point(pos:=self.postoyx(canput[random.randint(0, len(canput)-1)], rev=True))
                                await self.br.ws_send("channel", id=self.socketid, type="putStone", body={"pos":pos})
                elif type_ == "enemycantput":
                    # 相手が打てないとき
                    # 処理が速すぎてたまにバグるのでちょっと待つ
                    await asyncio.sleep(1)

                    if self.RV < 2:
                        # V1
                        pts = self.search_point()
                    elif self.RV < 3:
                        # V2
                        pts = self.search_point_v2()
                    elif self.RV < 4:
                        ... # V3
                    if len(pts) != 0:
                        if self.llotheo:
                            mpts = [i for i in pts if i[0] == min(pts, key=lambda x:x[0])[0]]
                        else:
                            mpts = [i for i in pts if i[0] == max(pts, key=lambda x:x[0])[0]]
                        pt = mpts[random.randint(0, len(mpts)-1)]
                        self.set_point(pos := self.postoyx(pt[1], rev=True))
                        await self.br.ws_send("channel", id=self.socketid, type="putStone", body={"pos":pos})
                        # 相手が打てないときの処理を忘れていた
                        pt = self.search_point(True)
                        if len(pt) == 0:
                            if self.check_valid_koma() != 0:
                                await self.interface({"type":"enemycantput"})
                else:
                    print(info)

        def create_banmen(self, map):
            """盤面作成関数"""
            # 1を自分、2を相手とする
            self.banmen = []
            for i, v in enumerate(map):
                self.banmen.append([])
                for r in list(v):
                    if r == "-":
                        # 空白
                        self.banmen[i].append(0)
                    elif r == "b":
                        # 黒
                        self.banmen[i].append(1 if self.colour else 2)
                    elif r == "w":
                        # 白
                        self.banmen[i].append(2 if self.colour else 1)
                    else:
                        # 壁
                        self.banmen[i].append(3)

        def search_point_v2(self) -> list[tuple[int, tuple[int, int]]]:
            """駒探す関数v2 一手読む"""
            # 最初の盤面保存
            fbeforebanmen = [[i for i in r] for r in self.banmen]
            points = []
            for first, yx in self.search_point():
                # まずは置く
                self.set_point(self.postoyx(yx, rev=True))
                # 辺、あるいは角にあるか調べる
                if (fs := self.check_side(yx)) == 2:
                    # 角にある
                    first += 120
                elif self.check_sumi(yx):
                    # 危ない場所(隅)にある
                    first -= 60
                elif fs == 1:
                    # 辺にある
                    first += 15
                # 置いた場所を保存
                tbeforebanmen = [[i for i in r] for r in self.banmen]
                if len(enemycanput := self.search_point(True)) != 0:
                    # 敵が置ける場所がある場合
                    epts = sum(map(lambda x:x[0], enemycanput))//2
                    # 辺、あるいは角に置けるか調べる
                    if any((self.check_side(i[1]) == 2) for i in enemycanput):
                        # 角に置けてしまうとき
                        epts += 120
                    elif any((self.check_side(i[1]) == 1) for i in enemycanput):
                        # 辺に置けてしまうとき
                        epts += 15
                else:
                    # 敵がどこにも置けない(Zero divisionになるので回避)
                    if len(self.search_point()) == 0:
                        # 自分の番が回ってこない=終了なのでここに置けば勝てる
                        points.append((2147483647, yx))
                        break
                    epts = 0
                # 自分が置いた時のポイントのリスト
                cpts = []
                for _, yx2 in enemycanput:
                    # 敵の攻撃を置く
                    self.set_point(self.postoyx(yx2, True), True)
                    if len(mecanput := self.search_point()):
                        # 一手後における場所があるとき
                        cs = (sum(map(lambda x:x[0], mecanput))/len(mecanput))
                        if any(self.check_side(i[1]) == 2 for i in mecanput):
                            # 角における
                            cs += 120
                        elif any(self.check_side(i[1]) == 1 for i in mecanput):
                            # 辺における
                            cs += 15
                        cpts.append(cs)
                    else:
                        cpts.append(0)
                    # 盤面を一個戻す
                    self.banmen = [[i for i in r] for r in tbeforebanmen]
                if len(cpts) != 0:
                    # 一手以上置ける場合
                    points.append((first-epts+(sum(cpts)/len(cpts)), yx))
                else:
                    # 一手も置けない場合(Zero division対策)
                    points.append((first-epts, yx))
                # 盤面を初期化
                self.banmen = [[i for i in r] for r in fbeforebanmen]
            return points

        def search_point(self, rev:bool=False) -> list[tuple[int, tuple[int, int]]]:
            """駒を置ける場所を探す関数"""
            points = []

            for y, i in enumerate(self.banmen):
                for x, r in enumerate(i):
                    # その場所が空白であるか
                    if r == 0:
                        # pointが0ではない(一つ以上取れる場合)pointsに入れる
                        if (point := len(self.point_search(y, x, rev))) != 0:
                            points.append((point, (y, x)))
            return points

        def set_point(self, pos:int, rev:bool=False):
            """駒設置関数"""
            Y, X = self.postoyx(pos)
            self.banmen[Y][X] = (2 if rev else 1)
            for y, x in self.point_search(Y, X, rev):
                self.banmen[y][x] = (2 if rev else 1)
        
        def point_search(self, y:int, x:int, rev:bool=False) -> tuple[tuple[int, int]]:
            #       上　　右上　　右　　右下　　下　　左下　　　左　　　左上
            move = ((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1))
            # 裏返せる場所のリスト
            canrev:list[tuple[int, int]] = []
            for v, s in move:
                revlist:list[tuple[int, int]] = []

                # komaが2(相手の駒)だったらrevlistにぶち込む
                # komaが1だったらrevlistに基づき裏返す
                # revがTrueだと逆(相手の攻勢)
                try:
                    n = 1
                    while True:
                        if (Y := y+v*n)<0 or (X := x+s*n)<0:
                            break

                        if (koma := self.banmen[Y][X]) == (2 if rev else 1):
                            canrev += revlist
                            break
                        elif koma == (1 if rev else 2):
                            revlist.append((Y, X))
                            n += 1
                        else:
                            break
                except IndexError:
                    pass
            
            return canrev

        def check_side(self, yx:tuple[int, int]) -> int:
            """2で角、1で辺、0でなんもなし"""
            #       上　　  右上　　右　 右下　　下　   左下　　左　　　左上
            sides = ((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1))
            iswall:list[bool] = []
            # 壁があるかを検索
            for i in sides:
                try:
                    if yx[0]+i[0]<0 or yx[1]+i[1]<0:
                        iswall.append(True)
                    elif self.banmen[yx[0]+i[0]][yx[1]+i[1]] == 3:
                        iswall.append(True)
                    else:
                        iswall.append(False)
                except IndexError:
                    iswall.append(True)
            # その場所から対照的に見て
            # 壁が対照的にあるか
            checkandlist = [(iswall[i] and iswall[i+4]) for i in range(4)]
            # 壁が対照的にないか
            rcheckandlist = [(not iswall[i] and not iswall[i+4]) for i in range(4)]
            # 対照的か(一方が壁ならもう一方も壁なのか、逆もしかり)
            checkislist = [(iswall[i] is iswall[i+4]) for i in range(4)]

            # 角の判別
            for i, v in enumerate(checkandlist):
                if v:
                    islist = checkislist.copy()
                    islist.pop(i)
                    if all(islist):
                        return 2

            # 辺の判別
            for i, v in enumerate(rcheckandlist):
                if v:
                    islist = checkislist.copy()
                    islist.pop(i)
                    if all(islist):
                        return 1

            # 角でも辺でもない、つまりなんもなし。
            return 0

        def check_sumi(self, yx:tuple[int, int]) -> bool:
            """隅(隣が角)にあるか確認する奴"""
            #       上　　  右上　　右　 右下　　下　   左下　　左　　　左上
            sides = ((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1))

            for i in sides:
                if self.check_side((yx[0]+i[0], yx[1]+i[1])) == 2:
                    return True
            else:
                return False

        def check_valid_koma(self) -> int:
            num = 0
            for i in self.banmen:
                num += i.count(0)
            return num

        def postoyx(self, pos, rev:bool=False):
            """pos to yx.
            
            if rev, yx to pos."""
            yoko = len(self.banmen[0])
            if rev:
                return yoko*pos[0] + pos[1]
            return pos//yoko, pos%yoko

        async def disconnect(self):
            # プレイ中のプレイヤーのリストからuseridを削除
            self.playing_user_list.remove(self.enemyid)

            self.br.on_comebacker(self.socketid, rev=True)
            await self.br.ws_send("disconnect", id_=str(self.socketid))

def textworkput(text):
    filepath = os.path.abspath(os.path.join(os.path.dirname(__file__),f'./{BOT_LOG_FILE}'))
    with open(filepath,"a") as f:
        f.write(text+"\n")

textworkput("bot start at {}".format(datetime.now().strftime("%Y/%m/%d %H:%M:%S")))
print("start")
try:
    br = bromine35()
    asyncio.run(br.main())
except KeyboardInterrupt as e:
    print("break!!!")
    if len(e.args) == 0:
        if not TESTMODE:
            asyncio.run(br.create_note("botとまります:blob_hello:"))
else:
    if not TESTMODE:
        asyncio.run(br.create_note("bot異常終了します:ablobcatcryingcute:\n@iodine53 異常終了したから調査しろ:blobhai:"))
finally:
    if not TESTMODE:
        asyncio.run(br.create_reaction("9iisgwj3rf", "❌", Instant=True))
        textworkput("bot stop at {}".format(datetime.now().strftime("%Y/%m/%d %H:%M:%S")))
from misskey import Misskey
import requests
import websockets
import json
import asyncio
import uuid
import random
import os
import logging

class bromine35:

    class Explosion(Exception):
        pass

    def __init__(self, instance, token, testmode:bool=False) -> None:
        self.TESTMODE = testmode
        self.logpath = "botlog.txt"
        self.V = 1.1
        # データ構造
        # uuid4 : (接続するチャンネル, 受け取り関数(async), params)
        # dict(uuid4 : tuple(channel, coroutinefunc, params))
        self._channels = {}
        self._pendings = []
        self._on_comeback = {}
        self._ws_add_list = []

        self.INSTANCE = instance
        self.TOKEN = token
        self.mk = Misskey(self.INSTANCE, i=self.TOKEN)
        self.WS_URL = f'wss://{self.INSTANCE}/streaming?i={self.TOKEN}'
        self.MY_USER_ID = self.mk.i()["id"]

        self.explosion = False

        # logger作成
        logformat = "%(levelname)-9s %(asctime)s [%(funcName)s] %(message)a"
        level = logging.INFO
        
        logging.basicConfig(format=logformat,
                            filename=os.path.abspath(os.path.join(os.path.dirname(__file__),f'./{self.logpath}')),
                            encoding="utf-8",
                            level=level)

        self.logger = logging.getLogger("bromine35bot")

    async def main(self):
        self.logger.info("bot start")
        # send_queueをinitで作るとattached to a different loopとかいうゴミでるのでここで宣言
        self._send_queue = asyncio.Queue()
        other = asyncio.gather(*(i() for i in self._pendings), return_exceptions=True)
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
            self.logger.info("bot stop")

    async def connect_check(self):
        while True:
            try:
                async with websockets.connect(self.WS_URL):
                    pass
                self.logger.info("connect check success")
            except asyncio.exceptions.TimeoutError:
                self.logger.warning("websocket timeout")
                await asyncio.sleep(30)
            except websockets.exceptions.WebSocketException as e:
                print(f"websocket error: {e}")
                self.logger.warning(f"websocket error:{e}")
                await asyncio.sleep(40)
            except Exception as e:
                print(f"yoteigai error:{e}")
                self.logger.critical(f"yoteigai error:{e}")
                await asyncio.sleep(60)
            else:
                break
        await asyncio.sleep(2)

    async def runner(self):
        # このwsdは最初に接続失敗すると未定義になるから保険のため
        wsd = None
        while True:
            try:
                async with websockets.connect(self.WS_URL) as ws:
                    wsd = asyncio.create_task(self.ws_send_d(ws))
                    for i in self._on_comeback.values():
                        await i()
                    self.logger.info("websocket connect success")
                    while True:
                        data = json.loads(await ws.recv())
                        if self.explosion:
                            raise self.Explosion("BOOM!!!!!!")
                        if data['type'] == 'channel':
                            for i, v in self._channels.items():
                                if data["body"]["id"] == i:
                                    asyncio.create_task(v[1](data["body"]))
                                    break
                            else:
                                self.logger.warning("data come from unknown channel")
                        else:
                            self.logger.warning(f"data come from not channel:type[{data['type']}]")

            except (websockets.exceptions.WebSocketException, asyncio.exceptions.TimeoutError) as e:
                self.logger.warning(f"error occured:{e}")
                await asyncio.sleep(2)
                await self.connect_check()
                continue

            except Exception as e:
                self.logger.fatal(f"fatal Error:{e}, args:{e.args}")
                raise e
            
            finally:
                if type(wsd) == asyncio.Task:
                    wsd.cancel()
                    try:
                        await wsd
                    except asyncio.CancelledError:
                        pass

    def on_comebacker(self, id_:str=None, func=None, rev:bool=False):
        """comebackを作る
        
        delの時はfuncいらない"""
        if id_ is None:
            id_ = uuid.uuid4()
        if rev:
            del self._on_comeback[id_]
        else:
            if not asyncio.iscoroutinefunction(func):
                raise ValueError("与える関数はコルーチンでなければなりません")
            self._on_comeback[id_] = func
        return id_

    def add_pending(self, func):
        if not asyncio.iscoroutinefunction(func):
            raise ValueError("func_がコルーチンじゃないです。")
        self._pendings.append(func)

    async def ws_send_d(self, ws:websockets.WebSocketClientProtocol):
        __PRIORITY_TYPES = ("connect", "disconnect")
        for i, v in self._channels.items():
            await ws.send(json.dumps({        
            "type": "connect",
            "body": {
                "channel": v[0],
                "id": i,
                "params": v[2]
            }
            }))
        # queueの中身の初期化兼disconnect等を処理
        while not self._send_queue.empty():
            getter = await self._send_queue.get()
            if any(getter[0] is i for i in __PRIORITY_TYPES):
                await ws.send(json.dumps({        
                "type": getter[0],
                "body": getter[1]
                }))
                if self.TESTMODE:
                    self.logger.info(f"websocket putted:{getter}")
        while True:
            # 型:tuple(type:str, body:dict)
            getter = await self._send_queue.get()
            await ws.send(json.dumps({        
            "type": getter[0],
            "body": getter[1]
            }))
            if self.TESTMODE:
                self.logger.info(f"websocket putted:{getter}")

    def ws_send(self, type_:str, body:dict) -> None:
        """ウェブソケットへsendするdaemonのqueueに送る奴"""
        self._send_queue.put_nowait((type_, body))

    def ws_connect(self, channel:str, func_, id_:str=None, **params) -> str:
        """channelに接続するときに使う関数 idを返す"""
        if not asyncio.iscoroutinefunction(func_):
            raise ValueError("func_がコルーチンじゃないです。")
        if id_ is None:
            id_ = str(uuid.uuid4())
        self._channels[id_] = (channel, func_, params)
        body = {
            "channel" : channel,
            "id" : id_,
            "params" : params
        }
        self.ws_send("connect", body)
        return id_

    def ws_disconnect(self, id_:str) -> None:
        """channelの接続解除に使う関数"""
        self._channels.pop(id_)
        body = {"id":id_}
        self.ws_send("disconnect", body)

    def add_ws_connect(self, channel:str, func_, id_:str=None, **params) -> str:
        """mainを実行する前に入れる場合に使う"""
        if not asyncio.iscoroutinefunction(func_):
            raise ValueError("func_がコルーチンじゃないです。")
        if id_ is None:
            id_ = str(uuid.uuid4())
        self._channels[id_] = (channel, func_, params)
        return id_

    async def api_post(self, endp:str, wttime:int, **dicts) -> requests.Response:
        url = f"https://{self.INSTANCE}/api/"+endp
        dicts["i"] = self.TOKEN
        return await asyncio.to_thread(requests.post, url, json=dicts, timeout=wttime)

    async def create_reaction(self, id, reaction, Instant=False):
        if not Instant:
            await asyncio.sleep(random.randint(3,5))
        try:
            await asyncio.to_thread(self.mk.notes_reactions_create, id, reaction)
            self.logger.info(f"create reaction success:{reaction}")
        except Exception as e:
            self.logger.info(f"create reaction fail:{e}")

    async def create_follow(self, id):
        try:
            await asyncio.to_thread(self.mk.following_create, id)
            self.logger.info("follow create success")
        except Exception as e:
            self.logger.info(f"follow create fail:{e}")

    async def create_note(self, text, cw=None, direct=None, reply=None):
        if direct == None:
            notevisible = "public"
        else:
            notevisible = "specified"
        try:
            await asyncio.to_thread(self.mk.notes_create, text, cw=cw,visibility=notevisible,visible_user_ids=direct,reply_id=reply)
            self.logger.info("note create success")
        except Exception as e:
            self.logger.info(f"note create fail:{e}")
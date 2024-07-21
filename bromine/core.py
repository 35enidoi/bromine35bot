import json
import asyncio
import uuid
import random
import logging
from functools import partial
from typing import Any, Awaitable, Callable, NoReturn, Optional, Union

from misskey import Misskey
import requests
import websockets


class Bromine:
    def __init__(self, instance: str, token: str, *, loglevel: int = logging.DEBUG, cooltime: int = 5) -> None:
        """bromineのcore
        instance: 接続するインスタンス
        token: トークン
        loglevel: loggingのlogのレベル
        cooltime: 接続に失敗したときに待つ時間"""
        # ヴァージョン
        # これいる？
        self.V = 1.1

        # uuid:[channelname, awaitablefunc, params]
        self._channels: dict[str, tuple[str, Callable[[dict[str, Any]], Awaitable[None]], dict[str, Any]]] = {}
        # list[awaitablefunc]
        self._pendings: list[Callable[[None], Awaitable[NoReturn]]] = []
        # uuid:tuple[isblock, awaitablefunc]
        self._on_comeback: dict[str, tuple[bool, Callable[[], Awaitable[None]]]] = {}

        # 値の保存
        self.INSTANCE = instance
        self.TOKEN = token
        self.COOL_TIME = cooltime

        # URL作ったり
        self.mk = Misskey(self.INSTANCE, i=self.TOKEN)  # 削除予定
        self.WS_URL = f'wss://{self.INSTANCE}/streaming?i={self.TOKEN}'

        # logger作成
        self.__logger = logging.getLogger("bromine35bot")

        # logを簡単にできるよう部分適用する
        self.log = partial(self.__logger.log, level=loglevel)

    async def main(self) -> None:
        """開始する関数"""
        self.log(msg="start main.")
        # send_queueをinitで作るとattached to a different loopとかいうゴミでるのでここで宣言
        self._send_queue = asyncio.Queue()
        other = asyncio.gather(*(i() for i in self._pendings), return_exceptions=True)
        try:
            await asyncio.create_task(self._runner())
        finally:
            other.cancel()
            try:
                await other
            except asyncio.exceptions.CancelledError:
                print("catch")
            self.log(msg="finish main.")

    async def _runner(self) -> NoReturn:
        """websocketとの交信を行うメインdaemon"""
        # 何回連続で接続に失敗したかのカウンター
        connect_fail_count = 0
        # この変数たちは最初に接続失敗すると未定義になるから保険のため
        # websocket_daemon(_ws_send_d)
        wsd: Union[None, asyncio.Task] = None
        # comebacks(asyncio.gather)
        comebacks: Union[None, asyncio.Future] = None
        while True:
            try:
                async with websockets.connect(self.WS_URL) as ws:
                    # 送るdaemonの作成
                    wsd = asyncio.create_task(self._ws_send_d(ws))

                    # comebacksの処理
                    _cmbs: list[Awaitable[None]] = []
                    for i in self._on_comeback.values():
                        if i[0]:
                            # もしブロックしなければいけないcomebackなら待つ
                            await i[1]()
                        else:
                            # でなければ後で処理する
                            _cmbs.append(i[1]())
                    if _cmbs != []:
                        # 全部一気にgatherで管理
                        comebacks = asyncio.gather(*_cmbs, return_exceptions=True)

                    self.log(msg="websocket connect success")
                    # 接続に成功したということでfail_countを0に
                    connect_fail_count = 0
                    while True:
                        # データ受け取り
                        data = json.loads(await ws.recv())
                        if data['type'] == 'channel':
                            for i, v in self._channels.items():
                                if data["body"]["id"] == i:
                                    asyncio.create_task(v[1](data["body"]))
                                    break
                            else:
                                self.log(msg="data come from unknown channel")
                        else:
                            # たまにchannel以外から来ることがある（謎）
                            self.log(msg=f"data come from not channel, datatype[{data['type']}]")

            except (
                asyncio.exceptions.TimeoutError,
                websockets.exceptions.ConnectionClosed,
                websockets.exceptions.ConnectionClosedError,
                websockets.exceptions.ConnectionClosedOK,
            ) as e:
                # websocketが死んだりタイムアウトした時の処理
                self.log(msg=f"error occured:{e}")
                connect_fail_count += 1
                await asyncio.sleep(self.COOL_TIME)
                if connect_fail_count > 5:
                    # Todo: 例外を投げる？
                    # 5回以上連続で失敗したとき長く寝るようにする
                    # とりあえず30待つようにする
                    await asyncio.sleep(30)

            except Exception as e:
                # 予定外のエラー発生時。
                self.log(msg=f"fatal Error:{type(e)}, args:{e.args}")
                raise e

            finally:
                # 再接続する際、いろいろ初期化する
                if type(wsd) is asyncio.Task:
                    # _ws_send_dを止める
                    wsd.cancel()
                    try:
                        await wsd
                    except asyncio.CancelledError:
                        pass
                    wsd = None
                if comebacks is not None:
                    # ブロックしないcomebacksがもし生きていたら殺す
                    comebacks.cancel()
                    try:
                        await comebacks
                    except asyncio.CancelledError:
                        pass
                    comebacks = None

    def add_comeback(self, func: Callable[[], Awaitable[None]], id_: Optional[str] = None, block: bool = False) -> str:
        """comebackを作る"""
        if id_ is None:
            id_ = uuid.uuid4()
        if not asyncio.iscoroutinefunction(func):
            raise ValueError("関数がコルーチンでなければなりません。")
        self._on_comeback[id_] = (block, func)
        return id_

    def del_comeback(self, id_: str) -> None:
        """comeback消す"""
        self._on_comeback.pop(id_)

    # 削除予定
    # -----------------------------------
    def add_pending(self, func: Callable[[], Awaitable[NoReturn]]) -> None:
        if not asyncio.iscoroutinefunction(func):
            raise ValueError("func_がコルーチンじゃないです。")
        self._pendings.append(func)
    # -----------------------------------

    async def _ws_send_d(self, ws: websockets.WebSocketClientProtocol) -> NoReturn:
        """websocketを送るdaemon"""
        __PRIORITY_TYPES = ("connect", "disconnect")
        # まずはchannelsの再接続から始める
        for i, v in self._channels.items():
            await ws.send(json.dumps({
                "type": "connect",
                "body": {
                    "channel": v[0],
                    "id": i,
                    "params": v[2]
                }
            }))

        # ここの処理ちょっと怪しい
        # この処理必要？(中身の初期化はいるけど...)
        # -----------------------------------
        # queueの中身の初期化兼disconnect等を処理
        while not self._send_queue.empty():
            getter = await self._send_queue.get()
            if any(getter[0] is i for i in __PRIORITY_TYPES):
                await ws.send(json.dumps({
                    "type": getter[0],
                    "body": getter[1]
                }))
        # -----------------------------------

        # あとはずっとqueueからgetしてそれを送る。
        while True:
            # 型:tuple(type:str, body:dict)
            getter = await self._send_queue.get()
            await ws.send(json.dumps({
                "type": getter[0],
                "body": getter[1]
            }))

    def ws_send(self, type_: str, body: dict) -> None:
        """ウェブソケットへsendするdaemonのqueueに送る奴"""
        self._send_queue.put_nowait((type_, body))

    def ws_connect(self,
                   channel: str,
                   func_: Callable[[dict[str, Any]], Awaitable[None]],
                   id_: Optional[str] = None,
                   **params) -> str:
        """channelに接続するときに使う関数 idを返す"""
        if not asyncio.iscoroutinefunction(func_):
            raise ValueError("func_がコルーチンじゃないです。")
        if id_ is None:
            id_ = str(uuid.uuid4())
        self._channels[id_] = (channel, func_, params)
        body = {
            "channel": channel,
            "id": id_,
            "params": params
        }
        if "_send_queue" in self.__dict__:
            self.ws_send("connect", body)
        self.log(msg=f"connect channel:{channel}, id:{id_}")
        return id_

    def ws_disconnect(self, id_: str) -> None:
        """channelの接続解除に使う関数"""
        channel = self._channels.pop(id_)[0]
        body = {"id": id_}
        self.ws_send("disconnect", body)
        self.log(msg=f"disconnect channel:{channel}, id:{id_}")

# -------------------
# -ここから下削除予定-
# -------------------

    async def api_post(self, endp: str, wttime: int, **dicts) -> requests.Response:
        url = f"https://{self.INSTANCE}/api/"+endp
        dicts["i"] = self.TOKEN
        return await asyncio.to_thread(requests.post, url, json=dicts, timeout=wttime)

    def safe_wrap(self, func_: Callable, *arg, **kargs):
        try:
            ret = func_(*arg, **kargs)
            self.log(msg=f"call {func_.__name__} success.")
            return ret
        except Exception:
            self.log(msg=f"call {func_.__name__} fail.")
            return None

    def safe_wrap_retbool(self, func_: Callable, *arg, **kargs):
        try:
            _ = func_(*arg, **kargs)
            self.log(msg=f"call {func_.__name__} success.")
            return True
        except Exception:
            self.log(msg=f"call {func_.__name__} fail.")
            return False

    async def create_reaction(self, id, reaction, Instant=False):
        if not Instant:
            await asyncio.sleep(random.randint(3, 5))
        try:
            await asyncio.to_thread(self.mk.notes_reactions_create, id, reaction)
            self.log(msg=f"create reaction success:{reaction}")
        except Exception as e:
            self.log(msg=f"create reaction fail:{e}")

    async def create_follow(self, id):
        try:
            await asyncio.to_thread(self.mk.following_create, id)
            self.log(msg="follow create success")
        except Exception as e:
            self.log(msg=f"follow create fail:{e}")

    async def create_note(self, text, cw=None, direct=None, reply=None):
        if direct is None:
            notevisible = "public"
        else:
            notevisible = "specified"
        try:
            await asyncio.to_thread(self.mk.notes_create,
                                    text,
                                    cw=cw,
                                    visibility=notevisible,
                                    visible_user_ids=direct,
                                    reply_id=reply)
            self.log(msg="note create success")
        except Exception as e:
            self.log(msg=f"note create fail:{e}")

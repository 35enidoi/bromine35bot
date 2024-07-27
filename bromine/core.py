import json
import asyncio
import uuid
import logging
from functools import partial
from typing import Any, Callable, NoReturn, Optional, Union, Coroutine

import websockets


class Bromine:
    def __init__(self, instance: str, token: str, *, cooltime: int = 5) -> None:
        """bromineのcore
        instance: 接続するインスタンス
        token: トークン
        loglevel: loggingのlogのレベル
        cooltime: 接続に失敗したときに待つ時間"""
        # uuid:[channelname, awaitablefunc, params]
        self._channels: dict[str, tuple[str, Callable[[dict[str, Any]], Coroutine[Any, Any, None]], dict[str, Any]]] = {}
        # uuid:tuple[isblock, awaitablefunc]
        self._on_comeback: dict[str, tuple[bool, Callable[[], Coroutine[Any, Any, None]]]] = {}

        # send_queueはここで作るとエラーが出るので型ヒントのみ
        self._send_queue: asyncio.Queue[tuple[str, dict]]

        # 値の保存
        self.COOL_TIME = cooltime

        self.WS_URL = f'wss://{instance}/streaming?i={token}'

        # logger作成
        self.__logger = logging.getLogger("Bromine")

        # logを簡単にできるよう部分適用する
        self.__log = partial(self.__logger.log, logging.DEBUG)

    @property
    def loglevel(self) -> int:
        """現在のログレベル"""
        return self.__log.args[0]

    @loglevel.setter
    def loglevel(self, level: int) -> None:
        self.__log = partial(self.__logger.log, level)

    async def main(self) -> NoReturn:
        """開始する関数"""
        self.__log("start main.")
        # send_queueをinitで作るとattached to a different loopとかいうゴミでるのでここで宣言
        self._send_queue = asyncio.Queue()
        try:
            await asyncio.create_task(self._runner())
        finally:
            self.__log("finish main.")

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
                    # ちゃんと通ってるかpingで確認
                    ping_wait = await ws.ping()
                    pong_latency = await ping_wait
                    self.__log(f"websocket connect success. latency: {pong_latency}s")

                    # 送るdaemonの作成
                    wsd = asyncio.create_task(self._ws_send_d(ws))

                    # comebacksの処理
                    _cmbs: list[Coroutine[Any, Any, None]] = []
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
                                self.__log("data come from unknown channel")
                        else:
                            # たまにchannel以外から来ることがある（謎）
                            self.__log(f"data come from not channel, datatype[{data['type']}]")

            except (
                asyncio.exceptions.TimeoutError,
                websockets.exceptions.ConnectionClosed,
                websockets.exceptions.ConnectionClosedError,
                websockets.exceptions.ConnectionClosedOK,
            ) as e:
                # websocketが死んだりタイムアウトした時の処理
                self.__log(f"error occured:{e}")
                connect_fail_count += 1
                await asyncio.sleep(self.COOL_TIME)
                if connect_fail_count > 5:
                    # Todo: 例外を投げる？
                    # 5回以上連続で失敗したとき長く寝るようにする
                    # とりあえず30待つようにする
                    await asyncio.sleep(30)

            except Exception as e:
                # 予定外のエラー発生時。
                self.__log(f"fatal Error:{type(e)}, args:{e.args}")
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

    def add_comeback(self,
                     func: Callable[[], Coroutine[Any, Any, None]],
                     id_: Optional[str] = None,
                     block: bool = False) -> str:
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

    async def _ws_send_d(self, ws: websockets.WebSocketClientProtocol) -> NoReturn:
        """websocketを送るdaemon"""
        # すでに接続済みのchannelにconnectしたりしないようにするやつ
        already_connected_ids: set[str] = set()
        # まずはchannelsの再接続から始める
        for i, v in self._channels.items():
            already_connected_ids.add(i)
            await ws.send(json.dumps({
                "type": "connect",
                "body": {
                    "channel": v[0],
                    "id": i,
                    "params": v[2]
                }
            }))

        # くえうえの初期化
        while not self._send_queue.empty():
            type_, body_ = await self._send_queue.get()
            if type_ == "connect":
                if body_["id"] in already_connected_ids:
                    # もうすでに送ったやつなので送らない
                    continue
                else:
                    # 追加する
                    already_connected_ids.add(body_["id"])

            await ws.send(json.dumps({
                "type": type_,
                "body": body_
            }))

        # あとはずっとqueueからgetしてそれを送る。
        while True:
            # 型:tuple(type:str, body:dict)
            type_, body_ = await self._send_queue.get()
            await ws.send(json.dumps({
                "type": type_,
                "body": body_
            }))

    def ws_send(self, type_: str, body: dict) -> None:
        """ウェブソケットへsendするdaemonのqueueに送る奴"""
        self._send_queue.put_nowait((type_, body))

    def ws_connect(self,
                   channel: str,
                   func_: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
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
            self.__log(f"connect channel before run: {channel}, id: {id_}")
        else:
            self.__log(f"connect channel: {channel}, id: {id_}")
        return id_

    def ws_disconnect(self, id_: str) -> None:
        """channelの接続解除に使う関数"""
        channel = self._channels.pop(id_)[0]
        body = {"id": id_}
        self.ws_send("disconnect", body)
        self.__log(f"disconnect channel: {channel}, id: {id_}")

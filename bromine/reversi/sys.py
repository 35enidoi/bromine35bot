from random import randint
import asyncio

from .core import reversi_core


class reversi_sys(reversi_core):

    # ゲームのダブりを防ぐためのリスト
    playing_user_list = []

    def __init__(self, brm, content: dict, socketid: str) -> None:
        """Reversi system init"""
        # testmodeの保存
        self.TESTMODE = brm.TESTMODE
        # reversi version
        self.RV = reversi_core.RC_VERSION
        # useridの保存
        self.MY_USER_ID = brm.MY_USER_ID
        # bromineの保存
        self.br = brm.br
        # id保存
        self.game_id = content["id"]
        self.socketid = socketid

        # ゲーム設定
        # ループボードの時はめんどいのでokの値をFalseにして承認しない
        self.ok: bool = True

        # user1であるかどうか
        self.user1: bool = content["user1Id"] == self.MY_USER_ID
        self.enemyid: str = content[f"user{2 if self.user1 else 1}Id"]
        self.colour: bool

        self.llotheo: bool = False
        self.put_everywhere: bool = False
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
        # self.br.ws_send("channel", {id:self.socketid, type:"init-form", body:form})

        # テストモードならリバーシシステムが準備完了なことを言う
        if self.TESTMODE:
            print("reversi system on ready", f"gameid:{self.game_id}")

    async def comeback(self):
        """カムバック時に実行される関数"""
        # まずはゲームの情報を手に入れる
        res = await self.br.api_post("reversi/show-game", 30, gameId=self.game_id)
        if res.status_code == 200:
            ds = res.json()
            if ds["isEnded"]:
                # もう終わってた時
                await self.disconnect()
            else:
                if ds["isStarted"]:
                    # 終わってなくて始まっている＝有効なゲームである

                    # 最後の一手前までの盤面作成
                    self.create_banmen(ds["map"])
                    for i in ds["logs"][:-1]:
                        self.set_point(i[3], rev=(bool(i[1]) != self.colour))

                    if bool((last := ds["logs"][-1])[1]) != self.colour:
                        # 最後の手が相手の場合、つまり今自分のターン。
                        # 処理書くのがめんどいのでinterfaceに流す
                        await self.interface({"type": "log", "body": {"player": (not self.colour), "pos": last[3]}})
                    else:
                        # 最後の手が自分、つまり相手のターンなのでそのまま再現
                        self.set_point(last[3])

    async def interface(self, info):
        """ここにウェブソケットをつなげる"""
        # else以外は準備段階に送られてくる物
        if (type_ := info["type"]) == "canceled":
            # キャンセルされたとき
            await self.disconnect()
        elif type_ == "updateSettings":
            # 対戦相手がオセロの設定変えたら来る奴
            body = info["body"]
            if (key := body["key"]) == "isLlotheo":
                # ロセオモード
                self.llotheo = body["value"]
            elif key == "loopedBoard":
                # ループボード
                # coreがループボード未対応なのでもしオンにされたら対戦できなくさせてる
                self.ok = not body["value"]
            elif key == "canPutEverywhere":
                # どこでも置けるモード
                self.put_everywhere = body["value"]
        elif type_ == "changeReadyStates":
            # 準備が整った合図
            if info["body"][f"user{1 if self.user1 else 2}"] is self.ok:
                # 自分がself.okか
                pass
            else:
                # 自分がself.okじゃない
                if info["body"][f"user{2 if self.user1 else 1}"]:
                    # 相手の合図の場合(分けてる理由は無限ループになるから)
                    self.br.ws_send("channel", {"id": self.socketid,
                                                "type": "ready",
                                                "body": self.ok})
        else:
            # ここからは対戦中あるいは対戦後に送られてくる
            if type_ == "ended":
                # 対戦終了時に送られる
                print("finish reversi gameid:", self.game_id)
                await self.disconnect()
                if not self.TESTMODE:
                    pass
                    # url = f"https://{self.br.INSTANCE}/reversi/g/{self.game_id} \n"
                    # enemyname = info["body"]["game"][f"user{2 if self.user1 else 1}"]["name"]
                    # if info["body"]["game"].get("winnerId"):
                    #     if info["body"]["game"]["winnerId"] == self.MY_USER_ID:
                    #         txt = "に勝ちました:nullcatchan_nope:"
                    #     else:
                    #         txt = "に負けました:oyoo:"
                    # elif info["body"]["game"].get("surrenderedUserId"):
                    #     txt = "に投了されました:thinknyan:"
                    # else:
                    #     txt = "との戦いで引き分けになりました:taisen_arigatou_gozaimasita:"
                    # await self.br.create_note(text=url+enemyname+txt)
            elif type_ == "started":
                # 対戦開始時に送られる
                print("start reversi! gameid:", self.game_id)

                # 自分の色の認識(黒はTrue、白はFalse)
                self.colour = (bool(info["body"]["game"]["black"]-1) is not self.user1)
                # coreの初期化
                self.core_set_colour(self.colour)
                self.create_banmen(info["body"]["game"]["map"])

                if self.TESTMODE:
                    print("どこでも置ける:", self.put_everywhere)
                    print("ロセオ:", self.llotheo)
                    print("色:", self.colour)
                else:
                    pass
                    # url = f"https://{self.br.INSTANCE}/reversi/g/{self.game_id} \n"
                    # enemyname = info["body"]["game"][f"user{2 if self.user1 else 1}"]["name"]
                    # txt = "と対戦を開始しました:taisen_yorosiku_onegaisimasu:"
                    # await self.br.create_note(text=url+enemyname+txt)

                if self.colour:
                    # もし自分の色が黒だった場合、先行なのでどっか置かないといけない。
                    pts = self.search_point()
                    if len(pts) != 0:
                        if self.llotheo:
                            mpts = [i for i in pts if i[0] == min(pts, key=lambda x: x[0])[0]]
                        else:
                            mpts = [i for i in pts if i[0] == max(pts, key=lambda x: x[0])[0]]
                        pt = mpts[randint(0, len(mpts)-1)]
                        self.set_point(pos := self.postoyx(pt[1], rev=True))
                        self.br.ws_send("channel", {"id": self.socketid,
                                                    "type": "putStone",
                                                    "body": {"pos": pos}})
            elif type_ == "log":
                # 石が置かれたときに来る奴
                body = info["body"]
                if not (body["player"] == self.colour):
                    # 相手の石置き情報だった場合、自分のターンになっている。

                    # まずは石を置く
                    self.set_point(body["pos"], rev=True)

                    # 置く場所の推測
                    if self.RV < 2:
                        # V1
                        pts = self.search_point()
                    elif self.RV < 3:
                        # V2
                        pts = self.search_point_v2()
                    elif self.RV < 4:
                        ...  # V3

                    if len(pts) != 0:
                        # 置ける場所が0個以上ある

                        # ロセオの場合、評価値を逆にして一番弱い手を使う。
                        if self.llotheo:
                            mpts = [i for i in pts if i[0] == min(pts, key=lambda x: x[0])[0]]
                        else:
                            mpts = [i for i in pts if i[0] == max(pts, key=lambda x: x[0])[0]]

                        # 取れる手の中からランダムに選ぶ
                        pt = mpts[randint(0, len(mpts)-1)]

                        # 内部の盤面に石を置いてから、石を置いたことをwebsocketの送る
                        self.set_point(pos := self.postoyx(pt[1], rev=True))
                        self.br.ws_send("channel", {"id": self.socketid,
                                                    "type": "putStone",
                                                    "body": {"pos": pos}})

                        # 相手が打てないときの処理
                        pt = self.search_point(True)
                        if len(pt) == 0:
                            # 相手が一個も打てない
                            if self.check_valid_koma() != 0:
                                # 盤面に空きがある
                                await self.interface({"type": "enemycantput"})
                    elif self.put_everywhere:
                        # どこにも置けるモードの時
                        # 盤面の空きと座標をリスト化
                        canput = []
                        for y, i in enumerate(self.banmen):
                            for x, r in enumerate(i):
                                if r == 0:
                                    canput.append((y, x))
                        if len(canput) != 0:
                            # 一個以上空きがある
                            self.set_point(pos := self.postoyx(canput[randint(0, len(canput)-1)], rev=True))
                            self.br.ws_send("channel", {"id": self.socketid,
                                                        "type": "putStone",
                                                        "body": {"pos": pos}})
            elif type_ == "enemycantput":
                # 相手が打てないとき
                # 処理が速すぎてたまにバグるのでちょっと待つ
                await asyncio.sleep(1)

                # 以下logの相手の時の処理と同じ(統一したいな)
                if self.RV < 2:
                    # V1
                    pts = self.search_point()
                elif self.RV < 3:
                    # V2
                    pts = self.search_point_v2()
                elif self.RV < 4:
                    ...  # V3
                if len(pts) != 0:
                    if self.llotheo:
                        mpts = [i for i in pts if i[0] == min(pts, key=lambda x: x[0])[0]]
                    else:
                        mpts = [i for i in pts if i[0] == max(pts, key=lambda x: x[0])[0]]
                    pt = mpts[randint(0, len(mpts)-1)]
                    self.set_point(pos := self.postoyx(pt[1], rev=True))
                    self.br.ws_send("channel", {"id": self.socketid,
                                                "type": "putStone",
                                                "body": {"pos": pos}})
                    pt = self.search_point(True)
                    if len(pt) == 0:
                        if self.check_valid_koma() != 0:
                            await self.interface({"type": "enemycantput"})
            else:
                # まだ知らない`送られてくるもの`があるかも...?
                print(info)

    async def disconnect(self):
        """websocketの接続を解除する関数"""
        # プレイ中のプレイヤーのリストからuseridを削除
        self.playing_user_list.remove(self.enemyid)

        # comebackから削除してチャンネルから切断する
        self.br.del_comeback(self.socketid)
        self.br.ws_disconnect(self.socketid)

class reversi_core:
    """reversi core"""
    RC_VERSION = 2
    banmen:list[list]
    colour:bool
    
    def core_set_colour(self, colour_:bool):
        """colourをsetするやつ"""
        self.colour = colour_

    def create_banmen(self, map):
        """盤面作成関数"""
        # 1を自分、2を相手とする
        banmen:list[list] = []
        for i, v in enumerate(map):
            banmen.append([])
            for r in list(v):
                if r == "-":
                    # 空白
                    banmen[i].append(0)
                elif r == "b":
                    # 黒
                    banmen[i].append(1 if self.colour else 2)
                elif r == "w":
                    # 白
                    banmen[i].append(2 if self.colour else 1)
                else:
                    # 壁
                    banmen[i].append(3)
        self.banmen = banmen

    def set_point(self, pos:int, rev:bool=False):
        """駒設置関数"""
        Y, X = self.postoyx(pos)
        self.banmen[Y][X] = (2 if rev else 1)
        for y, x in self.point_search(Y, X, rev):
            self.banmen[y][x] = (2 if rev else 1)
    
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

    def point_search(self, y:int, x:int, rev:bool=False) -> tuple[tuple[int, int]]:
        """駒を置いた時に裏返せる場所の座標のタプルを返す関数"""
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
        # CAUTION なんか挙動が変な気がする(気のせいだろうか)

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
        # 反対照的か(一方が壁ならもう一方はなにもなしなのか、逆もしかり)
        checkislist = [(iswall[i] is not iswall[i+4]) for i in range(4)]

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
        """盤面の空きを数える関数"""
        num = 0
        for i in self.banmen:
            num += i.count(0)
        return num

    def postoyx(self, pos, rev:bool=False):
        """pos to yx.
        
        if rev, yx to pos.
        
        開発環境が3.9.6なのでUnion(|)を使うのにimportが必要なので型推測書けない(importくらいさぼるな)"""
        yoko = len(self.banmen[0])
        if rev:
            return yoko*pos[0] + pos[1]
        return pos//yoko, pos%yoko
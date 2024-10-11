from typing import Literal
from statistics import mean


class ReversiCore:
    MOVE = ((1, 0),   (1, 1),  (0, 1),
            (-1, 1),           (-1, 0),
            (-1, -1), (0, -1), (1, -1))

    def __init__(self) -> None:
        self.__y: int = 0
        self.__x: int = 0
        self.__colour: bool = False

        self._valid_spaces: set[tuple[int, int]] = set()
        self._own_stones: set[tuple[int, int]] = set()
        self._enemy_stones: set[tuple[int, int]] = set()
        self._wall: set[tuple[int, int]] = set()

        self._sides: set[tuple[int, int]] = set()
        self._corners: set[tuple[int, int]] = set()
        self._sumi: set[tuple[int, int]] = set()

    @property
    def valid_spaces(self) -> set[tuple[int, int]]:
        return self._valid_spaces.copy()

    def core_set_colour(self, arg: bool) -> None:
        if isinstance(arg, bool):
            self.__colour = arg
        else:
            raise TypeError

    def create_banmen(self, map_: list[str]) -> None:
        """盤面作成関数"""
        y = len(map_)
        if y == 0:
            x = 0  # 盤面が存在しないけど一応例外として
        else:
            x = len(map_[0])

        valid_space = set()
        own_space = set()
        enemy_space = set()
        wall = set()

        if self.__colour:
            own_stone_colour = "b"
            enemy_stone_colour = "w"
        else:
            own_stone_colour = "w"
            enemy_stone_colour = "b"

        for posy, v in enumerate(map_):
            for posx, val in enumerate(v):
                if val == "-":
                    # 空白
                    valid_space.add((posy, posx))
                elif val == own_stone_colour:
                    # 自分のやつ
                    own_space.add((posy, posx))
                elif val == enemy_stone_colour:
                    # 敵のやつ
                    enemy_space.add((posy, posx))
                else:
                    # 壁
                    wall.add((posy, posx))

        self._banmen_update(y-1, x-1, valid_space, own_space, enemy_space, wall)

    def _banmen_update(self,
                       y: int,
                       x: int,
                       valid: set[tuple[int, int]],
                       own: set[tuple[int, int]],
                       enemy: set[tuple[int, int]],
                       wall: set[tuple[int, int]]) -> None:
        if y == 0 and x == 0:
            # なんもないとき変になるのを対策
            self.__y = 0
            self.__x = 0
        else:
            self.__y = y
            self.__x = x

        self._valid_spaces = valid.copy()
        self._own_stones = own.copy()
        self._enemy_stones = enemy.copy()
        self._wall = wall.copy()

        self._sides = set()
        self._corners = set()
        self._sumi: set[tuple[int, int]] = set()

        for y_, x_ in self._valid_spaces:
            side_check = self.__check_side(y_, x_)
            if side_check == 2:
                # 角
                self._corners.add((y_, x_))
            elif side_check == 1:
                # 辺
                self._sides.add((y_, x_))

        for y_, x_ in self._valid_spaces:
            if self.__check_sumi(y_, x_):
                self._sumi.add((y_, x_))

    def search_point_v2(self) -> list[tuple[int, tuple[int, int]]]:
        # 仮想リバーシ環境を作成
        rc = ReversiCore()
        rc._banmen_update(self.__y, self.__x, self._valid_spaces, self._own_stones, self._enemy_stones, self._wall)

        points: list[tuple[int, tuple[int, int]]] = []

        for value, yx in rc.search_point():
            y, x = yx
            point = 0
            rc._set_point(y, x)

            if (position := (y, x)) in rc._corners:
                # 角にあるとき
                point += 100
            elif position in rc._sumi:
                # 隅にある時(辺と被る可能性あるので先に)
                point -= 35
            elif position in rc._sides:
                # 辺にある時
                point += 15

            # 取れる数も追加しておく
            point += value

            if len(rc._enemy_stones) == 0:
                # ここに置けば勝てるということなので絶対にここに置く
                point += 99999999999

            enemypoints: list[int] = []
            for enemy_value, enemy_yx in rc.search_point(rev=True):
                enemy_y, enemy_x = enemy_yx
                enemypoint = 0
                if (enemyposition := (enemy_y, enemy_x)) in rc._corners:
                    # 相手が角におけるとき
                    enemypoint -= 100
                elif enemyposition in rc._sumi:
                    # 相手が隅におけるとき
                    enemypoint += 35
                elif enemyposition in rc._sides:
                    # 相手が辺における時
                    enemypoint -= 15

                # 同様
                enemypoint -= enemy_value

                enemypoints.append(enemypoint)

            # 合計を計算
            if len(enemypoints) != 0:
                points.append((int(point + mean(enemypoints)), position))
            else:
                points.append((point, position))

            # 初期化
            rc._banmen_update(self.__y, self.__x, self._valid_spaces, self._own_stones, self._enemy_stones, self._wall)

        return points

    def search_point(self, rev: bool = False) -> list[tuple[int, tuple[int, int]]]:
        """駒を置ける場所を探す関数"""
        points = []

        for y, x in self._valid_spaces:
            if (point := self.__point_search_num(y, x, rev)) != 0:
                points.append((point, (y, x)))

        return points

    def set_point(self, pos: int, rev: bool = False) -> None:
        self._set_point(*self.postoyx(pos), rev)

    def _set_point(self, y: int, x: int, rev: bool = False) -> None:
        if rev:
            my_stones = self._enemy_stones
            enemy_stones = self._own_stones
        else:
            my_stones = self._own_stones
            enemy_stones = self._enemy_stones

        self._valid_spaces.remove((y, x))
        my_stones.add((y, x))
        for i in self.__point_search(y, x, rev):
            my_stones.add(i)
            enemy_stones.remove(i)

    def __point_search(self, y: int, x: int, rev: bool = False) -> list[tuple[int, int]]:
        can_reverse = []
        if rev:
            my_stone = self._enemy_stones
            enemy_stone = self._own_stones
        else:
            my_stone = self._own_stones
            enemy_stone = self._enemy_stones

        for y_, x_ in self.MOVE:
            revlist: list[tuple[int, int]] = []

            n = 1
            while 0 <= (Y := y+y_*n) <= self.__y and 0 <= (X := x+x_*n) <= self.__x:
                # 盤面の範囲内にいる間

                if (position := (Y, X)) in my_stone:
                    # もしそこが自分の石だったら
                    if len(revlist) != 0:
                        # 隣の場所じゃなかったら
                        can_reverse += revlist
                    break
                elif position in enemy_stone:
                    # 相手の石だったら
                    revlist.append(position)
                    n += 1
                else:
                    # 空白とか壁とかだったら
                    break

        return can_reverse

    def __point_search_num(self, y: int, x: int, rev: bool = False) -> int:
        num = 0

        if rev:
            my_stone = self._enemy_stones
            enemy_stone = self._own_stones
        else:
            my_stone = self._own_stones
            enemy_stone = self._enemy_stones

        for y_, x_ in self.MOVE:
            n = 1
            while 0 <= (Y := y+y_*n) <= self.__y and 0 <= (X := x+x_*n) <= self.__x:
                # 盤面の範囲内にいる間
                if (position := (Y, X)) in my_stone:
                    # もしそこが自分の石だったら
                    num += n - 1
                    break
                elif position in enemy_stone:
                    # 相手の石だったら
                    n += 1
                else:
                    # 空白とか壁とかだったら
                    break

        return num

    def __check_side(self, y: int, x: int) -> Literal[0, 1, 2]:
        """2で角、1で辺、0でなんもなし"""
        # CAUTION なんか挙動が変な気がする(気のせいだろうか)

        iswall: list[bool] = []
        for y_, x_ in self.MOVE:
            iswall.append(((Y := y + y_) < 0 or Y > self.__y or (X := x + x_) < 0 or X > self.__x or (Y, X) in self._wall))

        # その場所から対照的に見て
        # 壁が対照的にあるか
        checkandlist = [(iswall[i] and iswall[i+4]) for i in range(4)]
        # 壁が対照的にないか
        rcheckandlist = [(not iswall[i] and not iswall[i+4]) for i in range(4)]
        # 反対照的か(一方が壁ならもう一方はなにもなしなのか、逆もしかり)
        checkislist = [(iswall[i] is not iswall[i+4]) for i in range(4)]

        # 角の判別
        if all(checkislist):
            return 2
        for pos, val in enumerate(checkandlist):
            if val:
                islist = checkislist.copy()
                islist.pop(pos)
                if all(islist):
                    return 2

        # 辺の判別
        for pos, val in enumerate(rcheckandlist):
            if val:
                islist = checkislist.copy()
                islist.pop(pos)
                if all(islist):
                    return 1

        # 角でも辺でもない、つまりなんもなし。
        return 0

    def __check_sumi(self, y: int, x: int) -> bool:
        for y_, x_ in self.MOVE:
            if (y + y_, x + x_) in self._corners:
                return True
        else:
            return False

    def postoyx(self, pos: int) -> tuple[int, int]:
        return pos//(self.__x + 1), pos % (self.__x + 1)

    def yxtopos(self, y: int, x: int) -> int:
        return y*(self.__x + 1) + x

    def enemycannotput(self) -> bool:
        return len(self.search_point(True)) == 0 and len(self._valid_spaces) != 0

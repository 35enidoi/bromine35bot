import os
import subprocess
import asyncio
from misskey import exceptions
from uuid import uuid4
from random import randint

import core
from reversi import reversi_sys

instance = "misskey.io"
token = os.environ["MISSKEY_BOT_TOKEN"]
HOST_USER_ID = "9gwek19h00"

br = core.bromine35(instance, token, True)

notes_queue = asyncio.Queue()

async def local_speed_watch():
    interval = 61
    while True:
        await asyncio.sleep(60*interval)
        notes = 0
        re_notes = 0
        userdetect = {}
        while not notes_queue.empty():
            notesinfo = await notes_queue.get()
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
        notetext = "ローカルの流速です:eyes_fidgeting:\n ノートの数;{}個 {}毎秒".format(notes, round(notes/(60*interval), 2))
        notetext += "\n リノートの数;{}個 {}毎秒\n インターバル;{}分".format(re_notes, round(re_notes/(60*interval), 2), interval)
        await br.create_note(notetext)

async def cpuwatch():
    while True:
        cpu_temp = []
        for _ in range(120):
            cpu_temp += await cpuwatch_short()
        print("watched cpu!\n{} {} {:.2f}".format(max(cpu_temp),min(cpu_temp),sum(cpu_temp)/len(cpu_temp)))
        await br.create_note(text="ラズパイ君の温度です！\n最大温度;{} 最小温度;{} 平均温度;{:.2f}".format(max(cpu_temp),min(cpu_temp),sum(cpu_temp)/len(cpu_temp)), direct=["9gwek19h00"])

# cpuwatchは今使ってない
br.add_pending(local_speed_watch)
# br.add_pending(cpuwatch)

async def detect_not_follow():
    try:
        followers = await asyncio.to_thread(br.mk.users_followers, user_id=br.MY_USER_ID)
        not_in = []
        for i in followers:
            if not i["follower"]["isFollowing"] and not i["follower"]["hasPendingFollowRequestFromYou"]:
                not_in.append(i["followerId"])
        for i in not_in:
            print(f"detect not follow! id:{i}")
            await br.create_follow(i)
            await asyncio.sleep(10)
    except exceptions.MisskeyAPIException as e:
        print(f"detect not follow error:{e}")
        await asyncio.sleep(10)
        asyncio.create_task(detect_not_follow)

br.on_comebacker(func=detect_not_follow)

LIST_DETECT_JYOPA = (":_zi::_lyo::_pa:","じょぱ",
                     ":_ma::_lu::_a::_wave:","まぅあ～",
                     ":zyopa_kuti_kara_daeki_to_iq_ga_ahure_deru_oto:")

async def onnote(note):
    note = note["body"]
    if note.get("text"):
        text_ = note["text"]
        if note["user"]["isBot"]:
            pass
        elif note["cw"] is not None:
            pass
        elif any(char in text_ for char in map(str, LIST_DETECT_JYOPA)):
            print(f"jyopa detect noteid;{note['id']}")
            asyncio.create_task(br.create_reaction(note["id"], ":blobcat_frustration:"))
    # ノートはlocal_speed_watchに流す
    if note.get("renoteId"):
        await notes_queue.put(("renote",note["userId"]))
    else:
        await notes_queue.put(("note",note["userId"]))

async def onnotify(note):
    print("notification coming")
    if note["type"] == "followed":
        print("follow coming")
        print(note["body"]["name"])
        asyncio.create_task(br.create_follow(note["body"]["id"]))
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
                    asyncio.create_task(cpuwatch_short(note["body"]["id"],visible))
                    return
                elif "explosion" in note["body"]["text"]:
                    print("explosion!!!")
                    await br.create_reaction(note["body"]["id"],":explosion:",Instant=True)
                    if not br.TESTMODE:
                        await br.create_note("bot、爆発します。:explosion:")
                    br.explosion = True
                    return
                elif "invite" in note["body"]["text"]:
                    print("reversi invite comming")
                    print(note["body"]["text"].split(" ")[-1])
                    res = await br.api_post("reversi/match", 30, userId=str(note["body"]["text"].split("\n")[-1]))
                    print(res.status_code)
                    asyncio.create_task(br.create_reaction(note["body"]["id"],"🆗",Instant=True))
                    return
        if note["body"]["user"]["isBot"]:
            print("mention bot detected")
            print(note["body"]["user"]["name"])
        elif "ping" in note["body"]["text"]:
            print("ping coming")
            if note["body"]["visibility"] == "specified":
                asyncio.create_task(br.create_note("bomb!:explosion:", reply=note["body"]["id"], direct=[note["body"]["userId"]]))
            else:
                asyncio.create_task(br.create_note("bomb!:explosion:", reply=note["body"]["id"]))
            asyncio.create_task(br.create_reaction(note["body"]["id"],"💣",Instant=True))
        elif "怪文書" in note["body"]["text"]:
            print("kaibunsyo coming")
            asyncio.create_task(kaibunsyo(note["body"]["id"]))
        else:
            print("mention coming")
            asyncio.create_task(br.create_reaction(note["body"]["id"],"❤️"))

async def onreversi(info):
    if info["type"] == "invited":
        if br.TESTMODE:
            print("invite!")
        if not (userid := info["body"]["user"]["id"]) in reversi_sys.playing_user_list:
            # プレイ中のuseridのリストにぶち込む
            reversi_sys.playing_user_list.append(userid)
            res = await br.api_post("reversi/match", 30, userId=userid)
            id_ = str(uuid4())
            rv = reversi_sys(br, res.json(), id_)
            br.on_comebacker(rv.socketid, rv.comeback)
            br.ws_connect("reversiGame", rv.interface, id_, gameId=rv.game_id)
            # フォームは今のところ未対応みたい

            # # フォーム送信
            # form = [{"id":i, "type":v[0], "label":v[1], "value":v[2]}for i, v in rv._form.items()]
            # br.ws_send("channel", {id:rv.socketid, type:"init-form", body:form})
    elif info["type"] == "matched":
        game = info["body"]["game"]
        if br.TESTMODE:
            print("matched!")
        if not (userid := game[f"user{2 if game['user1Id'] == br.MY_USER_ID else 1}"]["id"]) in reversi_sys.playing_user_list:
            # プレイ中のuseridのリストにぶち込む
            reversi_sys.playing_user_list.append(userid)
            id_ = str(uuid4())
            rv = reversi_sys(br, game, id_)
            br.on_comebacker(rv.socketid, rv.comeback)
            br.ws_connect("reversiGame", rv.interface, id_, gameId=rv.game_id)
    else:
        print("reversi anything comming")
        print(info)

br.ws_connect("main", onnotify)
br.ws_connect("localTimeline", onnote)
br.ws_connect("reversi", onreversi)

async def kaibunsyo(noteid):
    kaibunsyo = ""
    try:
        notes = await asyncio.to_thread(br.mk.notes_local_timeline, randint(5,15))
    except exceptions.MisskeyAPIException:
        return
    for i in notes:
        if i["cw"] is not None:
            pass
        elif i["text"] is not None:
            kaibunsyo += i["text"].replace("\n", "")[0:randint(0,len(i["text"]) if len(i["text"]) <= 15 else 15)]
    await br.create_note(kaibunsyo.replace("#", "＃").replace("@","*"),reply=noteid)

async def cpuwatch_short(reply=None, directs=None):
    cpu_temp = []
    if reply != None:
        await br.create_reaction(reply,":murakamisan_nurukopoppu_tyottotoorimasuyo2:")
    for _ in range(60):
        cpu_temp.append(float((subprocess.run("vcgencmd measure_temp", shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True).stdout.split("="))[1].replace("\n", "").replace("'C", "")))
        await asyncio.sleep(1)
    if reply != None:
        await br.create_reaction(reply,":blobcat_ok_sign:")
        await br.create_note("ラズパイ君の温度です！\n最大温度;{} 最小温度;{} 平均温度;{:.2f}".format(max(cpu_temp),min(cpu_temp),sum(cpu_temp)/len(cpu_temp)),reply=reply,direct=directs)
    else:
        return cpu_temp


async def setup():
    await br.create_note("bot、動きます。:ablobblewobble:")
    await br.create_reaction("9iisgwj3rf", "✅")

async def fin(yoteigai):
    if yoteigai:
        await br.create_note("bot異常終了します:ablobcatcryingcute:\n@iodine53 異常終了したから調査しろ:blobhai:")
    else:
        await br.create_note("botとまります:blob_hello:")
    await br.create_reaction("9iisgwj3rf", "❌", Instant=True)


def main():
    if not br.TESTMODE:
        asyncio.run(setup())
    try:
        asyncio.run(br.main())
    except (KeyboardInterrupt, br.Explosion):
        isyoteigai = False
    else:
        isyoteigai = True
    finally:
        if not br.TESTMODE:
            asyncio.run(fin(isyoteigai))

if __name__ == "__main__":
    main()
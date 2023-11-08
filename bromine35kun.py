from misskey import Misskey, exceptions
import websockets
from requests import exceptions
import json
import asyncio
from datetime import datetime
import subprocess
import random
import os

TOKEN = os.environ["MISSKEY_BOT_TOKEN"]
INSTANCE = "misskey.io"
WS_URL = f'wss://{INSTANCE}/streaming?i={TOKEN}'
HOST_USER_ID = "9gwek19h00"
BOT_LOG_FILE = "botlog.txt"

notes_queue = asyncio.Queue()

mk = Misskey("misskey.io", i=TOKEN)
MY_USER_ID = mk.i()["id"]
LIST_DETECT_JYOPA = (":_zi::_lyo::_pa:","じょぱ",":_ma::_lu::_a::_wave:","まぅあ～")

async def main():
    print("main start")
    await connect_check()
    await create_note("bot、動きます。:ablobblewobble:")
    mk.notes_reactions_create("9iisgwj3rf", "✅")
    pendings = [local_speed_watch()]
    other = asyncio.gather(*pendings, return_exceptions=True)
    try:
        await asyncio.create_task(runner(("main","localTimeline"), ("notifys","localtl")))
    except Exception:
        other.cancel()
        try:
            await other
        except asyncio.exceptions.CancelledError:
            print("catch")
        print("main finish")
        raise

async def connect_check():
    while True:
        try:
            async with websockets.connect(WS_URL):
                pass
            print("connect checked")
        except asyncio.exceptions.TimeoutError:
            print("timeout")
            await textworkput(BOT_LOG_FILE, "timeout at {}".format(datetime.now().strftime("%Y/%m/%d %H:%M:%S")))
            await asyncio.sleep(30)
        except websockets.exceptions.WebSocketException as e:
            print(f"websocket error: {e}")
            await textworkput(BOT_LOG_FILE, "websocket error;{} at {}".format(e,datetime.now().strftime("%Y/%m/%d %H:%M:%S")))
            await asyncio.sleep(40)
        except Exception as e:
            print(f"yoteigai error:{e}")
            await textworkput(BOT_LOG_FILE, "yoteigai error;{} at {}".format(e,datetime.now().strftime("%Y/%m/%d %H:%M:%S")))
            await asyncio.sleep(60)
        else:
            break
    await asyncio.sleep(2)

async def runner(channel,id):
    while True:
        try:
            asyncio.create_task(detect_not_follow())
            print("connect start")
            async with websockets.connect(WS_URL) as ws:
                for i in range(len(channel)):
                    await ws.send(json.dumps({        
                    "type": "connect",
                    "body": {
                        "channel": "{}".format(channel[i]),
                        "id": id[i]
                    }
                    }))
                print(channel,"connect")
                while True:
                    data = json.loads(await ws.recv())
                    if data['type'] == 'channel':
                        if data['body']['id'] == id[0]:
                            asyncio.create_task(onnotify(data["body"]))
                        else:
                            if data["body"]["type"] == "note":
                                asyncio.create_task(onnote(data["body"]["body"]))
        except (websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK, asyncio.exceptions.TimeoutError) as e:
            print("error occured")
            print(e)
            await textworkput(BOT_LOG_FILE,"error occured:{} at {}".format(e,datetime.now().strftime("%Y/%m/%d %H:%M:%S")))
            await asyncio.sleep(2)
            await connect_check()
            continue
        except Exception as e:
            print(e)
            print(channel)
            await textworkput(BOT_LOG_FILE,f"fatal Error; {e}")
            raise

async def onnote(note):
    if note.get("text"):
        text_ = note["text"]
        if note["user"]["isBot"]:
            pass
        elif note["cw"] is not None:
            pass
        elif any(char in text_ for char in map(str, LIST_DETECT_JYOPA)):
            print(f"jyopa detect noteid;{note['id']}")
            asyncio.create_task(create_reaction(note["id"], ":blobcat_frustration:"))
    if note.get("renoteId"):
        await notes_queue.put(("renote",note["userId"]))
    else:
        await notes_queue.put(("note",note["userId"]))

async def onnotify(note):
    print("notification coming")
    if note["type"] == "followed":
        print("follow coming")
        print(note["body"]["name"])
        asyncio.create_task(create_follow(note["body"]["id"]))
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
                    mk.notes_reactions_create(note["body"]["id"],":explosion:")
                    await create_note("bot、爆発します。:explosion:")
                    raise KeyboardInterrupt("errorrrrrrrrrrr!!!!")
        if note["body"]["user"]["isBot"]:
            print("mention bot detected")
            print(note["body"]["user"]["name"])
        elif "ping" in note["body"]["text"]:
            print("ping coming")
            if note["body"]["visibility"] == "specified":
                asyncio.create_task(create_note("bomb!:explosion:", reply=note["body"]["id"], direct=[note["body"]["userId"]]))
            else:
                asyncio.create_task(create_note("bomb!:explosion:", reply=note["body"]["id"]))
            asyncio.create_task(create_reaction(note["body"]["id"],"💣"))
        elif "怪文書" in note["body"]["text"]:
            print("kaibunsyo coming")
            asyncio.create_task(kaibunsyo(note["body"]["id"]))
        else:
            print("mention coming")
            asyncio.create_task(create_reaction(note["body"]["id"],"❤️"))

async def create_reaction(id,reaction):
    await asyncio.sleep(random.randint(3,5))
    try:
        mk.notes_reactions_create(id,reaction)
        print("create reaction",reaction)
    except Exception as e:
        print("create reaction fail")
        print(e)

async def create_follow(id):
    try:
        mk.following_create(id)
        print(f"follow create success id;{id}")
    except Exception as e:
        print(f"follow fail;{e}")

async def create_note(text,cw=None,direct=None,reply=None):
    if direct == None:
        notevisible = "public"
    else:
        notevisible = "specified"
    try:
        mk.notes_create(text,cw=cw,visibility=notevisible,visible_user_ids=direct,reply_id=reply)
        print("note create")
    except Exception as e:
        print(f"note create fail:{e}")

async def textworkput(filename,text):
    with open(filename,"a") as f:
        f.write(text+"\n")

async def cpuwatch():
    while True:
        cpu_temp = []
        for _ in range(120):
            cpu_temp += await cpuwatch_short()
        print("watched cpu!\n{} {} {:.2f}".format(max(cpu_temp),min(cpu_temp),sum(cpu_temp)/len(cpu_temp)))
        await create_note(text="ラズパイ君の温度です！\n最大温度;{} 最小温度;{} 平均温度;{:.2f}".format(max(cpu_temp),min(cpu_temp),sum(cpu_temp)/len(cpu_temp)), direct=["9gwek19h00"])

async def cpuwatch_short(reply=None, directs=None):
    cpu_temp = []
    if reply != None:
        await create_reaction(reply,":murakamisan_nurukopoppu_tyottotoorimasuyo2:")
    for _ in range(60):
        cpu_temp.append(float((subprocess.run("vcgencmd measure_temp", shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True).stdout.split("="))[1].replace("\n", "").replace("'C", "")))
        await asyncio.sleep(1)
    if reply != None:
        await create_reaction(reply,":blobcat_ok_sign:")
        await create_note("ラズパイ君の温度です！\n最大温度;{} 最小温度;{} 平均温度;{:.2f}".format(max(cpu_temp),min(cpu_temp),sum(cpu_temp)/len(cpu_temp)),reply=reply,direct=directs)
    else:
        return cpu_temp

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
        await create_note("ローカルの流速です:eyes_fidgeting:\n ノートの数;{}個 {}毎秒\n リノートの数;{}個 {}毎秒\n インターバル;{}分".format(notes, round(notes/(60*interval), 2), re_notes, round(re_notes/(60*interval), 2), interval))

async def detect_not_follow():
    try:
        followers = mk.users_followers(MY_USER_ID)
        not_in = []
        for i in followers:
            if not i["follower"]["isFollowing"]:
                not_in.append(i["followerId"])
        for i in not_in:
            print(f"detect not follow! id:{i}")
            await create_follow(i)
            await asyncio.sleep(10)
    except (exceptions.MisskeyAPIException, exceptions.ReadTimeout) as e:
        print(f"detect not follow error:{e}")
        await asyncio.sleep(10)
        asyncio.create_task(detect_not_follow)

async def kaibunsyo(noteid):
    kaibunsyo = ""
    for i in mk.notes_local_timeline(random.randint(5,15)):
        if i["cw"] is not None:
            pass
        elif i["text"] is not None:
            kaibunsyo += i["text"].replace("\n", "")[0:random.randint(0,len(i["text"]) if len(i["text"]) <= 15 else 15)]
    await create_note(kaibunsyo.replace("#", "＃").replace("@","*"),reply=noteid)

asyncio.run(textworkput(BOT_LOG_FILE,"bot start at {}".format(datetime.now().strftime("%Y/%m/%d %H:%M:%S"))))
print("start")
try:
    asyncio.run(main())
except KeyboardInterrupt as e:
    print("break!!!")
    if len(e.args) == 0:
        asyncio.run(create_note("botとまります:blob_hello:"))
except Exception:
    asyncio.run(create_note("bot異常終了します:ablobcatcryingcute:\n@iodine53 異常終了したから調査しろ:blobhai:"))
    raise
finally:
    asyncio.run(create_reaction("9iisgwj3rf","❌"))
    asyncio.run(textworkput(BOT_LOG_FILE,"bot stop at {}".format(datetime.now().strftime("%Y/%m/%d %H:%M:%S"))))
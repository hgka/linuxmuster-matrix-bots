#!/usr/bin/env python3


# Verschlüsselungsalgorithmen für Nachahmung
import hashlib, hmac
# Netzwerkanfrage bei Matrix für Nachahmung
import requests

# Datenaustausch über json und subprocess
import json
import subprocess  # see https://docs.python.org/3.6/library/subprocess.html#module-subprocess

# Konfigurationsdatei lesen
import configparser # see https://docs.python.org/3.6/library/configparser.html

# Asyncrone Bibliothek für Matrix-API
import asyncio
# Matrix-API Bibliothek
from nio import * # see https://matrix-nio.readthedocs.io/en/latest/index.html


config = configparser.ConfigParser()
config.read('config.ini')

##Enrol-Bot
bot_id = config['enrolbot']['id']
bot_passwd = config['enrolbot']['passwd']
bot_displayname = config['enrolbot']['displayname']
##Work-Bot
work_id = config['workbot']['id']
work_passwd = config['workbot']['passwd']
work_displayname = config['workbot']['displayname']
homeserver = config['homeserver']['url']
id_domain = bot_id.split(":")[1]
shared_secret = str.encode(config['impersonation']['secret'])  ## needs to be byte-data
client = AsyncClient(homeserver, bot_id)
workclient = AsyncClient(homeserver, work_id)

##Für Datenweitergabe an Workbot
class workdata:
    def __init__(self, invitee, roomid, event, events):
        self.invitee = invitee
        self.roomid = roomid
        self.event = event
        self.events = events

list = []

async def send_message(msg, roomid):
    ##Baue Nachricht aus bekommenen Parametern und schicke sie
    await client.room_send(
        room_id = roomid,
        message_type = "m.room.message",
        content={
            "msgtype": "m.text",
            "body": msg
        }
    )
async def send_work_message(msg, roomid):
    ##Baue Nachricht aus bekommenen Parametern und schicke sie
    await workclient.room_send(
        room_id = roomid,
        message_type = "m.room.message",
        content={
            "msgtype": "m.text",
            "body": msg
        }
    )

async def check_functionality():

    ## Wir brauchen sophomorix um Gruppen herauszufinden und aufzulösen
    try:
        completedprocess = subprocess.run(["sophomorix-class", "-h"], stdout=subprocess.PIPE)
    except OSError as e:
        print("Execution failed:", e, file=sys.stderr)
        logout_response = loop.run_until_complete(logout())
        raise SystemExit

    ## Wir brauchen auch Zugang zur Circles API, wenn wir die Kreise
    ## auflösen wollen
#    try:
#        completedprocess = subprocess.run("???")
#    except OSError as e:
#        print("Execution failed:", e, file=sys.stderr)
#        logout_response = loop.run_until_complete(logout())
#        raise SystemExit


async def get_impersonation_token(user_id, homeserver, shared_secret):
    login_api_url = homeserver + '/_matrix/client/r0/login'

    password = hmac.new(shared_secret, user_id.encode('utf-8'), hashlib.sha512)
    password = password.hexdigest()

    payload = {
        'type': 'm.login.password',
        'user': user_id,
        'password': password,
    }
    response = requests.post(login_api_url, data=json.dumps(payload))
    return response.json()['access_token']

async def get_lmn_classmembers(possibleclass,roomid):
    try:
        completedprocess = subprocess.run(["sophomorix-class", "-i", "-c", possibleclass, "-j"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        print("Execution failed:", e, file=sys.stderr)
        return(False, None)

    ## need to remove starting and ending of JSON
    try:
        data_in_str = ' '.join(completedprocess.stderr.decode('utf-8').split('\n')[1:-2])
        jsonstream = data_in_str.encode()
        jsondata = json.loads(jsonstream)
    except ValueError as e:
        print(e)
        print(data_in_str)
        return(False, None)
    
    ## check if the jsondata contains a total
    try:
        if 'COUNTER' not in jsondata:
            raise ValueError("No counter in JSON")
        if 'TOTAL' not in jsondata['COUNTER']:
            raise ValueError("No TOTAL in JSON-counter")
        if jsondata["COUNTER"]["TOTAL"] == 0:
            print("Total 0 in JSON: {possibleclass} - that is no class")
            #raise ValueError("Total 0 in JSON - that is no class")
            return(True, None)
    except ValueError as e:
        print(e)
        return(False, None)

    ## get the classes
    members=[]
    try:
        if 'GROUPS' not in jsondata:
            raise ValueError("No group found in JSON")

        ## get all members in all classes found
        nomembersfound=True
        for group in jsondata['GROUPS']:
            print(jsondata['GROUPS'][group])
            if 'member' in jsondata['GROUPS'][group]:
                nomembersfound=False
                print(f"Anzahl der Mitglieder der Gruppe {possibleclass}: {len(jsondata['GROUPS'][group]['member'])}")
                await send_message(f"{bot_displayname} sagt: Habe {len(jsondata['GROUPS'][group]['member'])} Mitglieder in Gruppe {possibleclass} gefunden.", roomid)
                for cn in jsondata['GROUPS'][group]['member']:
                    print(cn[3:cn[0:].find(",OU")])
                    members.append(cn[3:cn[0:].find(",OU")])
    except ValueError as e:
        print(e)
        return(False, None)

    if not nomembersfound:
        return(True, members)

    await send_message(f"{bot_displayname} sagt: Hm, habe keine Mitglieder in Gruppe {possibleclass} gefunden.", roomid)
    return(False,None)

async def call_on_invites(room, event):

    # also possible InviteAliasEvent
    if (not isinstance(event, InviteMemberEvent)):
        print(f"This is not an InviteMemberEvent! {event}")
        return

    # see: python3 >>> help(InviteMemberEvent)
    if ( event.membership != "invite" ):
        print(f"This is not an invitation! From {event.sender}: {event.membership}")
        return

    invitee = event.sender
    
    # join the room the bot is invited to
    roomid = room.room_id
    await client.join(roomid)

    # send a message about having joined
    await send_message(f"{bot_displayname} sagt: zu Diensten!", roomid)

    # examine the room
    try:
        response = (await client.room_get_state(roomid))
    except RoomGetStateError as e:
        print("Hab ein Problem: ", response, e)
        return

    
    try:
        print(response.transport_response)
        print(response.transport_response.status)
    except AttributeError:
        print("Problem: Es gibt keinen Status für diese Antwort")
        return

    if response.transport_response.status != 200:
        try:
            print(response.status_code)
        except AttributeError:
            print("Problem: Es gibt keinen status_code in der Antwort")
            return

        if response.status_code == "M_FORBIDDEN":
            await send_message(f"{bot_displayname} sagt: Ich darf in dem Raum gar nichts tun, tut mir leid! Erlaube mir, den Raum anzuschauen und lade mich erneut ein. Ich ziehe meine Einladung zurück.", roomid)
            await client.room_leave(roomid)
            return

    current_room = response

    try:
        events = current_room.events
    except AttributeError:
        await send_message(f"{bot_displayname} sagt: In diesem Raum finde ich gar keine Events!", roomid)

    ##Enrol-Bot füttert Objekt mit Daten und gibt den Auftrag an den Work-Bot weiter

    obj = workdata(invitee, roomid, event, events)
    list.append(obj)
    response = (await client.room_invite(roomid, work_id))
    if response.status_code == "M_FORBIDDEN":
        await send_message(f"{work_displayname} sagt: Bitte erlaube mir in den Einstellungen, das 'Standard'-Rollen Benutzer einladen dürfen und lade mich dann erneut ein. Der Server sagte außerdem: {response.message}", roomid)
        await client.room_leave(roomid)
        print("Bot canceled, no permission to invite")
        return
    if(len(list) == 1):
        await send_message(f"{bot_displayname} sagt: Ich verabschiede mich und schicke einen Arbeiter zum Einladen", roomid)
        await client.room_leave(roomid)
        await start_worker()
    await send_message(f"{bot_displayname} sagt: Ich habe meinem Arbeiter Bescheid gegeben, er kommt bald vorbei. Position in der Warteschlange: {len(list)-1}", roomid)
    await client.room_leave(roomid)

    #print(response.__dict__)
    #print(response.__attrs_attrs__)
    #print(response.transport_response)
    #print(response.message)

    ##Work-Bot übernimmt die Arbeit vom Enrol-Bot und holt die Daten aus dem ersten Objekt der Liste
    ##er läuft so lange, bis die Liste abgearbeitet ist

async def start_worker():
    while(not len(list) == 0):
        print("Starte Workbot...")
        invitee = list[0].invitee
        roomid = list[0].roomid
        event = list[0].event
        events = list[0].events

        await workclient.join(roomid)


        # get all invited people (some may be users, some may be groups)
        to_be_invited = []
        already_in_room = []
        for event in events:
            if 'type' in event:
                #await send_message(f"{bot_displayname} sagt: {event['type']}", roomid)
                if (event['type'] == 'm.room.member'):
                    if 'content' in event:
                        #await send_message(f"{bot_displayname} sagt: {event['content']}", roomid)
                        if 'membership' in event['content']:
                            #await send_message(f"{bot_displayname} sagt: {event['content']['membership']}", roomid)
                            if (event['content']['membership'] == 'invite'):
                                if 'state_key' in event:
                                    to_be_invited.append(event['state_key'])
                            if (event['content']['membership'] == 'join'):
                                if 'state_key' in event:
                                    already_in_room.append(event['state_key'])

        # syntax:
        # { 'type': 'm.room.member',
        #   'room_id': '!AQTHnwKnOTLIgVTZlb:example.com',
        #   'sender': '@kuechel:example.com',
        #   'content': {'membership': 'invite'},
        #   'state_key': '@10a:example.com',
        #   'origin_server_ts': 1585860032214,
        #   'unsigned': {'age': 6264213},
        #   'event_id': '$HtYxWl4cRDsIjplcYCkckzCQdQ-ohQPGCX42eSjTjro',
        #   'user_id': '@kuechel:example.com',
        #   'age': 6264213
        # }

        ## Bot ändert seinen Displayname auf den, von der Person er eingeladen wurde
        ## nach der Einladung setzt er ihn wieder auf "enrol-bot" zurück
        await workclient.set_displayname(str(await workclient.get_displayname(invitee)).split(": ")[1])

        #await send_message(f"{bot_displayname} sagt: Habe folgendes gefunden: {invited}", roomid)

        ## Jedes Mitglied, dass eine Gruppe ist, wird aufgelöst
        found_somebody_to_love=False
        for invitee in to_be_invited:
            name=str(invitee).split("@")[1].split(":")[0]
            (happy, newmembers) = await get_lmn_classmembers(name,roomid)
            if happy:
                if newmembers:
                    found_somebody_to_love=True
                    await send_work_message(f"{work_displayname} sagt: alle Mitglieder der Klasse/des Projekts {invitee} werden eingeladen!", roomid)
                    for newmember in newmembers:
                        ## alle User, die schon im Raum sind, werden gar nicht erst eingeladen
                        if "@"+newmember+":"+id_domain in already_in_room:
                            print(f"{newmember} ist schon drin")
                            continue

                        response = (await workclient.room_invite(roomid, "@"+newmember+":"+id_domain))
                        try:
                            asdf = response.transport_response
                            adsf = response.transport_response.status
                        except AttributeError:
                            print("Problem: Es gibt keinen Status für diese Antwort")
                            print(response)
                            return

                        if response.transport_response.status != 200:
                            try:
                                asdf = response.status_code
                            except AttributeError:
                                print("Problem: Es gibt keinen status_code in der Antwort")
                                print(response)
                                return

                            ## M_FORBIDDEN gibt es auch, wenn der User schon im Raum ist, aber das wird oben abgefangen
                            if response.status_code == "M_FORBIDDEN":
                                await send_work_message(f"{work_displayname} sagt: Ich darf {newmember} nicht in diesen Raum einladen. Bitte erlaube mir in den Einstellungen, das 'Standard'-Rollen Benutzer einladen dürfen. Der Server sagte außerdem: {response.message}", roomid)

        if not found_somebody_to_love:
            await send_work_message(f"{work_displayname} sagt: Ich habe keine Gruppe gefunden, deren Mitglieder ich einladen könnte. Lade zuerst eine Gruppe ein!", roomid)

        await workclient.set_displayname(work_displayname)
        await send_work_message(f"{work_displayname} sagt: Ich hoffe, ich habe gut gedient! Ich verlasse den Raum. Tschüss.", roomid)
        await workclient.room_leave(roomid)
        list.pop(0)

    # mache dich zum Einladenden (der ist vermutlich Administrator im Raum)
    #accesstoken = await get_impersonation_token('@kuechel:example.com', homeserver, shared_secret)
    #thisapi = api.Api()
    #response = requests.get(homeserver + thisapi.joined_members(accesstoken, roomid)[1])
    #print(response.json())
    #print(requests.get(homeserver + thisapi.whoami(accesstoken)[1]).json())
    #response = requests.get(homeserver+ thisapi.room_get_state(accesstoken,roomid)[1]).json()
    #print(json.dumps(response,sort_keys=True, indent=2))


async def login():
    await client.login(bot_passwd)
    await client.set_displayname(bot_displayname)
    print(f"Logge ein als {bot_displayname}.")
    await workclient.login(work_passwd)
    await workclient.set_displayname(work_displayname)
    print(f"Logge ein als {work_displayname}.")

async def logout():
    print(f"Logge aus als {bot_displayname}.")
    await client.close()
    print(f"Logge aus als {work_displayname}.")
    await workclient.close()

async def main():
    #auf das Event "Invite" warten
    client.add_event_callback(call_on_invites, InviteEvent)
    await client.sync_forever(30000)
    #await client.sync(15000)

loop = asyncio.get_event_loop()
check_response = loop.run_until_complete(check_functionality())

while True:
    print("Starte neue Schleife...")

    try:
        login_response = loop.run_until_complete(login())
    except KeyboardInterrupt:
        logout_response = loop.run_until_complete(logout())
        raise SystemExit

    try:
        main_response = loop.run_until_complete(main())
    except KeyboardInterrupt:
        logout_response = loop.run_until_complete(logout())
        raise SystemExit

    logout_response = loop.run_until_complete(logout())



logout_response = loop.run_until_complete(logout())


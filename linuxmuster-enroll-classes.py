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

bot_id = config['bot']['id']
bot_passwd = config['bot']['passwd']
homeserver = config['homeserver']['url']
id_domain = bot_id.split(":")[1]
shared_secret = str.encode(config['impersonation']['secret'])  ## needs to be byte-data
client = AsyncClient(homeserver, bot_id)


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

def check_functionality():

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

#access_token = get_impersonation_token(user_id, homeserver, shared_secret)
#print("Access token for %s: %s" % (user_id,access_token)

async def get_lmn_classmembers(possibleclass):
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
            if 'member' in jsondata['GROUPS'][group]:
                nomembersfound=False
                for cn in jsondata['GROUPS'][group]['member']:
                    members.append(cn[3:cn[0:].find(",OU")])
    except ValueError as e:
        print(e)
        return(False, None)

    if not nomembersfound:
        return(True, members)


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
    #print("Raum '" + room.display_name + "' beigetreten")

    # send a message about having joined
    await send_message("Enrol-Bot sagt: zu Diensten!", roomid)

    # examine the room
    try:
        response = (await client.room_get_state(roomid)).events
    except RoomGetStateError as e:
        print(response, e)
        ## return        

    # get all invited people (some may be users, some may be groups)
    invited = []
    for event in response:
        if 'type' in event:
            if (event['type'] == 'm.room.member'):
                if 'content' in event:
                    if 'membership' in event['content']:
                        if (event['content']['membership'] == 'invite'):
                            if 'state_key' in event:
                                invited.append(event['state_key'])
                
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
    
    ## Jedes Mitglied, dass eine Gruppe ist, wird aufgelöst
    for invitee in invited:
        name=str(invitee).split("@")[1].split(":")[0]
        (happy, newmembers) = await get_lmn_classmembers(name)
        if happy:
            if newmembers:
                await send_message(f"Enrol-Bot sagt: alle Mitglieder der Klasse/der Projekts {invitee} werden eingeladen!", roomid)
                for newmember in newmembers:
                    await client.room_invite(roomid, "@"+newmember+":"+id_domain)     

    await send_message(f"Enrol-Bot sagt: Ich hoffe, ich habe gut gedient! Ich verlasse den Raum. Tschüss.", roomid)
    await client.room_leave(roomid)

    # mache dich zum Einladenden (der ist vermutlich Administrator im Raum)
    #accesstoken = await get_impersonation_token('@kuechel:example.com', homeserver, shared_secret)
    #thisapi = api.Api()
    #response = requests.get(homeserver + thisapi.joined_members(accesstoken, roomid)[1])
    #print(response.json())
    #print(requests.get(homeserver + thisapi.whoami(accesstoken)[1]).json())
    #response = requests.get(homeserver+ thisapi.room_get_state(accesstoken,roomid)[1]).json()
    #print(json.dumps(response,sort_keys=True, indent=2))
    
    #await client.room_invite(roomid, "@username:url")                      #Add 'musterfrau' and leave the room
    #await client.close()

async def login():
    #einloggen
    await client.login(bot_passwd)

async def main():
    #auf das Event "Invite" warten
    client.add_event_callback(call_on_invites, InviteEvent)
    await client.sync_forever(30000)
    #await client.sync(15000)

async def logout():
    await client.close()


check_functionality()

loop = asyncio.get_event_loop()
login_response = loop.run_until_complete(login())


while True:
    print("Loop new")
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        raise SystemExit
    
client.close()


#!/usr/bin/env python3


import time

import json
import subprocess

import configparser 

import requests

# Asynchrone Matrix Bibliotheken
import asyncio
# Matrix-API Bibliotheken
import nio

# Config
config = configparser.ConfigParser()
config.read('config.ini')

homeserver = config['homeserver']['url']

# Bot
bot_displayname = config['kickbot']['displayname']
bot_id = config['kickbot']['id']
bot_passwd = config['kickbot']['passwd']

client = nio.AsyncClient(homeserver, bot_id)

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

async def call_on_invites(room, event):
    roomid = room.room_id 
    if(not isinstance(event, nio.InviteMemberEvent)):
        return
    if(event.membership != "invite"):
        return

    # Trete dem Raum bei
    #print('Trete Raum bei')
    await client.join(roomid)

    # Checke und resette Administratorstatus zu Moderatorstatus
    if (await amIadmin(roomid)):
        await resetToModerator(roomid)

    # Checke mein Powerlevel
    powerlevel = await getMyPowerLevel(roomid)
    levelname = await getPowerLevelName(powerlevel)
    await send_message(f"{bot_displayname} sagt: Hallo! Bin mit Status '{levelname}' in diesem Raum zu Diensten. Aufgabe: alle ausladen!", roomid)

    # Kicke alle User
    await kick_all_users(roomid)

async def getPowerLevelName(powerlevel):
    if powerlevel == 0:
        return "Standard"
    if powerlevel == 50:
        return "Moderator"
    if powerlevel >= 100:
        return "Administrator"
    return "Benutzerdefiniertes Level: "+int(powerlevel)

async def test(source, powerlevels):
    print(f"Source: {source}")
    print(f"PowerLevels: {powerlevels}")
    
async def kick_all_users(roomid):

    # Falls Kick-Bot kein Moderator in dem Raum ist:
    mypowerlevel = await getMyPowerLevel(roomid)
    if mypowerlevel < 50:
        ## versuche auf die Vergabe der Rechte zu warten
        have_rights = (await waitForRights(roomid))
        if not have_rights:
            return
    mypowerlevel = await getMyPowerLevel(roomid)

    ## Hole den Raumstatus
    response = (await client.room_get_state(roomid))
    events = response.events

    ## Suche nach den PowerLevels (Objekt) in diesem Raum:
    ##powerlevels = await getPowerLevels(events)
    ##if powerlevels == None:
    ##    ## Möglicherweise gibt es BadEvents in den PowerLevels, dann müssen wir hier abbrechen.
    ##    await send_message(f"{bot_displayname} sagt: Irgendetwas hat nicht funktioniert. Mache mich zum Moderator, kicke mich und lade mich wieder ein.", roomid)
    ##    return

    ## Jetzt suche nach Benutzern in diesem Raum:
    for event in events:
        if 'type' in event:
            # await send_message(f"{bot_displayname} sagt: {event['type']}", roomid)
            if (event['type'] == 'm.room.member'):
                if 'content' in event:
                    #await send_message(f"{bot_displayname} sagt: {event['content']}", roomid)
                    if 'membership' in event['content']:
                        #await send_message(f"{bot_displayname} sagt: {event['content']['membership']}", roomid)
                        if 'state_key' in event:
                            to_kick = event['state_key']
                            if to_kick == bot_id:
                                ## kicke mich nicht selbst
                                continue
                            if (event['content']['membership'] == 'invite' or event['content']['membership'] == 'join'):
                                powerlevel_to_kick = await getPowerLevel(roomid,to_kick)
                                if mypowerlevel > powerlevel_to_kick:
                                    #await send_message(f"{bot_displayname} sagt: Jetzt hätte ich versucht, {to_kick} mit Powerlevel {mypowerlevel} zu kicken/auszuladen", roomid)
                                    await client.room_kick(roomid, to_kick)
                                else:
                                    await send_message(f"{bot_displayname} sagt: {to_kick} kann ich nicht ausladen/kicken, habe nicht genügend Rechte ({powerlevel_to_kick} >= {mypowerlevel})", roomid)

    await send_message(f"{bot_displayname} sagt: Ich habe alle Benutzer aus dem Raum entfernt, so weit ich konnte. Ich hoffe ich habe gut gedient :) Ich verabschiede mich.", roomid)
    #print(f"Verlasse den Raum {roomid}")
    await client.room_leave(roomid)

async def waitForRights(roomid):
    ## Warte auf das Vergeben der Rechte, danach geht's weiter
    ## Überprüfung alle 10 Sekunden
    timeleft = 60
    while(timeleft > 0):
        await send_message(f"{bot_displayname} sagt: Ich darf in diesem Raum nichts tun. Mache mich bitte zum Moderator in diesem Raum (warte noch {timeleft} Sekunden).", roomid)
        time.sleep(10)
        timeleft=timeleft - 10
        powerlevel = await getMyPowerLevel(roomid)
        if powerlevel >= 50:
            return True

    await send_message(f"{bot_displayname} sagt: Mir wurden keine Rechte gegeben. Bitte lade mich erneut ein und mache mich zum Moderator", roomid)
    await client.room_leave(roomid)
    return False

##
## Da gibt es einen Bug.
## Wenn man mal einen Powerlevel eines Benutzers verändert und wieder zurückändert,
## dann gibt parse_event(event) einen BadEvent zurück. PowerLevels kann man dann
## nicht verwenden, um herauszubekommen, ob man rausschmeißen kann oder auch zur Findung des Powerlevels...
##
async def getPowerLevels(events):
    #Suche nach PowerLevels (Objekt) in diesem Raum:
    powerlevels = None
    for event in events:
        if 'type' in event:
            #print(event['type'])
            if (event['type'] == 'm.room.power_levels'):
                try:
                    powerlevels = nio.Event.parse_event(event).power_levels
                except:
                    ## parsen schlägt manchmal fehl (BadEvent), dann ist unklar, was die Powerlevels sind
                    ## print(nio.Event.parse_event(event))
                    pass
    return powerlevels


async def getPowerLevel(roomid, id_to_find):
    ## hole die Powerlevels aus dem Raum
    response = await client.room_get_state(roomid)
    events = response.events
    powerlevels = await getPowerLevels(events)
    powerlevel = 0
    ## hole PowerLevel des Bots in dem Raum
    if powerlevels != None:
        powerlevel = powerlevels.get_user_level(id_to_find)
    else:
        ## Manuelles Holen des Powerlevels des Bots
        print(f"BadEvent for Powerlevels in room ${roomid}. Wir checken manuell.")
        try:
            content = (await client.room_get_state_event(roomid,'m.room.power_levels', '')).content
            powerlevel = int(content['users'][id_to_find])
        except:
            print(f"Manuelles Checken der Powerlevels schlug fehl... Gebe auf")
            print(event)
    return powerlevel

async def getMyPowerLevel(roomid):
    ## hole die Powerlevels aus dem Raum
    response = await client.room_get_state(roomid)
    events = response.events
    powerlevels = await getPowerLevels(events)
    powerlevel = 0
    ## hole PowerLevel des Bots in dem Raum
    if powerlevels != None:
        powerlevel = powerlevels.get_user_level(bot_id)
    else:
        ## Manuelles Holen des Powerlevels des Bots
        print(f"BadEvent for Powerlevels in room ${roomid}. Wir checken manuell.")
        try:
            content = (await client.room_get_state_event(roomid,'m.room.power_levels', '')).content
            powerlevel = int(content['users'][bot_id])
        except:
            print(f"Manuelles Checken der Powerlevels schlug fehl... Gebe auf")
            print(event)
    return powerlevel
        
async def resetToModerator(roomid):
    try:
        ## setze den Administratorstatus zurück auf 50 (Moderator)
        content = (await client.room_get_state_event(roomid,'m.room.power_levels', '')).content
        content['users'][bot_id] = 50
        response = (await client.room_put_state(roomid,'m.room.power_levels',content))
        response = (await client.room_get_state_event(roomid,'m.room.power_levels', ''))
        await send_message(f"{bot_displayname} sagt: Administrator sollte ich hier nicht sein. Habe mich zum Moderator gemacht.",roomid)
        print(f"{bot_displayname} sagt: Administrator sollte ich hier nicht sein. Habe mich zum Moderator gemacht.")
    except:
        await send_message(f"{bot_displayname} sagt: Wollte mich vom Administrator degradieren. Irgendwie hat das nicht geklappt -> Sag' dem Admin Bescheid.",roomid)
    return    

async def amIadmin(roomid):
    powerlevel = (await getMyPowerLevel(roomid))
    if powerlevel >= 100:
        return True
    else:
        return False

async def checkrooms(response):
    try:
        rooms = (await client.joined_rooms()).rooms
    except:
        print("Hmm.. Irgendwas hat wohl nicht funktioniert, die Räume auszulesen.")
        print(rooms)
        return

    for roomid in rooms:
        if (await amIadmin(roomid)):
            await resetToModerator(roomid)
            await client.room_leave(roomid)
    return


async def check_functionality():
    return

async def login():
    await client.login(bot_passwd)
    await client.set_displayname(bot_displayname)
    print(f"Logge ein als {bot_displayname}.")
    
async def logout():
    print(f"Logge aus als {bot_displayname}.")
    await client.close()

async def main():
    client.add_event_callback(call_on_invites, nio.InviteEvent)
    #client.add_event_callback(test, nio.RoomMessage)
    client.add_response_callback(checkrooms, nio.SyncResponse)
    await client.sync_forever(30000)

loop = asyncio.get_event_loop()
check_response = loop.run_until_complete(check_functionality())

while True:
    print("Starte neue Schleife..")

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

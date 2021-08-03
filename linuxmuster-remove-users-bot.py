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

# Python Logging api
import logging
import logging.handlers

# Config
config = configparser.ConfigParser()
config.read('config.ini')

homeserver = config['homeserver']['url']

# Bot
bot_displayname = config['kickbot']['displayname']
bot_id = config['kickbot']['id']
bot_passwd = config['kickbot']['passwd']

client = nio.AsyncClient(homeserver, bot_id)

# Logging
do_debug = config['log']['debug']
log_file = config['log']['logfilename']

logger = logging.getLogger('Logger')
logger.setLevel(logging.DEBUG)

handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5)
stream = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s : %(levelname)s : %(message)s")
stream.setFormatter(formatter)
handler.setFormatter(formatter)

logger.addHandler(handler)
logger.addHandler(stream)

# Chat-Colors
color_red = '#ff0000'
color_green = '#008000'


async def debug(msg, code = 'debug'):
    ##Sende debug o. warnung via Konsole und schreibe in Log-Datei
    if code == 'debug':
        if do_debug == "True":
            logger.debug(msg)
    elif code == 'warning':
        logger.warning(msg)
    elif code == 'critical':
        logger.critical(msg)
    return

async def send_colored_message(msg, roomid, color):
    ##Baue Nachricht aus bekommenen Parametern und schicke sie (farbige Nachricht)
    await client.room_send(
        room_id = roomid,
        message_type = "m.room.message",
        content={
            "msgtype": "m.text",
            "body": "<" + color + ">(" + msg + ")",
            "formatted_body": "<p><span data-mx-color=" + color + ">" + msg + "</span></p>",
            "format": "org.matrix.custom.html"
        }
    )

async def send_message(msg, roomid):
    ##Baue Nachricht aus bekommenen Parametern und schicke sie (weiße Nachricht)
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

    ## Einladung ist kein InviteMemberEvent
    if(not isinstance(event, nio.InviteMemberEvent)):
        await debug(f"Einladung in Raum {roomid} ist kein InviteMemberEvent.")
        return

    ## Einladung: Membership steht nicht auf "invite"
    if(event.membership != "invite"):
        await debug(f"Einladung in Raum {roomid}: Einladungsmitgliedschaft steht auf: {event.membership} (nicht \"invite\")")
        return

    response = await client.join(roomid)
    if isinstance(response, nio.responses.JoinError):
        try:
            await debug(f"Raumbeitritt nach Einladung in Raum {roomid} schlug fehl: {response.message} ({response.status_code})")
        except AttributeError:
            await debug(f"Problem: Es gibt keinen status_code in der Antwort {response}.")
        return

    await debug(f"Beitritt {roomid} erfolgreich")

    # Checke und resette Administratorstatus zu Moderatorstatus
    if (await amIadmin(roomid)):
        await resetToModerator(roomid)

    # Checke mein Powerlevel
    powerlevel = await getMyPowerLevel(roomid)
    levelname = await getPowerLevelName(powerlevel)
    await send_message(f"{bot_displayname} sagt: Hallo! Bin mit Status '{levelname}' in diesem Raum zu Diensten. Meine Aufgabe: alle ausladen!", roomid)

    # Kicke alle User
    await kick_all_users(roomid)

async def getPowerLevelName(powerlevel):
    await debug("Hole mir den Namen des PowerLevels")
    if powerlevel == 0:
        return "Standard"
    if powerlevel == 50:
        return "Moderator"
    if powerlevel >= 100:
        return "Administrator"
    return "Benutzerdefiniertes Level: "+str(powerlevel)

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
    #print(response)
    events = response.events

    ## Suche nach den PowerLevels (Objekt) in diesem Raum:
    ##powerlevels = await getPowerLevels(events)
    ##if powerlevels == None:
    ##    ## Möglicherweise gibt es BadEvents in den PowerLevels, dann müssen wir hier abbrechen.
    ##    await send_message(f"{bot_displayname} sagt: Irgendetwas hat nicht funktioniert. Mache mich zum Moderator, kicke mich und lade mich wieder ein.", roomid)
    ##    return
    
    await debug(f"Beginne die Benutzer aus {roomid} zu kicken..")
    ## Jetzt suche nach Benutzern in diesem Raum:
    for event in events:
        if 'type' in event:
            # await send_message(f"{bot_displayname} sagt: {event['type']}", roomid)
            #await debug(f"{event['type']}")
            if (event['type'] == 'm.room.member'):
                if 'content' in event:
                    #await debug(f"{event['content']}")
                   #await send_message(f"{bot_displayname} sagt: {event['content']}", roomid)
                    if 'membership' in event['content']:
                        #await debug(f"{event['content']['membership']}")
                        #await send_message(f"{bot_displayname} sagt: {event['content']['membership']}", roomid)
                        if 'state_key' in event:
                            to_kick = event['state_key']
                            await debug(f"Es soll: {to_kick} rausgeschmissen werden.")
                            if to_kick == bot_id:
                                ## kicke mich nicht selbst
                                await debug(f"Hier nicht: Kicke mich nicht selbst")
                                continue
                            if (not (event['content']['membership'] == 'invite' or event['content']['membership'] == 'join')):
                                await debug(f"Hier nicht: Kicke {to_kick} nicht, denn er ist hier nicht drin")
                                continue

                            powerlevel_to_kick = await getPowerLevel(roomid,to_kick)
                                
                            if mypowerlevel > powerlevel_to_kick:
                                #await send_message(f"{bot_displayname} sagt: Jetzt hätte ich versucht, {to_kick} mit Powerlevel {mypowerlevel} zu kicken/auszuladen", roomid)
                                await client.room_kick(roomid, to_kick)
                                if isinstance(response, nio.responses.RoomKickError):
                                    await debug("Fehler beim Rauswerfen: " + response.message)
                                    continue
                            else:
                                await debug(f"Hier nicht: {to_kick} hat die Rechte {powerlevel_to_kick} und ich nur {mypowerlevel}.")
                                await send_colored_message(f"{bot_displayname} sagt: {to_kick} kann ich nicht ausladen/kicken, habe nicht genügend Rechte ({powerlevel_to_kick} >= {mypowerlevel})", roomid, color_red)

    await send_colored_message(f"{bot_displayname} sagt: Ich habe alle Benutzer aus dem Raum entfernt, so weit ich konnte. Alle anderen muss der Ersteller des Raumes ausladen. Falls weitere Administratoren im Raum sind, muss man diese bitten den Raum zu verlassen.", roomid, color_green)
    #print(f"Verlasse den Raum {roomid}")
    await client.room_leave(roomid)
    await debug("Arbeit erledigt und Raum verlassen")

async def waitForRights(roomid):
    await debug("Fehlende Rechte im Raum. Warte bis ich Rechte erhalte..")
    ## Warte auf das Vergeben der Rechte, danach geht's weiter
    ## Überprüfung alle 10 Sekunden
    timeleft = 60
    while(timeleft > 0):
        await send_colored_message(f"{bot_displayname} sagt: Ich darf in diesem Raum nichts tun. Mache mich bitte zum Moderator in diesem Raum (warte noch {timeleft} Sekunden).", roomid, color_red)
        time.sleep(10)
        timeleft=timeleft - 10
        powerlevel = await getMyPowerLevel(roomid)
        if powerlevel >= 50:
            return True

    await send_colored_message(f"{bot_displayname} sagt: Mir wurden keine Rechte gegeben. Bitte lade mich erneut ein und mache mich zum Moderator", roomid, color_red)
    await client.room_leave(roomid)
    await debug("Rechte im Raum nicht erhalten. Gehe wieder.")
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
    await debug(f"Hole mir die PowerLevels von {id_to_find} im Raum {roomid}...")
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
    await debug(f"Hole mir die PowerLevels von mir im Raum {roomid}...")
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
    await debug("Setze mein PowerLevel von Admin auf Moderator zurück")
    try:
        ## setze den Administratorstatus zurück auf 50 (Moderator)
        content = (await client.room_get_state_event(roomid,'m.room.power_levels', '')).content
        content['users'][bot_id] = 50
        response = (await client.room_put_state(roomid,'m.room.power_levels',content))
        response = (await client.room_get_state_event(roomid,'m.room.power_levels', ''))
        await send_message(f"{bot_displayname} sagt: Administrator sollte ich hier nicht sein. Habe mich zum Moderator gemacht.",roomid)
        #print(f"{bot_displayname} sagt: Administrator sollte ich hier nicht sein. Habe mich zum Moderator gemacht.")
    except:
        await send_message(f"{bot_displayname} sagt: Wollte mich vom Administrator degradieren. Irgendwie hat das nicht geklappt -> Sag' dem Admin Bescheid.",roomid)
        await debug("Zurücksetzen meines Powerlevels von Admin auf Moderator fehlgeschlagen.", 'warning')
    return    

async def amIadmin(roomid):
    powerlevel = (await getMyPowerLevel(roomid))
    if powerlevel >= 100:
        return True
    else:
        return False

async def checkrooms(response):
    try:
        response = await client.joined_rooms()
    except:
        await debug("Fehler beim Auslesen der Räume: " + str(response), 'warning')
        return False

    rooms = response.rooms

    for roomid in rooms:
        if (await amIadmin(roomid)):
            await resetToModerator(roomid)
            await client.room_leave(roomid)

    return True


async def check_functionality():
    return

async def login():
    await debug(f"Logge mich ein als {bot_displayname}")
    response = await client.login(bot_passwd)
    if isinstance(response, nio.responses.LoginError):
        await debug("Fehler beim Einloggen: " + response.message)
        return False
    response = await client.set_displayname(bot_displayname)
    if isinstance(response, nio.responses.ProfileSetDisplayNameError):
        await debug("Fehler beim Setzen des Namens: " + repsonse.message)

    return True
    
async def logout():
    await debug(f"Logge mich aus als {bot_displayname}")
    #print(f"Logge aus als {bot_displayname}.")
    await client.close()

async def main():
    await debug("Starte Ausladungs-Bot...")
    ## Callback, um Einladungen zu bearbeiten
    client.add_event_callback(call_on_invites, nio.InviteEvent)
    ## Callback, um Raumberechtigungen zu checken
    #client.add_response_callback(checkrooms, nio.SyncResponse)
    await client.sync_forever(30000)

    #client.add_event_callback(test, nio.RoomMessage)

loop = asyncio.get_event_loop()
check_response = loop.run_until_complete(check_functionality())

while True:
    logger.debug("Starte neue Schleife..")
    try:
        login_response = loop.run_until_complete(login())
    except KeyboardInterrupt:
        login_response = False

    if not login_response:
        logout_response = loop.run_until_complete(logout())
        raise SystemExit

    try:
        main_response = loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.debug("Keyboard Interrupt...")
        main_response = False

    if not main_response:
        logout_response = loop.run_until_complete(logout())
        raise SystemExit

logout_response = loop.run_until_complete(logout())

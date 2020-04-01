#!/usr/bin/env python3
import json
import hmac
import hashlib
import requests
import asyncio
from nio import (AsyncClient, InviteEvent, MatrixRoom)
import configparser

config = configparser.ConfigParser()
config.read('config.ini')

bot_id = config['bot']['id']
bot_passwd = config['bot']['passwd']
homeserver = config['homeserver']['url'] 
shared_secret = config['impersonation']['secret']  ## needs to be byte-data
client = AsyncClient(homeserver, bot_id)


def get_impersonation_token(user_id, homeserver, shared_secret):
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

async def call_on_invites(room, event):

    if ( event.membership != "invite" ):
        print("This is not an invitation! (", event.membership, ")")
        return

# see: python3 >>> help(InviteMemberEvent)
#InviteMemberEvent(source={'type': 'm.room.member', 'state_key': '@kuechel:humboldt-ka.de', 'sender': '@kuechel:humboldt-ka.de'}, sender='@kuechel:humboldt-ka.de', state_key='@kuechel:humboldt-ka.de', membership='join', prev_membership=None, content={'membership': 'join', 'displayname': 'Tobias Küchel', 'avatar_url': 'mxc://humboldt-ka.de/lTIJSiJLGDEGygXOJaarDwxt'}, prev_content=None)
#InviteMemberEvent(source={'type': 'm.room.member', 'sender': '@kuechel:humboldt-ka.de', 'state_key': '@schuelte:humboldt-ka.de', 'origin_server_ts': 1585738923323, 'unsigned': {'age': 80}, 'event_id': '$s1qbIVKy_V2fckV_PJDSHNwNIceZhVkhmfPY4XBs-4c'}, sender='@kuechel:humboldt-ka.de', state_key='@schuelte:humboldt-ka.de', membership='invite', prev_membership=None, content={'is_direct': True, 'membership': 'invite', 'displayname': 'Test', 'avatar_url': None}, prev_content=None)

    print("invited!")
    roomid=room.room_id
    await client.join(roomid)                                                           #Join to every room the bot is invited
    print("Raum '" + room.display_name + "' beigetreten")
    print(event)
    await client.room_send(
        room_id=roomid,
        message_type="m.room.message",
        content={
            "msgtype": "m.text",
            "body": "Bot sagt: zu Diensten!"
        }
    )
    
    #await client.room_invite(roomid, "@musterfrau:humboldt-ka.de")                      #Add 'musterfrau' and leave the room
    #await client.room_leave(roomid)
    #await client.close()

async def login():
    #einloggen
    await client.login(bot_passwd)

async def main():
    #auf das Event "Invite" warten
    client.add_event_callback(call_on_invites, InviteEvent)
    await client.sync_forever(30000)

loop = asyncio.get_event_loop()
login_response = loop.run_until_complete(login())

while True:
    print("Loop new")
    loop.run_until_complete(main())
    
client.close()



#!/usr/bin/env python3
import json
import hmac
import hashlib
import requests
import asyncio
from nio import * 
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


    # also possible InviteAliasEvent
    if (not isinstance(event, InviteMemberEvent)):
        print("This is not an InviteMemberEvent!", event)
        return
    
    # see: python3 >>> help(InviteMemberEvent)
    if ( event.membership != "invite" ):
        print("This is not an invitation! (", event.membership, ")")
        return
    

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

    ## Versuche, alle Mitglieder herauszubekommen
    try:
        response = (await client.joined_members(roomid))
    except:
        print(response)
        ## return

    for member in response.members:
        username=str(member.user_id).split("@")[1].split(":")[0]
        print(username)
        
    
    #await client.room_invite(roomid, "@username:url")                      #Add 'musterfrau' and leave the room
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



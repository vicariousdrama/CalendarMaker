#!~/.pyenv/boostzapper/bin/python3
from nostr.event import Event, AuthMessage
from nostr.filter import Filter, Filters
from nostr.key import PrivateKey, PublicKey
from nostr.message_type import ClientMessageType
from nostr.relay_manager import RelayManager
import datetime
import json
import logging
import os
import random
import shutil
import ssl
import sys
import time
import uuid

# globals
privateKey = None
relayManager = None
config = None
_relayPublishTime = 2.50
_relayConnectTime = 1.25
_directMessages = []
_monitoredEvents = []
_monitoredPubkeys = []
_monitoredProfiles = []
_monitoredEvent = []

def loadJsonFile(filename, default=None):
    if filename is None: return default
    if not os.path.exists(filename): return default
    with open(filename) as f:
        return(json.load(f))

def saveJsonFile(filename, obj):
    # first as temp file
    tempfile = f"{filename}.tmp"
    with open(tempfile, "w") as f:
        f.write(json.dumps(obj=obj,indent=2))
    # then move over top
    shutil.move(tempfile, filename)

def getNostrRelaysFromConfig(aConfig):
    relays = []
    relayUrls = []
    if "relays" in aConfig:
        for relay in aConfig["relays"]:
            relayUrl = ""
            canRead = True
            canWrite = True
            if type(relay) is str:
                relayUrl = relay
            if type(relay) is dict:
                if "url" not in relay: continue
                relayUrl = relay["url"]
                canRead = relay["read"] if "read" in relay else canRead
                canWrite = relay["write"] if "write" in relay else canWrite
            relayUrl = relayUrl if str(relayUrl).startswith("wss://") else f"wss://{relayUrl}"
            if relayUrl not in relayUrls:
                relayUrls.append(relayUrl)
                relays.append({"url":relayUrl,"read":canRead,"write":canWrite})
    return relays

def connectToRelays():
    logger.debug("Connecting to relays")
    global relayManager
    relayManager = RelayManager()
    relays = getNostrRelaysFromConfig(config).copy()
    random.shuffle(relays)
    relaysLeftToAdd = 50
    for nostrRelay in relays:
        if relaysLeftToAdd <= 0: break
        relaysLeftToAdd -= 1
        if type(nostrRelay) is dict:
            relayManager.add_relay(url=nostrRelay["url"],read=nostrRelay["read"],write=nostrRelay["write"])
        if type(nostrRelay) is str:
            relayManager.add_relay(url=nostrRelay)
    relayManager.open_connections({"cert_reqs": ssl.CERT_NONE})
    time.sleep(_relayConnectTime)

def disconnectRelays():
    logger.debug("Disconnecting from relays")
    global relayManager
    relayManager.close_connections()

def authenticateRelays(theRelayManager, pk):
    if not theRelayManager.message_pool.has_auths(): return False
    while theRelayManager.message_pool.has_auths():
        auth_msg = theRelayManager.message_pool.get_auth()
        logger.info(f"AUTH request received from {auth_msg.url} with challenge: {auth_msg.challenge}")
        am = AuthMessage(challenge=auth_msg.challenge,relay_url=auth_msg.url)
        pk.sign_event(am)
        logger.debug(f"Sending signed AUTH message to {auth_msg.url}")
        theRelayManager.publish_auth(am)
        theRelayManager.message_pool.auths.task_done()
    return True

def siftMessagePool():
    global _directMessages
    global _monitoredEvents
    global _monitoredPubkeys
    global _monitoredProfiles
    global _monitoredEvent
    # AUTH
    authenticateRelays(relayManager, privateKey)
    # EVENT
    while relayManager.message_pool.has_events():
        event_msg = relayManager.message_pool.get_event()
        subid = event_msg.subscription_id
        if subid.startswith("my_dms"): _directMessages.append(event_msg.event)
        elif subid.startswith("my_events"): _monitoredEvents.append(event_msg.event)
        elif subid.startswith("my_pubkeys"): _monitoredPubkeys.append(event_msg.event)
        elif subid.startswith("my_profiles"): _monitoredProfiles.append(event_msg.event)
        elif subid.startswith("my_eventbyid"): _monitoredEvent.append(event_msg.event)
        else:
            u = event_msg.url
            c = event_msg.event.content
            logger.debug(f"Unexpected event from relay {u} with subscription {subid}: {c}")
        relayManager.message_pool.events.task_done()
    # NOTICES
    while relayManager.message_pool.has_notices():
        notice = relayManager.message_pool.get_notice()
        message = f"RELAY NOTICE FROM {notice.url}: {notice.content}"
        logger.info(message)
        relayManager.message_pool.notices.task_done()
    # EOSE NOTICES
    while relayManager.message_pool.has_eose_notices():
        relayManager.message_pool.get_eose_notice()
        relayManager.message_pool.eose_notices.task_done()

def removeSubscription(relaymanager, subid):
    request = [ClientMessageType.CLOSE, subid]
    message = json.dumps(request)
    relaymanager.publish_message(message)
    time.sleep(_relayPublishTime)
    relaymanager.close_subscription(subid)

if __name__ == '__main__':

    # Logging to systemd
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(fmt="%(asctime)s %(name)s.%(levelname)s: %(message)s", datefmt="%Y.%m.%d %H:%M:%S")
    stdoutLoggingHandler = logging.StreamHandler(stream=sys.stdout)
    stdoutLoggingHandler.setFormatter(formatter)
    logging.Formatter.converter = time.gmtime
    logger.addHandler(stdoutLoggingHandler)

    # Look at arguments
    configfile = "config.json"
    calendarfile = "calendarconfig.json"
    argField = "calendar"
    argValue = ""
    if len(sys.argv) > 1:
        for argValue in sys.argv[1:]:
            if argValue.startswith("--"):
                argField = str(argValue[2:]).lower()
            else:
                logger.debug(f"Assigning value {argValue} to {argField}")
                if argField == "config": configfile = argValue
                if argField == "calendar": calendarfile = argValue

    # Load config file
    config = loadJsonFile(configfile)
    if config is None:
        logger.error(f"Config file {configfile} is empty or not json")
        quit()
    
    # Load calendar file
    calendar = loadJsonFile(calendarfile)
    if calendar is None:
        logger.error(f"Calendar file {calendarfile} is empty or not json")
        quit()

    # Connect to relays
    connectToRelays(config)

    # Set local parameters
    configupdated = False
    nsec = config["nsec"]
    if len(nsec) < 63:
        logger.warning("nsec length less than 63, creating new one")
        nsec = PrivateKey().bech32
        config["nsec"] = nsec
        configupdated = True
    if configupdated:
        saveJsonFile(configfile, config)
    calendaruuid = calendar["uuid"]
    if len(calendaruuid) == 0:
        calendaruuid = str(uuid.uuid4())
        calendar["uuid"] = calendaruuid
        calendarconfigupdated = True
    if calendarconfigupdated:
        saveJsonFile(calendarfile, calendar)
    privateKey = PrivateKey().from_nsec(config["nsec"])
    sleepTime = calendar["frequency"]
    keepRunning = True

    # Loop
    while keepRunning:

        calendarAList = []
        currentTime = int(datetime.datetime.now().timestamp())

        # do each in search list
        for searchitem in calendar["searchlist"]:
            kind = searchitem["kind"]
            author = searchitem["author"]

            # Setup and publish subscription
            subscription_events = "my_events"
            filters = Filters([Filter(kinds=[kind],authors=[author])])
            request = [ClientMessageType.REQUEST, subscription_events]
            request.extend(filters.to_json_array())
            message = json.dumps(request)
            relayManager.add_subscription(subscription_events, filters)
            relayManager.publish_message(message)
            time.sleep(_relayPublishTime)

            # Check if needed to authenticate and publish again if need be
            if authenticateRelays(relayManager, privateKey):
                relayManager.publish_message(message)
                time.sleep(_relayPublishTime)

            # Sift through messages
            siftMessagePool()
            
            # Remove subscription
            removeSubscription(relayManager, subscription_events)

            # Check matching events
            _monitoredEventsTmp = []
            for event in _monitoredEvents:
                # handle calendars
                if event.kind == 31924:
                    useThisCalendar = False
                    if event.tags is not None:
                        for tagset in event.tags:
                            if len(tagset) < 2: continue
                            if tagset[0] != "d": continue
                            if tagset[1] == searchitem["d"]:
                                useThisCalendar = True
                    if not useThisCalendar:
                        _monitoredEventsTmp.append(event)
                        continue
                    for tagset in event.tags:
                        if len(tagset) < 2: continue
                        if tagset[0] != "a": continue
                        calendarAList.append(tagset[1])
                # handle date and time events
                if event.kind in (31922, 31923):
                    useThisEvent = False
                    eventuuid = None
                    phrase = searchitem["phrase"]
                    if str(phrase).lower() in str(event.content).lower():
                        useThisEvent = True
                    if event.tags is not None:
                        for tagset in event.tags:
                            if len(tagset) < 2: continue
                            if tagset[0] in ("name", "description"):
                                if str(phrase).lower() in str(tagset[1]).lower():
                                    useThisEvent = True
                            if tagset[0] == "d": 
                                eventuuid = tagset[1]
                    if eventuuid is None:
                        useThisEvent = False
                    if not useThisEvent:
                        _monitoredEventsTmp.append(event)
                        continue
                    # ensure not in the past
                    startOrEndInFuture = False
                    for tagset in event.tags:
                        if len(tagset) < 2: continue
                        if tagset[0] in ("start", "end"):
                            if currentTime < int(tagset[1]): startOrEndInFuture = True
                    if not startOrEndInFuture:
                        _monitoredEventsTmp.append(event)
                        continue
                    # build up the a tag
                    avalue = f"{kind}:{event.public_key}:{eventuuid}"
                    calendarAList.append(avalue)
            _monitoredEvents = _monitoredEventsTmp
        # end for loop

        # Done checking configured calendar items and pubkeys
        kind = 31924
        content = calendar["content"]
        tags = []
        tags.append(["d", calendaruuid])
        tags.append(["name", calendar["name"]])
        tags.append(["description", calendar["description"]])
        tags.append(["image", calendar["image"]])
        tags.append(["p", privateKey.public_key.hex(), "", "Maintainer"])
        for avalue in calendarAList:
            tags.append(["a", avalue])
        # create event and sign it
        e = Event(content=content,kind=kind,tags=tags)
        privateKey.sign_event(e)

        # Send the event
        relayManager.publish_event(e)

        # Sleep
        if sleepTime <= 0:
            keepRunning = False
        else:
            logger.debug(f"sleeping for {sleepTime}")
            time.sleep(sleepTime)
    
    # Disconnect from relays
    disconnectRelays()

from gevent import monkey

monkey.patch_all()
import json
from dotenv import load_dotenv
from ssdp import SSDPServer
from flask import Flask, jsonify, render_template
from gevent.pywsgi import WSGIServer
import xml.etree.ElementTree as ElementTree
from datetime import timedelta, datetime, time
import logging
import socket
import threading
from requests.auth import HTTPDigestAuth
import requests
import os
import sched


logging.basicConfig(level=logging.INFO)
load_dotenv(verbose=True)

app = Flask(__name__)
scheduler = sched.scheduler()
logger = logging.getLogger()

host_name = socket.gethostname()
host_ip = socket.gethostbyname(host_name)

# URL format: <protocol>://<username>:<password>@<hostname>:<port>, example: https://test:1234@localhost:9981
config = {
    "deviceID": os.environ.get("DEVICE_ID") or "12345678",
    "bindAddr": os.environ.get("TVH_BINDADDR") or "",
    # only used if set (in case of forward-proxy)
    "tvhURL": os.environ.get("TVH_URL") or "http://localhost:9981",
    "tvhProxyURL": os.environ.get("TVH_PROXY_URL"),
    "tvhProxyHost": os.environ.get("TVH_PROXY_HOST") or host_ip,
    "tvhProxyPort": os.environ.get("TVH_PROXY_PORT") or 5004,
    "tvhUser": os.environ.get("TVH_USER") or "",
    "tvhPassword": os.environ.get("TVH_PASSWORD") or "",
    # number of tuners in tvh
    "tunerCount": os.environ.get("TVH_TUNER_COUNT") or 6,
    "tvhWeight": os.environ.get("TVH_WEIGHT") or 300,  # subscription priority
    # usually you don't need to edit this
    "chunkSize": os.environ.get("TVH_CHUNK_SIZE") or 1024 * 1024,
    # specifiy a stream profile that you want to use for adhoc transcoding in tvh, e.g. mp4
    "streamProfile": os.environ.get("TVH_PROFILE") or "pass",
}

discoverData = {
    "FriendlyName": "tvhProxy",
    "Manufacturer": "Silicondust",
    "ModelNumber": "HDTC-2US",
    "FirmwareName": "hdhomeruntc_atsc",
    "TunerCount": int(config["tunerCount"]),
    "FirmwareVersion": "20150826",
    "DeviceID": config["deviceID"],
    "DeviceAuth": "test1234",
    "BaseURL": "%s"
    % (
        config["tvhProxyURL"]
        or "http://" + config["tvhProxyHost"] + ":" + str(config["tvhProxyPort"])
    ),
    "LineupURL": "%s/lineup.json"
    % (
        config["tvhProxyURL"]
        or "http://" + config["tvhProxyHost"] + ":" + str(config["tvhProxyPort"])
    ),
}


@app.route("/discover.json")
def discover():
    return jsonify(discoverData)


@app.route("/lineup_status.json")
def status():
    return jsonify(
        {
            "ScanInProgress": 0,
            "ScanPossible": 0,
            "Source": "Cable",
            "SourceList": ["Cable"],
        }
    )


@app.route("/lineup.json")
def lineup():
    lineup = []

    for c in _get_channels():
        if c["enabled"]:
            url = "%s/stream/channel/%s?profile=%s&weight=%s" % (
                config["tvhURL"],
                c["uuid"],
                config["streamProfile"],
                int(config["tvhWeight"]),
            )

            lineup.append(
                {"GuideNumber": str(c["number"]), "GuideName": c["name"], "URL": url}
            )

    return jsonify(lineup)


@app.route("/lineup.post", methods=["GET", "POST"])
def lineup_post():
    return ""


@app.route("/")
@app.route("/device.xml")
def device():
    return render_template("device.xml", data=discoverData), {
        "Content-Type": "application/xml"
    }


@app.route("/epg.xml")
def epg():
    return _get_xmltv(), {"Content-Type": "application/xml"}


def _get_channels():
    url = "%s/api/channel/grid" % config["tvhURL"]
    params = {"limit": 999999, "start": 0}
    try:
        r = requests.get(
            url,
            params=params,
            auth=HTTPDigestAuth(config["tvhUser"], config["tvhPassword"]),
        )
        return r.json(strict=False)["entries"]

    except Exception as e:
        logger.error("An error occured: %s" + repr(e))


def _get_genres():
    def _findMainCategory(majorCategories, minorCategory):
        prevKey, currentKey = None, None
        for currentKey in sorted(majorCategories.keys()):
            if currentKey > minorCategory:
                return majorCategories[prevKey]
            prevKey = currentKey
        return majorCategories[prevKey]

    url = "%s/api/epg/content_type/list" % config["tvhURL"]
    params = {"full": 1}
    try:
        r = requests.get(
            url, auth=HTTPDigestAuth(config["tvhUser"], config["tvhPassword"])
        )
        entries = r.json(strict=False)["entries"]
        r = requests.get(
            url,
            params=params,
            auth=HTTPDigestAuth(config["tvhUser"], config["tvhPassword"]),
        )
        entries_full = r.json(strict=False)["entries"]
        majorCategories = {}
        genres = {}
        for entry in entries:
            majorCategories[entry["key"]] = entry["val"]
        for entry in entries_full:
            if entry["key"] not in majorCategories:
                mainCategory = _findMainCategory(majorCategories, entry["key"])
                if mainCategory != entry["val"]:
                    genres[entry["key"]] = [mainCategory, entry["val"]]
                else:
                    genres[entry["key"]] = [entry["val"]]
            else:
                genres[entry["key"]] = [entry["val"]]
        return genres
    except Exception as e:
        logger.error("An error occured: %s" + repr(e))


def _get_xmltv():
    try:
        url = "%s/xmltv/channels" % config["tvhURL"]
        r = requests.get(
            url, auth=HTTPDigestAuth(config["tvhUser"], config["tvhPassword"])
        )
        logger.info("downloading xmltv from %s", r.url)
        tree = ElementTree.ElementTree(
            ElementTree.fromstring(
                requests.get(
                    url, auth=HTTPDigestAuth(config["tvhUser"], config["tvhPassword"])
                ).content
            )
        )
        root = tree.getroot()
        url = "%s/api/epg/events/grid" % config["tvhURL"]
        params = {
            "limit": 999999,
            "filter": json.dumps(
                [
                    {
                        "field": "start",
                        "type": "numeric",
                        "value": int(
                            round(
                                datetime.timestamp(datetime.now() + timedelta(hours=72))
                            )
                        ),
                        "comparison": "lt",
                    }
                ]
            ),
        }
        r = requests.get(
            url,
            params=params,
            auth=HTTPDigestAuth(config["tvhUser"], config["tvhPassword"]),
        )
        logger.info("downloading epg grid from %s", r.url)
        epg_events_grid = r.json(strict=False)["entries"]
        epg_events = {}
        event_keys = {}
        for epg_event in epg_events_grid:
            if epg_event["channelUuid"] not in epg_events:
                epg_events[epg_event["channelUuid"]] = {}
            epg_events[epg_event["channelUuid"]][epg_event["start"]] = epg_event
            for key in epg_event.keys():
                event_keys[key] = True
        channelNumberMapping = {}
        channelsInEPG = {}
        genres = _get_genres()
        for child in root:
            if child.tag == "channel":
                channelId = child.attrib["id"]
                channelNo = child[1].text
                if not channelNo:
                    logger.error("No channel number for: %s", channelId)
                    channelNo = "00"
                if not child[0].text:
                    logger.error("No channel name for: %s", channelNo)
                    child[0].text = "No Name"
                channelNumberMapping[channelId] = channelNo
                if channelNo in channelsInEPG:
                    logger.error("duplicate channelNo: %s", channelNo)

                channelsInEPG[channelNo] = False
                for icon in child.iter("icon"):
                    # check if icon exists (tvh always returns an URL even if there is no channel icon)
                    iconUrl = icon.attrib["src"]
                    r = requests.head(iconUrl)
                    if r.status_code != requests.codes.ok:
                        logger.error("remove icon: %s", iconUrl)
                        child.remove(icon)

                child.attrib["id"] = channelNo
            if child.tag == "programme":
                channelUuid = child.attrib["channel"]
                channelNumber = channelNumberMapping[channelUuid]
                channelsInEPG[channelNumber] = True
                child.attrib["channel"] = channelNumber
                start_datetime = (
                    datetime.strptime(child.attrib["start"], "%Y%m%d%H%M%S %z")
                    .astimezone(tz=None)
                    .replace(tzinfo=None)
                )
                stop_datetime = (
                    datetime.strptime(child.attrib["stop"], "%Y%m%d%H%M%S %z")
                    .astimezone(tz=None)
                    .replace(tzinfo=None)
                )
                if (
                    stop_datetime > datetime.now()
                    and start_datetime < datetime.now() + timedelta(hours=72)
                ):
                    # add extra details for programs in the next 72hs
                    start_timestamp = int(round(datetime.timestamp(start_datetime)))
                    epg_event = epg_events[channelUuid][start_timestamp]
                    if "image" in epg_event:
                        programmeImage = ElementTree.SubElement(child, "icon")
                        imageUrl = str(epg_event["image"])
                        if imageUrl.startswith("imagecache"):
                            imageUrl = config["tvhURL"] + "/" + imageUrl + ".png"
                        programmeImage.attrib["src"] = imageUrl
                    if "genre" in epg_event:
                        for genreId in epg_event["genre"]:
                            for category in genres[genreId]:
                                programmeCategory = ElementTree.SubElement(
                                    child, "category"
                                )
                                programmeCategory.text = category
                    if "episodeOnscreen" in epg_event:
                        episodeNum = ElementTree.SubElement(child, "episode-num")
                        episodeNum.attrib["system"] = "onscreen"
                        episodeNum.text = epg_event["episodeOnscreen"]
                    if "hd" in epg_event:
                        video = ElementTree.SubElement(child, "video")
                        quality = ElementTree.SubElement(video, "quality")
                        quality.text = "HDTV"
                    if "new" in epg_event:
                        ElementTree.SubElement(child, "new")
                    else:
                        ElementTree.SubElement(child, "previously-shown")
                    if "copyright_year" in epg_event:
                        date = ElementTree.SubElement(child, "date")
                        date.text = str(epg_event["copyright_year"])
                    del epg_events[channelUuid][start_timestamp]
        for key in sorted(channelsInEPG):
            if channelsInEPG[key]:
                logger.debug("Programmes found for channel %s", key)
            else:
                channelName = root.find('channel[@id="' + key + '"]/display-name').text
                logger.error("No programme for channel %s: %s", key, channelName)
                # create 2h programmes for 72 hours
                yesterday_midnight = datetime.combine(
                    datetime.today(), time.min
                ) - timedelta(days=1)
                date_format = "%Y%m%d%H%M%S"
                for x in range(0, 36):
                    dummyProgramme = ElementTree.SubElement(root, "programme")
                    dummyProgramme.attrib["channel"] = str(key)
                    dummyProgramme.attrib["start"] = (
                        yesterday_midnight + timedelta(hours=x * 2)
                    ).strftime(date_format)
                    dummyProgramme.attrib["stop"] = (
                        yesterday_midnight + timedelta(hours=(x * 2) + 2)
                    ).strftime(date_format)
                    dummyTitle = ElementTree.SubElement(dummyProgramme, "title")
                    dummyTitle.attrib["lang"] = "eng"
                    dummyTitle.text = channelName
                    dummyDesc = ElementTree.SubElement(dummyProgramme, "desc")
                    dummyDesc.attrib["lang"] = "eng"
                    dummyDesc.text = "No programming information"
        logger.info("returning epg")
        return ElementTree.tostring(root)
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        logger.error("An error occured: " + repr(e))
        raise e


def _start_ssdp():
    ssdp = SSDPServer()
    thread_ssdp = threading.Thread(target=ssdp.run, args=())
    thread_ssdp.daemon = True  # Daemonize thread
    thread_ssdp.start()
    ssdp.register(
        "local",
        "uuid:{}::upnp:rootdevice".format(discoverData["DeviceID"]),
        "upnp:rootdevice",
        "http://{}:{}/device.xml".format(
            config["tvhProxyHost"], config["tvhProxyPort"]
        ),
        "SSDP Server for tvhProxy",
    )

def main():
    http = WSGIServer(
        (config["bindAddr"], int(config["tvhProxyPort"])),
        app.wsgi_app,
        log=logger,
        error_log=logger,
    )
    _start_ssdp()
    http.serve_forever()

if __name__ == "__main__":
    main()

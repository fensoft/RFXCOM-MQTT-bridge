import json
import logging
import paho.mqtt.client as mqtt
from RFXtrx import PySerialTransport, SensorEvent, ControlEvent, StatusEvent
import RFXtrx.lowlevel
from settings import *

loglevel = logging.getLevelName(LOGLEVEL)
logging.basicConfig(level=loglevel)

def flatten_json(nested_json, separator='/'):
    out = {}
    def flatten(x, name=''):
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + separator)
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + separator)
                i += 1
        else:
            out[name[:-1]] = x
    flatten(nested_json)
    return out

def on_connect(client, userdata, flags, rc):
    logging.info("MQTT Connected with result code " + str(rc) + ": " + mqtt.connack_string(rc))
    connect_topic = MQTT_PREFIX + "/status"
    mqtt_client.publish(connect_topic, "Online!")
    client.subscribe(MQTT_PREFIX + "/#")

def on_message(client, userdata, msg):
    topics = msg.topic.split("/")
    if topics[-1] == "set":
        try:
            value = int(msg.payload.decode("utf-8"))
        except:
            value = msg.payload.decode("utf-8")
        action = topics[-2]
        code = name_to_id(topics[-3]).split(":")
        packettype = topics[-4].split(":")[0]
        subtype = topics[-4].split(":")[1]
        if packettype == "17" and action == "Command":
            pkt = RFXtrx.lowlevel.Lighting2()
            pkt.id_combined = int(code[0],16)
            pkt.unitcode = int(code[1])
            pkt.subtype = int(subtype)
            pkt.packettype = int(packettype)
            device = RFXtrx.LightingDevice(pkt)
            if value == 0 or (type(value) is str and value.lower() == "off"):
                device.send_off(transport)
            elif value == 100 or (type(value) is str and value.lower() == "on"):
                device.send_on(transport)
            else:
                device.send_dim(transport, value)


transport = PySerialTransport(RFX_PORT, debug=RFX_DEBUG)

mqtt_client = mqtt.Client()  # Create the client
mqtt_client.on_connect = on_connect  # Callback on when connected
mqtt_client.on_message = on_message  # Callback when message received
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)  # Set user and pw
mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)  # Connect the MQTT Client

mqtt_client.loop_start()

def id_to_name(id_string):
    if id_string in CONVERTDICT.keys():
        return CONVERTDICT[id_string]
    return id_string

def name_to_id(id_string):
    rev = dict(map(reversed, CONVERTDICT.items()))
    if id_string in rev.keys():
        return rev[id_string]
    return id_string

while True:
    event = transport.receive_blocking()

    if event is None:
        continue

    logging.debug(event)
    if isinstance(event, SensorEvent) or isinstance(event, ControlEvent):
        for key, val in flatten_json(event.values).items():
            mqtt_client.publish("{}/{}:{}/{}/{}".format(MQTT_PREFIX, event.device.packettype, event.device.subtype, id_to_name(event.device.id_string), key), val, retain=True)

    if isinstance(event, StatusEvent):
        mqtt_topic = MQTT_PREFIX + "/status"
        logging.error("Statusevent: " + str(event))
        mqtt_client.publish(mqtt_topic, "StatusEvent received, cannot handle: " + str(event))

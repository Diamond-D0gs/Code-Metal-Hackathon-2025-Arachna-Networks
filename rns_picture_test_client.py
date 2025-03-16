import cv2
import RNS
import time
import math
import pickle
import numpy as np

class announce_handler:
    def __init__(self):
        self.aspect_filter = "Code-Metal-Demo-2025"
        self.server_destination = None

    def received_announce(self, destination_hash, announced_identity, app_data):
        if self.server_destination is None:
            self.server_destination = RNS.Destination(announced_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "Code-Metal-Demo-2025")

reticulum = RNS.Reticulum()

rnode_interface = RNS.Interfaces.RNodeInterface.RNodeInterface(
    RNS.Transport,
    {
        "name": "RnodeInterface",
        "port": "/dev/ttyUSB0",
        "frequency": 915000000,
        "bandwidth": 500000,
        "txpower": 0,
        "spreadingfactor": 7,
        "codingrate": 5
    }
)

rnode_interface.OUT = True
reticulum._add_interface(rnode_interface)

rns_identity = RNS.Identity()

client_destination = RNS.Destination(rns_identity, RNS.Destination.IN, RNS.Destination.SINGLE, "Code-Metal-Demo-2025")

curr_announce_handler = announce_handler()
RNS.Transport.register_announce_handler(curr_announce_handler)

while curr_announce_handler.server_destination is None:
    time.sleep(0.1)

RNS.Transport.deregister_announce_handler(curr_announce_handler)

link_established = False
def link_established_callback(link):
    link_established = True

PACKET_DATA_SIZE = RNS.Packet.ENCRYPTED_MDU - 4

image_data = [None]
new_image = [False]
payloads_in_progress = {}
packets_accumulated = {}
def packet_callback(message, packet):
    payload_id = int.from_bytes(message[0:2])
    payload_packet_count = int.from_bytes(message[2:3])
    payload_packet_index = int.from_bytes(message[3:4])
    packet_data = message[4:]

    if payload_id in payloads_in_progress:
        payloads_in_progress[payload_id][payload_packet_index] = packet_data
        packets_accumulated[payload_id] += 1
    else:
        payloads_in_progress[payload_id] = [None] * payload_packet_count
        payloads_in_progress[payload_id][payload_packet_index] = packet_data
        packets_accumulated[payload_id] = 1

    if packets_accumulated[payload_id] == payload_packet_count:
        payload_data = b''
        for packet_index in range(len(payloads_in_progress[payload_id])):
            payload_data += payloads_in_progress[payload_id][packet_index]

        del payloads_in_progress[payload_id]
        del packets_accumulated[payload_id]
        
        raw_jpeg_data = np.frombuffer(payload_data, dtype=np.uint8)
        image_data[0] = cv2.imdecode(raw_jpeg_data, cv2.IMREAD_UNCHANGED)
        new_image[0] = True

        RNS.Packet(rns_link, b'').send()
    
rns_link = RNS.Link(curr_announce_handler.server_destination, established_callback=link_established_callback)
rns_link.set_packet_callback(packet_callback)

print("Establishing link...")

while True:
    if new_image[0]:
        cv2.imshow('Client', image_data[0])
        new_image[0] = False
        #cv2.waitKey(100)
    else:
        cv2.pollKey()
    time.sleep(0.1)
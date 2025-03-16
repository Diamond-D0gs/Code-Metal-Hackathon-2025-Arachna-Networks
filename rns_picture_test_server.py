import cv2
import RNS
import time
import math
import pickle

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
rns_destination = RNS.Destination(rns_identity, RNS.Destination.IN, RNS.Destination.SINGLE, "Code-Metal-Demo-2025")
rns_destination.accepts_links(True)

class link_class:
    def __init__(self):
        self.done_packet_received = False
        self.link: RNS.Link = None

    def packet_callback(self, message, packet):
        self.done_packet_received = True

    def link_callback(self, link):
        self.link = link
        self.link.set_packet_callback(self.packet_callback)

curr_link_class = link_class()
rns_destination.set_link_established_callback(curr_link_class.link_callback)

while curr_link_class.link is None:
    rns_destination.announce()
    time.sleep(2)

rns_link = curr_link_class.link

HEADER_SIZE = 4
DATA_SIZE = RNS.Packet.ENCRYPTED_MDU - HEADER_SIZE
RETAKE_TIME_SEC = 20

payload_index: int = 0
prev_time: float = time.time()
while True:
    cam = cv2.VideoCapture(0)
    ret, frame = cam.read()
    cam.release()

    result, jpg_img_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 10])
    
    packet_data_sizes = []
    jpg_data_bytes = jpg_img_data.tobytes()
    payload_packet_count = int(math.ceil(len(jpg_data_bytes) / DATA_SIZE))
    for payload_packet_index in range(0, payload_packet_count):
        data_start: int = payload_packet_index * DATA_SIZE
        data_end: int = data_start + min(DATA_SIZE, len(jpg_data_bytes) - data_start)
        
        packet_data = payload_index.to_bytes(2)
        packet_data += payload_packet_count.to_bytes(1)
        packet_data += payload_packet_index.to_bytes(1)
        packet_data += jpg_data_bytes[data_start:data_end]
        
        RNS.Packet(rns_link, packet_data).send()

        time.sleep(0.7)

    payload_index += 1

    while not curr_link_class.done_packet_received:
        curr_link_class.done_packet_received = False
        time.sleep(0.1)

    sleep_time = RETAKE_TIME_SEC - (time.time() - prev_time)
    time.sleep(max(0, sleep_time))
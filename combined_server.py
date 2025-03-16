import cv2
import RNS
import time
import math
import socket
import numpy as np

HEADER_SIZE = 4
LORA_SEND_RATE_SEC = 20
SOCKET_SEND_RATE_SEC = 0.03333
DATA_SIZE = RNS.Packet.ENCRYPTED_MDU - HEADER_SIZE

SERVER_IP = 'localhost'

class combined_sever:
    def __init__(self):
        self.reticulum = None
        self.rns_identity = None
        self.rns_destination = None
        self.rns_link = None
        self.payload_index = 0
        self.server_socket = None
        self.client_socket = None
        self.done_packet_received = False

    def packet_callback(self, message, packet):
        self.done_packet_received = True

    def link_established_callback(self, link):
        self.rns_link = link
        self.link.set_link_established_callback(self.packet_callback)

    def init_reticulum(self):
        self.reticulum = RNS.Reticulum()
        self.rns_identity = RNS.Identity()

        rnode_interface = RNS.Interfaces.RNodeInterface.RNodeInterface(
            RNS.Transport,
            {
                "name": "RnodeInterface",
                "port": "COM4",
                "frequency": 915000000,
                "bandwidth": 500000,
                "txpower": 0,
                "spreadingfactor": 7,
                "codingrate": 5
            }
        )

        rnode_interface.OUT = True
        self.reticulum._add_interface(rnode_interface)

        self.rns_destination = RNS.Destination(self.rns_identity, RNS.Destination.IN, RNS.Destination.SINGLE, "Code-Metal-Demo-2025")
        self.rns_destination.set_link_established_callback(self.link_established_callback)
        self.rns_destination.accepts_links(True)

        while self.rns_link is None:
            self.rns_destination.announce()
            time.sleep(2)

    def init_socket(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((SERVER_IP, 8888))
        self.server_socket.listen(5)
        self.client_socket, client_address = self.server_socket.accept()

    def send_lora(self, raw_image_data):
        jpg_img_data = cs2.imencode(raw_image_data, [cv2.IMWRITE_JPEG_QUALITY, 10])
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

        while not self.done_packet_received:
            self.done_packet_received = False
            time.sleep(0.1)

    def send_socket(self, raw_image_data):
        jpg_img_data = cv2.imencode(raw_image_data, [cv2.IMWRITE_JPEG_QUALITY, 80])
        jpg_data_bytes = jpg_img_data.tobytes()
        self.client_socket.sendall(len(jpg_img_bytes).to_bytes(4))
        self.client_socket.sendall(jpg_img_bytes)

    def run(self):
        self.init_socket()
        self.init_reticulum()

        cam = cv2.VideoCapture(0)
        current_time = time.time()
        socket_accumulator = 0
        lora_accumulator = 0
        while True:
            result, raw_image_data = cam.read()
            
            old_time = current_time
            current_time = time.time()
            delta_time = current_time - old_time
            socket_accumulator += delta_time
            lora_accumulator += delta_time

            if socket_accumulator >= SOCKET_SEND_RATE_SEC:
                self.send_socket(raw_image_data)
                socket_accumulator = 0

            if (lora_accumulator >= LORA_SEND_RATE_SEC) and self.done_packet_received:
                self.send_lora(raw_image_data)
                lora_accumulator = 0
        
        return

combined_sever().run()
import cv2
import RNS
import time
import math
import socket
import numpy as np

PACKET_DATA_SIZE = RNS.Packet.ENCRYPTED_MDU - 4

CLIENT_IP = 'localhost'

class combined_client:
    def __init__(self):
        self.aspect_filter = "Code-Metal-Demo-2025"
        self.server_destination = None
        self.reticulum = None
        self.rns_identity = None
        self.client_destination = None
        self.link_established = False
        self.rns_link = None
        self.new_lora_image = False
        self.new_socket_image = False
        self.lora_image_data = None
        self.socket_image_data = None
        self.payloads_in_progress = {}
        self.packets_accumulated = {}
        self.client_socket = None
        self.socket_accumulated_data = b''
        self.socket_data_size = 0

    def link_established_callback(self):
        self.link_established = True

    def received_announce(self, destination_hash, announced_identity, app_data):
        if self.server_destination is None:
            self.server_destination = RNS.Destination(announced_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "Code-Metal-Demo-2025")
            self.rns_link = RNS.Link(self.server_destination, established_callback=self.link_established_callback)

    def packet_callback(message, packet):
        payload_id = int.from_bytes(message[0:2])
        payload_packet_count = int.from_bytes(message[2:3])
        payload_packet_index = int.from_bytes(message[3:4])
        packet_data = message[4:]

        if payload_id in self.payloads_in_progress:
            self.payloads_in_progress[payload_id][payload_packet_index] = packet_data
            self.packets_accumulated[payload_id] += 1
        else:
            self.payloads_in_progress[payload_id] = [None] * payload_packet_count
            self.payloads_in_progress[payload_id][payload_packet_index] = packet_data
            self.packets_accumulated[payload_id] = 1

        if self.packets_accumulated[payload_id] == payload_packet_count:
            payload_data = b''
            for packet_index in range(len(self.payloads_in_progress[payload_id])):
                payload_data += self.payloads_in_progress[payload_id][packet_index]

            del self.payloads_in_progress[payload_id]
            del self.packets_accumulated[payload_id]
            
            raw_jpeg_data = np.frombuffer(payload_data, dtype=np.uint8)
            self.lora_image_data = cv2.imdecode(raw_jpeg_data, cv2.IMREAD_UNCHANGED)
            self.new_lora_image = True

            RNS.Packet(rns_link, b'').send()

    def init_reticulum(self):
        self.reticulum = RNS.Reticulum()

        self.rns_identity = RNS.Identity()

        rnode_interface = RNS.Interfaces.RNodeInterface.RNodeInterface(
            RNS.Transport,
            {
                "name": "RnodeInterface",
                "port": "/dev/ttyUSB1",
                "frequency": 915000000,
                "bandwidth": 500000,
                "txpower": 0,
                "spreadingfactor": 7,
                "codingrate": 5
            }
        )

        rnode_interface.OUT = True
        self.reticulum._add_interface(rnode_interface)

        self.client_destination = RNS.Destination(self.rns_identity, RNS.Destination.IN, RNS.Destination.SINGLE, "Code-Metal-Demo-2025")

        RNS.Transport.register_announce_handler(self)

        while not self.link_established:
            time.sleep(0.1)

        RNS.Transport.deregister_announce_handler(self)

    def init_socket(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((CLIENT_IP, 8888))

    def check_socket(self):
        if len(self.socket_accumulated_data) < 4:
            packet = self.client_socket.recv(4096)
            if not packet:
                return
            data += packet
        if not self.socket_accumulated_data:
            return

        self.socket_data_size = int.to_bytes(data[:4])
        self.socket_accumulated_data = self.socket_accumulated_data[4:]
        
        while len(data) < self.socket_data_size:
            data += self.client_socket.recv(4096)

        jpg_data_bytes = self.socket_image_data[:self.socket_data_size]
        raw_jpeg_data = np.frombuffer(jpg_data_bytes, dtype=np.uint8)
        self.lora_image_data = cv2.imdecode(raw_jpeg_data, cv2.IMREAD_UNCHANGED)
        self.new_lora_image = True

        self.socket_image_data = b''
        self.socket_data_size = 0


    def run(self):
        self.init_socket()
        self.init_reticulum()
        #time.sleep(10)

        while True:
            self.check_socket()

            if self.new_lora_image:
                cv2.imshow('LoRa Stream', self.lora_image_data)
                self.new_lora_image = False
            if self.new_socket_image:
                cv2.imshow('Wi-Fi Stream', self.socket_image_data)
                self.socket_image_data = False

            cv2.pollKey()

            time.sleep(0.1)

combined_client().run()

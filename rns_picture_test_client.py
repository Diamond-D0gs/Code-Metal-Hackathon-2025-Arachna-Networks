import cv2
import RNS
import time
import numpy as np

# The announce handler object is responsible for behaving as a callback to announcements from other Reticulum destinations.
# The aspect filter attribute means that this announce handler will only respond the announcements containing those aspects.
# In this instance we are using the announce handler as a means of retrieving the server's destination.
class announce_handler:
    def __init__(self):
        self.aspect_filter = "Code-Metal-Demo-2025"
        self.server_destination = None # This attribute will hold the server destination once it arrives.

    def received_announce(self, destination_hash, announced_identity, app_data):
        if self.server_destination is None:
            self.server_destination = RNS.Destination(announced_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "Code-Metal-Demo-2025")
            # "announced_identity" contains the public key of the server's destination.
            # "RNS.Destination.OUT" means that this destination is for outgoing traffic.
            # "RNS.Destination.SINGLE" means this destination connects to only one other destination.
            # "Code-Metal-Demo-2025" is an aspect used to label the announces of the destination. Ties into the "aspect_filter".

# Initialize RNS by creating a Reticulum instance.
reticulum = RNS.Reticulum()

# Manually create the RNode interface by instantating its interface class and passing radio parameters.
# Interfaces typically do not have to be created manually as they can be specified in Reticulum's config file,
# but we chose to manually create our interface here for control reasons.
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

rnode_interface.OUT = True # All manually created interfaces must have their "OUT" attribute set to true or they will not transmit and function.
reticulum._add_interface(rnode_interface) # Add the newely created interface to the Reticulum instance.

rns_identity = RNS.Identity() # A locally created identity will hold the public and private keys for the instance.

# Create the client's destination for the server to connect to.
# "RNS.Destination.IN" means that this destination is for incoming traffic.
client_destination = RNS.Destination(rns_identity, RNS.Destination.IN, RNS.Destination.SINGLE, "Code-Metal-Demo-2025")

# Instantiate the announce handler and register it with the Transport class' announce handler.
# All announcements, regardless of the interface or destination are aggregated through the Transport class.
curr_announce_handler = announce_handler()
RNS.Transport.register_announce_handler(curr_announce_handler)

# Poll and wait until we've established a connection to the server.
while curr_announce_handler.server_destination is None:
    time.sleep(0.1)

# Remove the announce handler from the announce handler, it's no longer needed.
RNS.Transport.deregister_announce_handler(curr_announce_handler)

# This callback will serve as a wait for Link establishment.
# A Link in RNS represents a lower overhead point to point tunnel with in the mesh network over multiple hops for higher throughput data transfer.
link_established = False
def link_established_callback(link):
    link_established = True

# Data has to fit within the size of an RNS packet (383 bytes if encrypted).
# The payload is larger than the size of a single packet, meaning the server must dice the payload,
# and send it as sequenced chunks that the client will reconstruct back into the payload
# once all chunks have been received.
PACKET_DATA_SIZE = RNS.Packet.ENCRYPTED_MDU - 4 # Sequence data will take up 4 bytes. 2 bytes for payload id, 1 byte for chunk id, and 1 byte for chunk count.

image_data = [None] # A temporary buffer for storing completed payload data. It is a list to allow mutability by the "packet_callback" method.
new_image = [False] # A flag that indicates if a new image is ready to be displayed. It is a list for the same reasons above.
payloads_in_progress = {} # Dictionary that stores the collected chunks from the sequenced payload chunk packets for a given payload id.
packets_accumulated = {} # Dictionary that stores how many chunks have been collected from a sequence for a given payload id.
def packet_callback(message, packet):
    payload_id = int.from_bytes(message[0:2])
    payload_packet_count = int.from_bytes(message[2:3])
    payload_packet_index = int.from_bytes(message[3:4])
    packet_data = message[4:]

    if payload_id in payloads_in_progress: # Extract and store chunk, increment accumulation count, if payload_id is registered.
        payloads_in_progress[payload_id][payload_packet_index] = packet_data
        packets_accumulated[payload_id] += 1
    else: # Allocate list to hold chunk data buffers, store first received chunk, and register payload id.
        payloads_in_progress[payload_id] = [None] * payload_packet_count
        payloads_in_progress[payload_id][payload_packet_index] = packet_data
        packets_accumulated[payload_id] = 1

    # Once all the chunks have been received for a payload, piece them back together in the proper order in a new byte array.
    if packets_accumulated[payload_id] == payload_packet_count:
        payload_data = b''
        for packet_index in range(len(payloads_in_progress[payload_id])):
            payload_data += payloads_in_progress[payload_id][packet_index]

        # Clear the completed entries out of the dictionary to prevent memory leaks.
        del payloads_in_progress[payload_id]
        del packets_accumulated[payload_id]

        # Decode the jpeg data from the payload into a raw RGB image and indicate it's ready to be displayed.
        raw_jpeg_data = np.frombuffer(payload_data, dtype=np.uint8)
        image_data[0] = cv2.imdecode(raw_jpeg_data, cv2.IMREAD_UNCHANGED)
        new_image[0] = True

        # Notify the server that you're ready to receive another payload.
        RNS.Packet(rns_link, b'').send()

# Retrieve the server's destination from the announce handler, establish a link, and set the callbacks for
# link establishment and packet received.
rns_link = RNS.Link(curr_announce_handler.server_destination, established_callback=link_established_callback)
rns_link.set_packet_callback(packet_callback)

print("Establishing link...")

# Main loop of the client, wait for a raw image to be displayed, display it once if it arrives, 
# else run the message loop for the CV2 window and sleep for 100ms.
while True:
    if new_image[0]:
        cv2.imshow('Client', image_data[0])
        new_image[0] = False
    else:
        cv2.pollKey()
    time.sleep(0.1)

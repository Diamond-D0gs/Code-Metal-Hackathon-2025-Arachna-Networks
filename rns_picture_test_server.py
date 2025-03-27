import cv2
import RNS
import time
import math

# Initalize RNS by creating a Reticulum instance.
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

# "RNS.Destination.IN" means that this destination is for incoming traffic.
# "RNS.Destination.SINGLE" means this destination connects to only one other destination.
# "Code-Metal-Demo-2025" is an aspect used to label the announces of the destination. Ties into the "aspect_filter" on the client end.
rns_destination = RNS.Destination(rns_identity, RNS.Destination.IN, RNS.Destination.SINGLE, "Code-Metal-Demo-2025")
rns_destination.accepts_links(True) # Allows the destination to establish a link with the requestee.
# A Link in RNS represents a lower overhead point to point tunnel with in the mesh network over multiple hops for higher throughput data transfer.

# This class serves to hold the callbacks and flags that will be associated with our link.
class link_class:
    def __init__(self):
        self.done_packet_received = False # A flag that will be tripped that signals the main loop to proceed.
        self.link: RNS.Link = None # Where the main loop will retrieve the link reference from.

    # The client only sends an empty packet to the server to indicate it's done with the current payload
    # and is ready to receive another. 
    def packet_callback(self, message, packet):
        self.done_packet_received = True

    # This callback is called once the link has been successfully established with the client.
    def link_callback(self, link):
        self.link = link
        self.link.set_packet_callback(self.packet_callback) # Bind the packet callback to the newly created link.

curr_link_class = link_class() # Instantiate the the link object and bind its link establishment method to the server's destination.
rns_destination.set_link_established_callback(curr_link_class.link_callback)

# Wait for a client to receive the server's announcement and establish a link. Sleep 2 seconds to between announcements to avoid spam.
while curr_link_class.link is None:
    rns_destination.announce()
    time.sleep(2)

# Data has to fit within the size of an RNS packet (383 bytes if encrypted).
# The payload is larger than the size of a single packet, meaning the server must dice the payload,
# and send it as sequenced chunks that the client will reconstruct back into the payload
# once all chunks have been received.
HEADER_SIZE = 4 
PACKET_DATA_SIZE = RNS.Packet.ENCRYPTED_MDU - HEADER_SIZE # Sequence data will take up 4 bytes. 2 bytes for payload id, 1 byte for packet count, and 1 byte for packet index.
RETAKE_TIME_SEC = 20 # Had to set a conservatively high retake time due to technical issues encountered during the hackathon we didn't have time to resolve.
FRAMES_IN_FLIGHT = 3

payload_index = 0 # Each payload has an index for tracking by the client when reconstructing the chunked payload.
prev_time = time.time() # Keep a track of time between transmissions to maintain cadence of frames sent.
while True:
    # Open the webcam, read a frame, and close it (leaving it open will not give you the latest frame).
    cam = cv2.VideoCapture(0)
    ret, frame = cam.read()
    cam.release()

    # Encode the raw RGB frame data into JPEG.
    result, jpg_img_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 10])
    
    jpg_data_bytes = jpg_img_data.tobytes() # Convert from numpy array to bytes array.
    payload_packet_count = int(math.ceil(len(jpg_data_bytes) / PACKET_DATA_SIZE)) # Calculate how many packets will be required to send.
    for payload_packet_index in range(0, payload_packet_count): 
        data_start = payload_packet_index * PACKET_DATA_SIZE
        data_end = data_start + min(PACKET_DATA_SIZE, len(jpg_data_bytes) - data_start) # Bounds us within the range of the JPEG data.
        
        packet_data = payload_index.to_bytes(2) # Payload ID
        packet_data += payload_packet_count.to_bytes(1) # Number of packets in payload.
        packet_data += payload_packet_index.to_bytes(1) # Index of current packet in payload.
        packet_data += jpg_data_bytes[data_start:data_end] # Data chunk.
        
        RNS.Packet(curr_link_class.link, packet_data).send() # Send the packet data through the link.

        # SX1262 based RNodes can only handle ~3 packets being dispatched back to back
        # before needing to throttle; else the radio will begin dropping packets and possibly crash.
        if i >= FRAMES_IN_FLIGHT:
            time.sleep(0.65) #Functional delay time based on emperical tests (650ms).
        RNS.Packet(rns_link, packet_data).send() # Send the packet data through the link.

        # SX1262 based RNodes can only handle ~3 packets being dispatched back to back
        # before needing to throttle; else the radio will begin dropping packets and possibly crash.
        if i >= FRAMES_IN_FLIGHT:
            time.sleep(0.65) #Functional delay time based on emperical tests (650ms).

    payload_index += 1

    # Wait until the client has indicated that it is finished with the current payload.
    while not curr_link_class.done_packet_received:
        time.sleep(0.1)

    # Reset the flag for the next payload.
    curr_link_class.done_packet_received = False

    # Calculate the delta time between frames with respect to the retake period.
    curr_time = time.time()
    sleep_time = RETAKE_TIME_SEC - (curr_time - prev_time)
    prev_time = curr_time

    time.sleep(max(0, sleep_time)) # Skip sleeping if we're over the retake period (negative sleep times cause an exception too).

# UDP Server Script to listen for incoming UPD packets.


# Problems: What confirmation message should the server send? Probably the same message it received or the equipment code.


import socket


import player_entry


import json


import os


import UDP_Client


localIP = "0.0.0.0"


localPort = 7501


broadcastPort = 7500


bufferSize = 1024


msgFromServer = None


HARDWARE_TEAM_PAIR_FILE = "hardware_team.json"


last_mtime = 0  # This will store the last modified time of the json file


shut_down_counter = 3


# bytesToSend = str.encode(msgFromServer)


# Create a datagram socket for localPort


UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)


# Create a datagram socket for broadcastPort


UDPBroadcastSocket = socket.socket(















    family=socket.AF_INET, type=socket.SOCK_DGRAM)


# Allow immediate reuse of address


UDPServerSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


UDPBroadcastSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


# Enable broadcast (only once, not inside the loop)


UDPBroadcastSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)


# Bind to address and ip


UDPServerSocket.bind((localIP, localPort))


# Load hardware-team mapping from JSON for friendly fire checks


def load_hardware_team_mapping():

    global last_mtime

    try:

        # This will obtain the most recent modified time of the json file

        curr_mtime = os.path.getmtime(HARDWARE_TEAM_PAIR_FILE)

        if curr_mtime != last_mtime:  # file has changed

            with open(HARDWARE_TEAM_PAIR_FILE, "r") as f:

                player_entry.HARDWARE_TEAM_PAIR = json.load(f)

            last_mtime = curr_mtime

    except FileNotFoundError:

        print("No hardware-team mapping found.")

    except Exception as e:

        print("Error loading hardware-team mapping:", e)


# Function to compare attacker and target to determine if friendly fire occurred


def check_friendly_fire(attacker, target, hardware_team_pair):

    try:

        return hardware_team_pair.get(attacker) == hardware_team_pair.get(target)

    except Exception as e:

        print("Friendly fire check error:", e)

        return False


def shut_down_server(message):

    global shut_down_counter

    if message == "221":

        shut_down_counter -= 1

        if shut_down_counter == 0:

            UDPServerSocket.close()

            UDPBroadcastSocket.close()

            return True

    return False


print("UDP server up and listening")


# Listen for incoming datagrams


try:

    while (True):

        # Load the hardware-team mapping at the start of each loop

        load_hardware_team_mapping()

        # Load server address from json file at the start of each loop

        UDP_Client.load_SERVER_ADDRESS()

        SERVER_ADDRESS = UDP_Client.SERVER_ADDRESS

        bytesAddressPair = UDPServerSocket.recvfrom(bufferSize)

        message_bytes = bytesAddressPair[0]

        address = bytesAddressPair[1]

        # Decode bytes to string

        message = message_bytes.decode()

        clientMsg = "Client Message: {}".format(message)

        clientIP = "Client IP Address: {}".format(address)

        print(clientMsg)

        print(clientIP)

        # If there there is a colon, the message received is a hit

        if ":" in message:

            attacker, target = message.split(":")

            # If check_friendly_fire is true, then broadcast codes for friendly fire hit, else broadcast normal hit

            if check_friendly_fire(attacker, target, player_entry.HARDWARE_TEAM_PAIR):

                # Attacker of the same team

                UDPBroadcastSocket.sendto(str.encode(















                    attacker), (SERVER_ADDRESS[0], broadcastPort))

                # Target

                UDPBroadcastSocket.sendto(str.encode(















                    target), (SERVER_ADDRESS[0], broadcastPort))

                # Send whole message to traffic generator

                UDPBroadcastSocket.sendto(



                    message_bytes, (SERVER_ADDRESS[0], 7502))

            else:

                # Broadcast only target for normal hit

                UDPBroadcastSocket.sendto(str.encode(















                    target), (SERVER_ADDRESS[0], broadcastPort))

                # Send whole message to traffic generator

                UDPBroadcastSocket.sendto(



                    message_bytes, (SERVER_ADDRESS[0], 7502))

        else:

            # Debugging print statement -----------------------------------------------------------------------------------------------------------------

            # print("HARDWARE_TEAM_PAIR contents:")

            # if player_entry.HARDWARE_TEAM_PAIR:

            #     for key, value in player_entry.HARDWARE_TEAM_PAIR.items():

            #         print(f"{key} -> {value}")

            # else:

            #     print("<empty dict>")

            # --------------------------------------------------------------------------------------------------------------------------------------------

            # Prepare reply message

            msgFromServer = clientMsg

            bytesToSend = str.encode(msgFromServer)

            # This was an optional step for testing: Sending a reply to client with the same message it sent.

            # -------------------------------------------------------------------------------------------------------

            # Sending a reply to client

            # replace second part with address for UDP_client testing

            # UDPServerSocket.sendto(bytesToSend, address)

            # -------------------------------------------------------------------------------------------------------

            # Also broadcast to traffic generator

            # message_bytes to send exactly what the client sent

            UDPBroadcastSocket.sendto(







                message_bytes, (SERVER_ADDRESS[0], broadcastPort))

            if shut_down_server(message):

                break


except KeyboardInterrupt:

    print("UDP server manually stoppped.")

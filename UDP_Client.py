# Summary: This code defines a UDP client that allows the user to select between local or broadcast network.


# To send the equipment code to the server, call get_equipment_code(equipment_code).


# Where do I call get_equipment_code()? Call it from another script where you want to send the code.


# Importations


import socket


import atexit


import json


# Global variable to store server address


SERVER_ADDRESS = None


# Create a UDP socket at client side (socket() is a class from socket module, creates object)


UDPClientSocket = socket.socket(















    # Creates single socket for entire program



    family=socket.AF_INET, type=socket.SOCK_DGRAM)


# enable broadcasts


UDPClientSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)


# Function to select a server network


def select_network():

    while True:

        print("Select the server network to connect to: ")

        print("1. Local Network (Default)")

        print("2. Select personalized network")

        choice = input("Select option (1 or 2): ")

        # Switch statement (match in python)

        if choice == '1':

            return ("127.0.0.1", 7501)

        elif choice == '2':

            address = input("Enter you network address: ")

            return (address, 7501)

        else:

            print("Invalid choice. Try again.\n")

            print("----------------------------\n")


# Configure server once at startup and store in global variable


def configure_server():

    global SERVER_ADDRESS

    SERVER_ADDRESS = select_network()

    save_SERVER_ADDRESS()


# Function to save Server address in a json file


def save_SERVER_ADDRESS():

    global SERVER_ADDRESS

    with open('server_address.json', 'w') as f:

        json.dump(SERVER_ADDRESS, f)


# Function to load Server address from a json file


def load_SERVER_ADDRESS():

    global SERVER_ADDRESS

    try:

        with open('server_address.json', 'r') as f:

            SERVER_ADDRESS = tuple(json.load(f))

    except FileNotFoundError:

        print("No server address found. Please configure the server.")


# Function to get equipment code and handle any future logic.


def get_equipment_code(equipment_code):

    code = equipment_code

    # Add future logic to validate code, such as check if digit, save to database, etc.

    # Send code to server

    send_packet(code)

    return code


# This function gets the data, encodes it, creates a UDP socket, and send the data


def send_packet(data):

    # Check if the server address is configured, else prints error and returns

    if SERVER_ADDRESS is None:

        print("ERROR: Server address not configured.")

        return

    # variable containing the message to send to the server

    msgFromClient = data

    # Encode the message to bytes!

    # bytesToSend = str.encode(msgFromClient)

    bytesToSend = str(msgFromClient).encode()

    # Defines the buffer size at 1KB or 1024 bytes

    bufferSize = 1024

    # Send to server using created UDP socket

    UDPClientSocket.sendto(bytesToSend, SERVER_ADDRESS)

    # Receive response from server

    # msgFromServer = UDPClientSocket.recvfrom(

    #     bufferSize)  # [0] is network, [1] is port

    # server_sender_port = msgFromServer[1]

    # # decode the bytes to a normal string

    # msg_decoded = msgFromServer[0].decode()

    # # now format the message

    # msg = "Message from Server: {}".format(msg_decoded)

    # # Print message from server

    # print(msg)

    # print("Server received from port:  ", SERVER_ADDRESS[1])

    # print("Server sender port: ", server_sender_port)


# Close the socket automatically on program exit
atexit.register(UDPClientSocket.close)

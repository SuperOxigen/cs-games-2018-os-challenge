#! /usr/bin/python3
"""CS Games 2018 - System Challenge Tester."""

import argparse
import os
import os.path
import errno
import random
import socket
import subprocess
import sys
import time


DATA_DIRECTORY = "data"


class RequestPacket(object):
    last_id = 0

    def __init__(self, operation_id, payload=None, corrupted=False):
        self.operation_id = operation_id
        if payload:
            self.payload = payload
            self.size = 8 + len(self.payload.encode())
        else:
            self.payload = None
            self.size = 8

        RequestPacket.last_id += 1
        self.packet_id = RequestPacket.last_id
        self.corrupted = corrupted

    def to_bytes(self):
        packet_id = self.packet_id.to_bytes(2, 'big')
        operation_id = self.operation_id.to_bytes(2, 'big')
        packet_size = self.size.to_bytes(2, 'big')
        if self.payload:
            payload = self.payload.encode()
        else:
            payload = b''
        temp = packet_id + operation_id + packet_size + payload

        x = 0
        for c in temp:
            x = x ^ c

        if self.corrupted:
            parity = int(255-x).to_bytes(2, 'big')
        else:
            parity = int(x).to_bytes(2, 'big')

        return packet_id + operation_id + packet_size + parity + payload

    def __str__(self):
        return ("\tPacket ID: {}\n\tOp ID: {}\n\tSize: {}\n\t"
                "Payload: {}".format(
                    self.packet_id, self.operation_id,
                    self.size, self.payload))


class ResponsePacket(object):
    def __init__(self, raw_packet):
        self.actual_size = len(raw_packet)
        if len(raw_packet) != 8:
            raise ValueError("Packet is invalid length")

        self.packet_id = int.from_bytes(raw_packet[:2], 'big')
        self.op_status = int.from_bytes(raw_packet[2:4], 'big')
        self.size = int.from_bytes(raw_packet[4:6], 'big')
        self.parity = int.from_bytes(raw_packet[6:8], 'big')
        self.raw = raw_packet

    def to_bytes(self):
        return self.raw

    def matches_parity(self):
        x = 0

        for c in self.raw:
            x = x ^ c

        return int(x) == 0


class SystemInterface(object):

    def __init__(self, port, process):
        self.port = port
        self.process = process
        self.socket = None
        self.last_id = 0

    def isConnected(self):
        return self.socket is not None

    def connect(self):
        print("Connecting to server.")
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect(("localhost", self.port))
        conn.setblocking(0)
        self.socket = conn

    def disconnect(self):
        if self.socket:
            print("Disconnecting")
            self.socket.close()
        self.socket = None

    def kill(self):
        self.disconnect()
        if self.check_if_alive():
            print("Killing process")
            self.process.terminate()

    def send_packet(self, packet):
        # print("Sending request packet:")
        # print(packet)
        sent = self.socket.send(packet.to_bytes())

        if sent < packet.size:
            raise ValueError("Failed to send packet!")

    def check_if_alive(self):
        return self.process.returncode is None

    def receive_packet(self):
        retries = 0
        chunks = []
        rec = 0
        while retries < 5 and rec < 8:
            try:
                response = self.socket.recv(8-rec)
            except socket.error as e:
                err = e.args[0]
                if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                    time.sleep(0.5)
                    continue
                else:
                    raise ValueError("Error while receiving packet!")

            if len(response) == 0:
                raise ValueError("Error while receiving packet!")

            chunks.append(response)
            rec += len(response)

        if retries == 5 or rec < 8:
            raise ValueError("Failed to receive packet")

        return ResponsePacket(b''.join(chunks))

    def make_request(
            self, operation_id, payload=None,
            check_parity=False, **kwargs):
        request = RequestPacket(operation_id, payload=payload, **kwargs)

        self.send_packet(request)
        time.sleep(1)
        response = self.receive_packet()

        if request.packet_id != response.packet_id:
            raise ValueError("Packet ID's do not match!")

        if check_parity and not response.matches_parity():
            raise ValueError(
                "Parity bit note sent on packet {}".format(request.packet_id))

        return response.op_status

    def request_ack_a(self, **kwargs):
        return self.make_request(1, **kwargs)

    def request_ack_b(self, **kwargs):
        return self.make_request(2, **kwargs)

    def request_terminate(self, **kwargs):
        return self.make_request(3, **kwargs)

    def request_create_user(self, username, **kwargs):
        return self.make_request(4, payload=username, **kwargs)

    def request_delete_user(self, username, **kwargs):
        return self.make_request(5, payload=username, **kwargs)

    def request_create_file(self, filename, **kwargs):
        return self.make_request(6, payload=filename, **kwargs)

    def request_delete_file(self, filename, **kwargs):
        return self.make_request(7, payload=filename, **kwargs)

    def request_add_user_to_file(self, username, filename, **kwargs):
        return self.make_request(
            8, payload="{}:{}".format(username, filename), **kwargs)

    def request_remove_user_from_file(self, username, filename, **kwargs):
        return self.make_request(
            9, payload="{}:{}".format(username, filename), **kwargs)

    def request_write_data(self, username, filename, data, **kwargs):
        return self.make_request(
            10, payload="{}:{}:{}".format(username, filename, data), **kwargs)


def tier_one_test(interface):

    def try_operation(operation, expected, **kwargs):
        try:
            res = operation(**kwargs)
        except ValueError as e:
            print(e)
            interface.kill()
            sys.exit(1)
        if res != expected:
            print("Bad requtrn code.  Expected: {}, Got: {}"
                  .format(expected, res))

    try_operation(interface.request_ack_a, 100)
    try_operation(interface.request_ack_b, 200)
    try_operation(interface.request_terminate, 300)

    try:
        interface.process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        print("Wait time out. Killing")
        interface.process.terminate()
        sys.exit(1)

    print("Tier 1 - Complete")


def tier_two_test(interface):
    def try_op(operation, expected, **kwargs):
        if not isinstance(expected, list):
            expected = [expected]
        try:
            res = operation(**kwargs)
        except ValueError as e:
            print(e)
            interface.kill()
            sys.exit(1)
        if res not in expected:
            print("Bad return code.  Expected: [{}], Got: {}"
                  .format(', '.join([str(ex) for ex in expected]), res))
        else:
            print("Case good.")

    try_op(interface.request_ack_a, 100)
    try_op(interface.request_ack_b, 200)
    try_op(interface.request_ack_a, 100)
    try_op(interface.request_ack_b, 200)

    users = [
        "alex", "rodger", "jules", "paul",
        "kat", "qasim", "nat", "peter",
        "tim", "kurk", "will", "ben",
        "stew", "dave", "mike", "jeff",
        "stella", "kyle", "daniel", "luke"]

    print("=== Entering first half of names ===")
    for user in users[:10]:
        try_op(interface.request_create_user, 400, username=user)

    print("=== Entering invalid names ===")
    try_op(interface.request_create_user, 402, username="_23432efaas--")

    print("=== Entering reused names ===")
    try_op(
        interface.request_create_user, 403,
        username=random.choice(users[:10]))
    try_op(
        interface.request_create_user, 403,
        username=random.choice(users[:10]))

    print("=== Entering second half of names ===")
    for user in users[10:]:
        try_op(interface.request_create_user, 400, username=user)

    try_op(interface.request_create_user, 401, username="phil")
    try_op(interface.request_create_user, [401, 402], username="alex")

    try_op(interface.request_delete_user, 500, username="rodger")
    users.remove("rodger")

    try_op(interface.request_delete_user, 501, username="2147-adsf211_")
    try_op(interface.request_delete_user, 502, username="rodger")

    filenames = ["file_{}.txt".format(i) for i in "abcdefghik"]

    for filename in filenames[:5]:
        try_op(interface.request_create_file, 600, filename=filename)

    try_op(
        interface.request_create_file, 603,
        filename=random.choice(filenames[:5]))

    try_op(
        interface.request_create_file, 602, filename="adsf..asdf")
    try_op(
        interface.request_create_file, 602, filename="adsf..asdf")
    try_op(
        interface.request_create_file, 602, filename="ad1234_343")
    try_op(
        interface.request_create_file, 602, filename="1324")
    try_op(
        interface.request_create_file, 602, filename=".hidden")
    try_op(
        interface.request_create_file, 602, filename="filasd.")
    try_op(
        interface.request_create_file, 602, filename="ad.adsf.df")

    for filename in filenames[5:]:
        try_op(interface.request_create_file, 600, filename=filename)

    try_op(
        interface.request_create_file, 601, filename="justonemore.txt")

    for user in users[7:12]:
        try_op(
            interface.request_add_user_to_file, 800,
            username=user, filename=filenames[5])

    try_op(
        interface.request_add_user_to_file, 804,
        username=users[8], filename=filenames[5])

    try_op(
        interface.request_add_user_to_file, 801,
        username=users[0], filename="dne.txt")

    try_op(
        interface.request_add_user_to_file, 802,
        username="baduser", filename=filename[6])

    for user in users[7:12]:
        try_op(
            interface.request_remove_user_from_file, 900,
            username=user, filename=filenames[5])

    try_op(
        interface.request_remove_user_from_file, 904,
        username=users[8], filename=filenames[5])

    try_op(
        interface.request_remove_user_from_file, 901,
        username=users[0], filename="dne.txt")

    try_op(
        interface.request_remove_user_from_file, 902,
        username="baduser", filename=filename[6])

    for filename in filenames:
        try_op(interface.request_delete_file, 700, filename=filename)

    for user in users:
        try_op(interface.request_delete_user, 500, username=user)

    try_op(interface.request_terminate, 300)

    try:
        interface.process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        print("Wait time out. Killing")
        interface.process.terminate()
        sys.exit(1)

    print("Tier 2 - Complete")


def get_arguments():
    "Parses the tester arguments."
    parser = argparse.ArgumentParser(
        description="A test program for the systems challenge.")

    parser.add_argument(
        'program', metavar='PROGRAM', type=str,
        help="Path to the compiled program.")

    parser.add_argument(
        'port', metavar="PORT", type=int,
        help="Port for the server to be listening to.")

    parser.add_argument(
        '--tier', choices=range(1, 4), type=int, required=True,
        help="The degree of testing to be done")

    return parser.parse_args()


def launch_program(program, port):
    if not os.path.isfile(program):
        print("Specified program does not exists")
        sys.exit(1)
    print("Launching program: {} on port {}".format(program, port))
    proc = subprocess.Popen(
        [program, str(port)],
        stdout=sys.stdout, stderr=sys.stderr)

    return proc


def main():
    """Main Test Program"""

    options = get_arguments()

    if os.path.exists(DATA_DIRECTORY) and not os.path.isdir(DATA_DIRECTORY):
        print("There is a file named {} in the current directory. "
              "Delete it, or change directores.".format(DATA_DIRECTORY))
        sys.exit(1)
    if not os.path.exists(DATA_DIRECTORY):
        os.makedirs(DATA_DIRECTORY)

    proc = launch_program(options.program, options.port)

    interface = SystemInterface(options.port, proc)
    interface.connect()

    try:
        if options.tier == 1:
            tier_one_test(interface)
        elif options.tier == 2:
            tier_two_test(interface)
    except BaseException as e:
        print("Unknown error: {}".format(str(e)))

    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        print("Wait time out. Killing")
        proc.terminate()


if __name__ == "__main__":
    main()

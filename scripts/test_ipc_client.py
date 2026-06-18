from ipc import IPCClient

client = IPCClient()

client.send(
    "PLAY_VIDEO"
)

print(
    "Message sent."
)

# PterodactylAutoStarter
Automatically restarts or starts servers that has Pterodactyl API support.

## Requirements
- Python 3.x
- websocket-client (install using `pip install websocket-client`)
- requests (install using `pip install requests`)

## Usage
1. Run the `Main.py` script.
2. Provide the credentials.

## How Does It Work?
This tool connects to the Pterodactyl websocket and checks if the server status is offline or the server went offline or the cpu usage has gone above 100. When it sees that the server is down it will automatically restart the server.

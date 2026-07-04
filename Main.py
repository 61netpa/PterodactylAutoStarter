import os;
import json;
import time;
import requests;
import uuid;
from websocket import create_connection, WebSocketException;

class Main:
    def __init__(self):
        self.Config = self.GetConfig();
        self.CurrentState = None;
        self.Restarting = False;
        self.Connection = None;
        self.ServerDeathCount = 0;

    def GetConfig(self) -> dict:
        try:
            Path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Config.json");
            if (os.path.exists(Path)):
                with open(Path) as File:
                    return json.load(File);
            else:
                PanelURL = input("Enter the panel server URL: ").removeprefix("https://").removeprefix("http://");
                while (True):
                    APIKey = input("Enter the API Key: ");
                    if (APIKey.lower().startswith("ptlc_")):
                        break;
                    else:
                        print("Invalid API key");
                while (True):
                    ServerUUID = input("Enter the Server UUID: ");
                    try:
                        FormattedUUID = uuid.UUID(ServerUUID);
                        if (str(FormattedUUID) == str(ServerUUID).lower()):
                            break;
                    except ValueError:
                        print("Invalid UUID.");
                ConfigData = { "PanelURL": PanelURL, "ServerUUID": ServerUUID, "APIKey": APIKey };
                with open(Path, "w") as File:
                    json.dump(ConfigData, File, indent = 4);
                return ConfigData;
        except Exception as Error:
            print(f"Couldn't get config. Error: {Error}");
            return {};

    def SendPowerCommand(self, Command: str) -> None:
        EndpointURL = f"https://{self.Config['PanelURL']}/api/client/servers/{self.Config['ServerUUID']}/power";
        Headers = {
            "Authorization": f"Bearer {self.Config['APIKey']}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        };
        try:
            requests.post(EndpointURL, headers = Headers, json = {"signal": Command}, timeout = 10);
        except (Exception) as Error:
            print(f"An error has occurred while sending the power command. Error: {Error}");

    def KillServer(self) -> None:
        self.SendPowerCommand("kill");

    def StartServer(self) -> None:
        self.SendPowerCommand("start");

    def RestartServer(self) -> None:
        if (not self.Connection): return;
        self.Restarting = True;
        self.CurrentState = "starting";
        self.KillServer();
        time.sleep(3);
        self.StartServer();
        time.sleep(10);
        self.Restarting = False;

    def SetWebsocket(self) -> bool:
        ResponseHeaders = {
            "Authorization": f"Bearer {self.Config['APIKey']}",
            "Accept": "application/json",
        };
        try:
            Response = requests.get(f"https://{self.Config['PanelURL']}/api/client/servers/{self.Config['ServerUUID']}/websocket", headers = ResponseHeaders, timeout = 10 );
            Response.raise_for_status();
            ResponseData = Response.json();
            if ("data" not in ResponseData or "token" not in ResponseData["data"] or "socket" not in ResponseData["data"]):
                print(f"Unexpected response from server. Raw response: {ResponseData}");
                return False;
            Data = Response.json()["data"];
            Token = Data["token"];
            WebsocketURL = Data["socket"];
        except (requests.exceptions.RequestException) as Error:
            print(f"An error occurred while sending the HTTP request to the panel. Error: {Error}");
            return False;
        except (json.JSONDecodeError) as Error:
            print(f"Failed to parse the JSON. The server most likely returned a webpage or just an invalid json. Error: {Error}");
            return False;
        except (Exception) as Error:
            print(f"An error occurred while getting websocket data. Error: {Error}");
            return False;
        WebSocketHeaders = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        };
        try:
            self.Connection = create_connection(WebsocketURL, header = WebSocketHeaders, origin = f"https://{self.Config['PanelURL']}", timeout = 10);
            AuthPayload = json.dumps({"event": "auth", "args": [Token]});
            self.Connection.send(AuthPayload);
            print("Websocket has been successfully set and connected.");
            return True;
        except (Exception) as Error:
            print(f"An error occurred while connecting to the websocket. Error: {Error}");
            self.Connection = None;
            return False;

    def Run(self) -> None:
        print("Auto Starter is running.");
        self.SetWebsocket();
        ConnectionStartTime = time.time();
        while (True):
            if (self.Connection and (time.time() - ConnectionStartTime) > 600):
                print("Websocket is about to die :sob:. Refreshing...");
                self.Connection.close();
                self.Connection = None;
                self.SetWebsocket();
                ConnectionStartTime = time.time();
                continue;
            if (not self.Connection):
                if (not self.SetWebsocket()):
                    time.sleep(10);
                    continue;
            else:
                try:
                    Message = self.Connection.recv();
                    Data = json.loads(Message);
                    EventType = Data["event"];
                    match EventType:
                        case "status":
                            self.CurrentState = Data.get("args")[0];
                            if (self.CurrentState == "offline" and not self.Restarting):
                                print("Server is offline, starting...");
                                self.Restarting = True
                                self.StartServer();
                                time.sleep(5);
                                self.Restarting = False;
                        case "stats":
                            if (self.CurrentState != "running"): continue;
                            StatsString = Data.get("args", ["{}"])[0];
                            Stats = json.loads(StatsString);
                            CPUUsage = Stats.get("cpu_absolute", 0.0);
                            if (CPUUsage > 100.0):
                                print(f"Server has exteeded the usage (Usage: {CPUUsage}). Retries left: { 3 - self.ServerDeathCount }");
                                self.ServerDeathCount += 1;
                            else:
                                self.ServerDeathCount = 0;
                            if (self.ServerDeathCount > 3):
                                print("Restarting...");
                                self.KillServer();
                except (WebSocketException) as Error:
                    print(f"Websocket connection lost, Error: {Error}");
                    self.Connection = None;
                except (json.JSONDecodeError):
                    pass;
                except (Exception) as Error:
                    print(f"An error has occured. Error: {Error}");
                    self.Connection = None;
                    time.sleep(5);

if (__name__ == '__main__'):
    Main().Run();

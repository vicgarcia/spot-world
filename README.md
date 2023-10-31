
### origins

I began working on this as a sort of experiment and learning project for working with the Spot SDK in late summer 2022.

In 2023, I revisited this code in the context of the Spot SDK 3.3 update, specifically to leverage the changes to the autowalk mission editing on the tablet I wanted to be able to lever.

Spot world is the outcome of this. A command line environment for controlling the spot robot and executing missions.

### usage

The first step to utilize spot world is to record an autowalk map with a variety of actions, then use the tablet map editor to organize groups of actions into individual missions. For my development example, I built a map around the office to do a variety of 'inspections', then created missions such as capturing photos of whiteboards and kitchen provisions. I also added some simple pose actions, put these into missions with names like 'goto engineering' so that running these can move the robot to a specific point.

Once I had a map and missions, I exported the .walk path from the tablet to a usb drive.

Setup spot world by cloning the repository, create a virtual environment in the repository. I use a combination of pyenv and venv to create a virtual environment (in a directory within the cloned repo named `venv`) and installing the dependencies from the `requirements.txt` file. The repo contains a `spot_world` wrapper script which start the app using the virtual environment.

Place the `.walk` folder from the tablet into the `autowalks` folder in the repo.

Start the app, providing command line args ...
```
./spot_world --hostname <ip of robot> --username <username> --password <password> --autowalk autowalks/folder-from-tablet.walk
```

When the app starts, it will ...
- connect to the robot and authenticate
- setup an estop
- 'take' the lease
- load the graph from the autowalk to the robot
- power on the motors

The app exposes a variety of commands to ...
- control estop, lease, and power states
- list fiducials from the graph, navigate to a fiducial
- list missions from autowalk,

The terminal ...

The terminal prompt displays estop, lease, and power status. Each indicator block is rendered in green when active and red when not. The display is not updated in real time, it's rendered when a command completes.

Examples ...

Undock the robot

robot undock

Go to a fiducial

For complete details use the `help` command

### install

clone the repository

create virtual environment and install dependencies
```
python -m venv venv
./venv/bin/pip install -U pip
./venv/bin/pip install -r requirements.txt
```

run the app using the wrapper script
```
./spot_world --hostname 192.168.200.64 --username admin --password passwordhere --autowalk ./maps/something.walk
```

create a .env file to avoid having to put hostname/username/password on the command line
```
vim .env
---
SPOT_HOSTNAME=
SPOT_USERNAME=
SPOT_PASSWORD=
```

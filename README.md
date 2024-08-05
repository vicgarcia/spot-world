<header image>

## the idea

I began working on spot-world as a sort of experiment and learning project for working with the [Boston Dynamics Spot SDK](https://dev.bostondynamics.com/) in late summer 2022. I wanted to learn some of the details of interacting with the underlying robot services.

In 2023, I revisited this code for the release of the Spot 3.3 firmware update, specifically to leverage some of the improvements to autowalk missions and assist in testing feature development with the robot.

Since then, I've made some further improvements to the experience to make spot-world useful for working with a spot robot day to day. The end result is a console environment for controlling a Spot robot, moving the robot around an autowalk map and running missions.


## in action

Before diving in, take a look at some typical use cases for spot-world

<console screenshot>

Undock and navigate to a given fiducial
```
robot undock
fiducials goto 3
```

Run a mission
```
mission run industrial-gauge-demo
```

Navigate from one dock to another
```
robot undock
fiducials goto 525
robot dock
```

Execute a mission on a continous loop
```
mission loop office-tour
```


## install

clone the repository

create virtual environment and install dependencies
```
python3 -m venv venv
./venv/bin/pip install -U pip
./venv/bin/pip install -r requirements.txt
```

Optionally, create an `.env` file to avoid having to put hostname/username/password on the command line
```
cp .env.template .env
vim .env
---
SPOT_HOSTNAME=
SPOT_USERNAME=
SPOT_PASSWORD=
```


## usage

The first step to utilize spot-world is to record an autowalk map with a variety of actions, then use the tablet map editor to organize groups of actions into individual missions. For my development example, I built a map around the office to do a variety of inspection actions as well as poses at specific locations, then created missions as groups of the actions, such as a 'office-tour' mission that consists of visiting various locations in the office, or the 'industrial-gauge-demo' mission to demonstrate computer vision software.

<tablet screenshot>

After creating the map and missions, use the tablet file manager app to copy the contents of the `<mission name>.walk` folder to a usb drive, then to the `./autowalks` folder in the spot-world repo.

Run the app using the wrapper script
```
./spot-world --hostname 192.168.80.3 --username admin --password hunter2 --autowalk ./autowalks/mission-name.walk --initialize
```

The `--hostname`, `--username`, and `--password` arguments can be omitted when using an `.env` file to provide them as described above. The `--initialize` flag will acquire a robot lease, setup the estop, and power on the motors when starting the application as a time saver.

#### the console

The console shows the status of the robot to the right of the command line. The indicators use color to provide information on the robot.

`LEASE` shows the status of the robot lease, with green indicating a current lease and white indicating no current lease.

`ESTOP` shows the status of the robot estop. White indicates no estop is running, green indicates an estop is running and the estop is not engaged (blocking the robot from moving), red indicates the estop is engaged, and yellow indicates an error state with the estop.

`MOTOR` shows the status of the robot motors.

`XX%` shows the battery state as a percentage. It will be green when the charge is above 30%, yellow when between 30% and 11%, and red when 10% or less.

Exit the application using the `exit` command. Be aware that exiting will automatically sit the robot, power off the motors, shutdown the estop, and release the lease. The goal being to exit the application and ensure the robot is in a disconnected state and ready for other use without interference.

Be aware that exiting the applciation while the robot is standing will result in the robot stopping and sitting immediately. The behavior is inteded to be at minimum a graceful shutdown, but may still result in the robot falling. Take proper safety precautions at all times when using spot-world, but especially while the robot is standing and in motion.

#### status command

The status of the robot can be seen using the `status` command.

`status` will print the current status of the robot. This is in the form of the data structure returned from the robot directly, so the formatting is not pretty, but functional.

The status command is available regardless the lease or estop state of the robot.

Many commands will fail when used without the robot being in the proper state. It cannot undock without a lease, an estop, and motors powered on. It cannot move when sitting. The status command will work regardless of any robot state.

#### lease command

The robot lease can be managed with the `lease` command.

`lease acquire` will acquire a body lease to control the robot.

`lease take` will take a body lease to control the robot.

`lease release` will release the lease for the robot.

Leases are released when exiting the app. There is no need to explicitly release before exiting.

Be aware that releasing a lease or exiting the app with the robot standing may be unsafe and cause the robot to fall.

#### estop command

The robot estop can be managed with the `estop` command.

`estop setup` will start the estop with the robot.

`estop shutdown` will stop the estop with the robot.

`estop clear` will disengage the estop after it's been activated.

The estop functionality can be used to engage the estop and stop and cut robot power by pressing `ctrl-c` at any time while the app is running and an estop is setup. The robot will stop motion and sit when the estop is engaged. This calls the `settle_then_cut` sdk function, which attempts to sit the robot gently as opposed to an immediate cut of power. Be aware of this distinction and it's implication for your use case. Spot World is a developer tool, is not robustly tested for use in hazardous environments, and is provided without any warranty.

The estop is shutdown when exiting the app. There is no need to explicitly release the app.

Be aware that shutting down the estop or exiting the app with the robot standing may be unsafe and cause the robot to fall.

#### motors command

The robot motors can be managed with the `motors` command.

`motors on` will turn the motors on.

`motors off` will turn the motors off.

The motors will be powered off when exiting the app. There is no need to explicitly power off the motors.

Be aware that when powering off the motors or exiting the app with the robot standing may be unsafe and cause the robot to fall.

#### robot command

The robot command exposes a variety of movement related behaviors.

`robot undock` will undock the robot. When undocking, the dock id is save for use.

When the robot is undocked, the id of the dock is saved as the originating dock. The robot will also be localized (utilizing the dock fiducial) to the loaded map when undocking automatically.

`robot stand` will stand the robot up.

`robot sit` will sit the robot down.

`robot localize` will localize to a visible fiducial.

Localiziation is automatically performed as part of the undock command, so it's not strictly necessary. It can be useful, but since spot-world offers no direct way of controlling robot motion directly, the robot will always need to either be localized or in immediate view of a fiducial.

For my use case, it's sufficient to have a couple spare fiducials in places the robot is likely to be, so that if the robot is not docked when starting the app, it's possible to stand the robot, call the localize command, and then move the robot using other available commands.

`robot dock` will dock the robot at a visible dock.

If called where no dock is visible the command will fail. This can be used in combination with the fiducials command to navigate to a dock then dock at it.

`robot return` will navigate the robot to the originating dock and dock the robot.

The originating dock is saved when the undock command is called, and if the app is stared with the robot undocked, the command will fail.

#### fiducials command

Interact with fiducials on the map using the `fiducials` command.

`fiducials list` will list all fiducials on the map which will include any fiducials indicating a dock.

`fiducials goto <fiducial number>` will navigate the robot to the fiducial.

The logic to locate a waypoint near a fiducial to navigate the robot to is not incredibly precise. 'Near the fiducial, typically not directly in front of it' is a better description of what to expect.

To move the robot to a precise position near a fiducial or anywhere on the map, a better approach would be using a pose action and a mission as described further in this documentation.

#### missions command

Run mission using the `missions` command.

`missions list` will list all available missions.

`missions execute <mission-name>` will execute a mission.

Mission execution provides two behaviors with regards to docking.

If the `missions execute` command is called when the robot is docked, the robot will undock, execute the mission, then return to the dock.

If the `missions execute` command is called when the robot is undocked, the robot will execute the mission and stop and return control to the console at the location of the last action.

While the typical use case is to execute the mission while docked with the robot returning to the dock when complete, mission execution when the robot is undocked is useful for some other specialized use cases.

As described above, the most reliable way to move the robot to an exact position use a pose action. Create a mission with a single action, the pose action. Executing this mission with the robot undocked (undocking with the `robot undock` command first when necessary) will cause the robot to navigate to the desired position and return control to the console.

Currently the spot-world mission execution functionality does not handle any mission interruptions or errors. Any situation which would trigger an alert for instructions (a mission question) on the tablet will cause mission execution to fail. Mission failure will abide by docking behavior of the mission being executed, with missions originating from the dock failing and the robot returning to the dock, and missions originating off dock stoping and returning robot control to the console in place.

`missions loop <mission-name>` will execute a mission in a loop, executing the mission again when completed.

The missions loop command has turned out to be a major use case for spot-world. Visitors to the office like to see the robot up and walking around. It's fun and allows for demonstration of the robot in action. I use a mission that performs various actions and poses at different points around the office, then run that mission on a loop.

The loop will execute continously until broken be engageing the estop with `ctrl-c`. Be aware the robot will stop moving and sit. The robot will sit, and the estop will need to be cleared with `estop clear` and the motors powered on with `motors on`. If the loop was started while the robot was docked, the robot will return to the dock using the `robot return` command.

<action shot>


## safety

spot-world is a dev tool side project. It has not been tested in any serious way. It's primarily used in a office lab setting under supervision in a controlled environment. It has not been validated for use in any environment or use case beyond this. This codebase is provided for experimental and educational purposes. Use at your own risk, and please exercise all necessary safety precautions when working with Spot robots.

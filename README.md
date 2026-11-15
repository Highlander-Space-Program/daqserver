# daqserver

The main DAQ server repo.

## Running this project

1. Download the command
   [`uv`](https://docs.astral.sh/uv/getting-started/installation/) to your
   computer
2. Download [`git`](https://git-scm.com/install/) command to your computer
3. Clone the project `git clone https://github.com/Highlander-Space-Program/daqserver.git`
4. Get into the source code `cd daqserver`
5. Run the project `uv run server`

## Running this project with MQTT

1. Same steps as 1-4 from above
2. Download [Docker
   Desktop](https://docs.docker.com/compose/install/#docker-desktop-recommended)
   to your computer
3. Create a .env file `cp .env.example .env`
4. Spin up the mqtt broker and server `docker compose up -d mosquitto server`
5. If need to check the logs, run `docker compose logs -f mosquitto`

You don't need to download any Python for this, `uv` will download the right
version and install all of the packages for you.

## Running the data simulator

The simulator sends fake sensor data to Grafana, so you can build and test
dashboards without the real test stand. It fakes 4 pressure sensors (PT-1 to
PT-4), 3 temperature sensors (TC-1 to TC-3) and 1 thrust sensor (LC-1), and
plays out a pretend test fire (pressurize, burn, vent) that repeats every 60
seconds.

### 1. Start Grafana

1. Do steps 1-4 from [Running this project](#running-this-project) if you
   haven't already
2. Download and open [Docker
   Desktop](https://docs.docker.com/compose/install/#docker-desktop-recommended).
   Leave it running.
3. Start Grafana `docker compose up -d grafana`
4. Open http://localhost:3000 in your browser and log in with username `admin`
   and password `admin`. If it asks you to change the password, you can click
   **Skip**.

### 2. Start the simulator

In a terminal inside the `daqserver` folder, run:

```
uv run python -m server.streaming.simulator
```

You should see `Pushing 8 channels at 10.0 Hz ...`. Leave this terminal open.
The simulator keeps running until you press `Ctrl+C`.

### 3. Make a graph in Grafana

1. In Grafana, click **Dashboards** in the left menu, then **New** →
   **New dashboard** → **Add visualization**
2. When it asks for a data source, pick **-- Grafana --**
3. Under the query, change **Query type** to **Live Measurements**
4. For **Channel**, pick one of these:
   - `stream/daq_sim/pressure` for the pressure sensors (psi)
   - `stream/daq_sim/temperature` for the temperature sensors (°C)
   - `stream/daq_sim/load` for the thrust sensor (lbs)
5. You should see lines moving within a few seconds. Click **Save dashboard**
   (top right) so you don't have to do this again.

Repeat step 3 to add a graph for each channel.

### Something went wrong?

- **`Cannot reach Grafana`**: Grafana isn't running. Make sure Docker Desktop
  is open and run `docker compose up -d grafana` again.
- **`Grafana rejected the credentials`**: someone changed the Grafana admin
  password. Ask the DAQ lead for it, then put these two lines in your `.env`
  file (create it with `cp .env.example .env` if you don't have one):
  ```
  GRAFANA_USER=admin
  GRAFANA_PASSWORD=the-new-password
  ```
- **The channel isn't in the list, or the graph is empty**: make sure the
  simulator terminal is still running and not showing errors. The channels
  only show up after the simulator has started sending data.

## Development

If you are going to add a new package to the python code, use `uv add
package-name`. When you are committing code, I recommend following the [git
commit conventions](https://www.conventionalcommits.org/en/v1.0.0/). For this
project, I don't want anyone to directly push code to the `main` branch, unless
you are doing a quick bugfix or fixing a typo. What you are going to do is push
your local branch to this remote repository, and then create a pull request
that is going to merge into the `main` branch. The DAQ lead or DAQ SE will look
over your code in the pull request. If it is good, we will merge your code to
the `main` branch, and if it is not good, we will ask you to make some changes.
The idea here is that we want to keep `main` branch stable and not breaking.
This means that you need to always create a new branch whenever you started
working on your code.

## I am confused

This section here shows you how to navigate and use the codebase. If you have
trouble with creating a pull request or how to use `git` you should try looking
for a quick Youtube Tutorial or try asking ChatGPT, and then learn how to solve
ur `git` problem, so you won't have to deal with it again later in the future.

Under some directories like [`scripts`](./scripts) and [`server`](./server),
you may find another `README.md` file. Inside of these `README.md` files, you
will find guides and descriptions that will help you with navigating around the
codebase. Don't afraid to ping the DAQ lead or the DAQ SE for help. Trying to
figure out how to work with a new codebase yourself is difficult. When you are
assigned a task for this project, you are expected to know a little bit of
Python and also a little bit of `git`. Please don't ever use `git push --force`
or `git push --force-with-lease` if you have no idea what you are doing.

For those of you who already know a little bit about Python, it's a good idea
to follow the [`PEP-8`](https://peps.python.org/pep-0008/) styling guide when
adding your code to the project. If you want to challenge yourself a bit more
(and I would be really happy if you do), try to make sure that everything you
wrote is [type hinted](https://peps.python.org/pep-0484/) and tested through
`pytest` (yes this means I would like you to write some unit tests for your
code whenever possible).

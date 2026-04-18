# daqserver

The main DAQ server repo.

## Running this project

1. Download the command [`uv`](https://docs.astral.sh/uv/getting-started/installation/) to your computer
2. Download [`git`](https://git-scm.com/install/) command to your computer
3. Clone the project `git clone https://github.com/Highlander-Space-Program/daqserver.git`
4. Get into the source code `cd daqserver`
5. Run the project `uv run server`

## Running this project with MQTT
1. Same steps as 1-4
5. Download [`Docker Desktop`](https://docs.docker.com/compose/install/#docker-desktop-recommended) to your computer
6. Create a .env file `cp .env.example .env`
7. Spin up the mqtt broker and server `docker compose up -d mosquitto server`
8. If need to check the logs, run `docker compose logs -f mosquitto`

You don't need to download any Python for this, `uv` will download the right
version and install all of the packages for you.

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

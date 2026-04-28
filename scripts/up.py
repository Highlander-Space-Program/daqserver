import subprocess
import time
import re
import sys
import os
from pathlib import Path


def run_command(cmd, capture_output=False, exit_on_fail=True):
    """Utility to run shell commands."""
    print(f"\n> Running: {cmd}")
    result = subprocess.run(
        cmd, shell=True, text=True, capture_output=capture_output
    )

    if result.returncode != 0 and exit_on_fail:
        print(f"ERROR: Command failed with exit code {result.returncode}")
        if capture_output:
            print("STDERR:", result.stderr)
            print("STDOUT:", result.stdout)
        sys.exit(result.returncode)

    return result


def strip_ansi_codes(text):
    """Removes ANSI color and style escape codes from a string."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def parse_env(filepath):
    """Parses an environment file into a dictionary."""
    env_dict = {}
    if not os.path.exists(filepath):
        return env_dict

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            # Ignore comments and empty lines
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                env_dict[key.strip()] = val.strip()
    return env_dict


def is_env_ready(env_dict):
    """Checks if all required variables are present and not empty."""
    required_keys = [
        "INFLUXDB_TOKEN",
        "INFLUXDB_URL",
        "INFLUXDB_DATABASE",
        "MQTT_HOST",
        "MQTT_PORT",
    ]
    for key in required_keys:
        if key not in env_dict or not env_dict[key]:
            return False
    return True


def setup_environment():
    """Runs the initial setup to generate tokens and configure .env"""
    print("\n> Initializing setup process...")
    Path(".env").touch()

    # 1. Start InfluxDB3 Core
    run_command("docker compose up -d influxdb3-core")

    # 2. Generate the Admin Token
    print("\n> Waiting for InfluxDB to initialize and generate token...")
    token = None
    token_cmd = (
        "docker compose exec influxdb3-core influxdb3 create token --admin"
    )

    for attempt in range(1, 11):
        result = run_command(token_cmd, capture_output=True, exit_on_fail=False)
        if result.returncode == 0:
            clean_stdout = strip_ansi_codes(result.stdout)
            match = re.search(r"Token:\s+(\S+)", clean_stdout)
            if match:
                token = match.group(1)
                print(f"Successfully extracted token: {token}")
                break
        else:
            print("STDERR:", result.stderr)
            print("STDOUT:", result.stdout)
            print()

        print(f"Attempt {attempt}/10 failed, retrying in 3 seconds...")
        time.sleep(3)

    if not token:
        print(
            "ERROR: Failed to generate or extract the InfluxDB token after multiple attempts."
        )
        sys.exit(1)

    # 3. Read .env.example
    env_example_path = ".env.example"
    if not os.path.exists(env_example_path):
        print(f"ERROR: {env_example_path} not found in the current directory.")
        sys.exit(1)

    with open(env_example_path, "r") as f:
        env_content = f.read()

    # 4. Ask user deployment preference
    print("\n" + "=" * 50)
    while True:
        choice = (
            input(
                "Do you want to run the 'server' inside of a Docker container? (y/n): "
            )
            .strip()
            .lower()
        )
        if choice in ["y", "yes", "n", "no"]:
            break
        print("Please enter 'y' or 'n'.")

    run_server_in_docker = choice.startswith("y")

    # 5. Modify environment variables
    env_content = re.sub(
        r"^INFLUXDB_TOKEN=.*$",
        f"INFLUXDB_TOKEN={token}",
        env_content,
        flags=re.MULTILINE,
    )

    if not run_server_in_docker:
        env_content = re.sub(
            r"^INFLUXDB_URL=.*$",
            "INFLUXDB_URL=http://localhost:8181",
            env_content,
            flags=re.MULTILINE,
        )
        env_content = re.sub(
            r"^MQTT_HOST=.*$",
            "MQTT_HOST=localhost",
            env_content,
            flags=re.MULTILINE,
        )
        print("\n> Configured .env for LOCAL server execution.")
    else:
        print("\n> Configured .env for DOCKER server execution.")

    # Write to .env
    with open(".env", "w") as f:
        f.write(env_content)
    print("> Saved environment variables to .env")


def main():
    env_dict = parse_env(".env")

    # Check if we need to run the setup phase
    if not is_env_ready(env_dict):
        setup_environment()
        # Reload the environment dictionary after setup
        env_dict = parse_env(".env")
    else:
        print("\n> .env is fully configured. Skipping token generation.")

    # Determine execution mode based on .env configuration
    run_locally = "localhost" in env_dict.get(
        "INFLUXDB_URL", ""
    ) or "localhost" in env_dict.get("MQTT_HOST", "")

    # Start core infrastructure (Docker Compose will naturally skip containers that are already running)
    print("\n> Ensuring core infrastructure is running...")
    run_command(
        "docker compose up -d influxdb3-core influxdb3-ui grafana mosquitto"
    )

    # Start the server based on environment context
    if run_locally:
        print("\n> Detected 'localhost' in .env. Starting server locally...")
        run_command("uv run server")
    else:
        print(
            "\n> Detected docker hostnames in .env. Starting server in Docker..."
        )
        run_command("docker compose up -d --build server")


if __name__ == "__main__":
    main()

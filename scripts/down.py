import os
import subprocess


def run_command(cmd):
    """Utility to run shell commands."""
    print(f"\n> Running: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(
            f"Warning: Command '{cmd}' failed with exit code {result.returncode}"
        )
    else:
        print("> Command completed successfully.")


def main():
    print("=" * 50)
    print("Cleanup Script")
    print("=" * 50)

    # 1. Ask the user if they want to remove the .env file
    while True:
        choice = (
            input("\nDo you want to remove the .env file? (y/n): ")
            .strip()
            .lower()
        )
        if choice in ["y", "yes", "n", "no"]:
            break
        print("Please enter 'y' or 'n'.")

    # 2. Process .env removal
    if choice.startswith("y"):
        env_path = ".env"
        if os.path.exists(env_path):
            try:
                os.remove(env_path)
                print(f"> Successfully removed {env_path}.")
            except OSError as e:
                print(f"> ERROR: Could not remove {env_path}. Reason: {e}")
        else:
            print(f"> {env_path} does not exist. Skipping.")
    else:
        print("> Keeping the .env file.")

    # 3. Run docker compose down -v
    print("\n> Tearing down Docker containers and volumes...")
    run_command("docker compose down -v")

    print("\n> Cleanup complete.")


if __name__ == "__main__":
    main()

import argparse
import asyncio
import logging
import os
import signal
from typing import List
import warnings
import sys
import shutil
import getpass
import subprocess
from bluetti_mqtt.bluetooth import scan_devices
from bluetti_mqtt.bus import EventBus
from bluetti_mqtt.device_handler import DeviceHandler
from bluetti_mqtt.mqtt_client import MQTTClient


class CommandLineHandler:
    def __init__(self, argv=None):
        self.argv = argv or sys.argv[:]
        self.service_config = {}
        self.service_file_content = ""

    def execute(self):
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description='Scans for Bluetti devices and logs information')
        parser.add_argument(
            '--scan',
            action='store_true',
            help='Scans for devices and prints out addresses')
        parser.add_argument(
            '--broker',
            metavar='HOST',
            dest='hostname',
            help='The MQTT broker host to connect to')
        parser.add_argument(
            '--port',
            default=1883,
            type=int,
            help='The MQTT broker port to connect to - defaults to %(default)s')
        parser.add_argument(
            '--username',
            type=str,
            help='The optional MQTT broker username')
        parser.add_argument(
            '--password',
            type=str,
            help='The optional MQTT broker password')
        parser.add_argument(
            '--interval',
            default=0,
            type=int,
            help='The polling interval - default is to poll as fast as possible')
        parser.add_argument(
            '--ha-config',
            default='normal',
            choices=['normal', 'none', 'advanced'],
            help='What fields to configure in Home Assistant - defaults to most fields ("normal")')
        parser.add_argument(
            '--ha-discovery-prefix',
            default='homeassistant',
            help='The Home Assistant discovery prefix - defaults to %(default)s')
        parser.add_argument(
            '--loglevel',
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            default='INFO',
            type=str.upper,
            help='Set the logging output level (DEBUG, INFO, WARNING, ERROR) - defaults to %(default)s')
        parser.add_argument(
            '--install',
            action='store_true',
            help='Install bluetti-mqtt as a systemd service (requires sudo).')
        parser.add_argument(
            'addresses',
            metavar='ADDRESS',
            nargs='*',
            help='The device MAC(s) to connect to')

        # The default event loop on windows doesn't support add_reader, which
        # is required by asyncio-mqtt
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        args = parser.parse_args(self.argv[1:])

        # Configure logging
        numeric_level = getattr(logging, args.loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f'Invalid log level: {args.loglevel}')
        logging.basicConfig(
            datefmt='%Y-%m-%d %H:%M:%S',
            format='%(asctime)s %(levelname)-8s %(message)s',
            level=numeric_level
        )
        if numeric_level == logging.DEBUG:
            warnings.simplefilter('always')

        if args.install:
            self.handle_install(args)
        elif args.scan:
            asyncio.run(scan_devices())
        elif args.hostname and len(args.addresses) > 0:
            self.start(args) # This is the existing run method for normal operation
        else:
            # If --install is not given, and other conditions aren't met,
            # show help. This might need adjustment if --install
            # can be combined with other args to pre-fill service config.
            # For now, assume --install is exclusive or collects its own data.
            parser.print_help()

    def handle_install(self, args: argparse.Namespace):
        if os.geteuid() != 0:
            print("Error: Installation requires root privileges. Please run with sudo.", file=sys.stderr)
            sys.exit(1)
        # Placeholder removed, actual logic starts here

        # Determine Executable Path
        executable_path = shutil.which('bluetti-mqtt')
        if not executable_path:
            executable_path = os.path.abspath(sys.argv[0])
            if not (os.path.exists(executable_path) and os.access(executable_path, os.X_OK)):
                print(f"Error: Could not determine bluetti-mqtt executable path from '{sys.argv[0]}'. Please ensure it's in PATH or run from its directory.", file=sys.stderr)
                sys.exit(1)

        # Determine Service User
        run_as_user = os.getenv('SUDO_USER')
        if not run_as_user or run_as_user == 'root':
            while True:
                prompt_user = input(f"Enter the username to run the service as (e.g., pi) [current SUDO_USER: {os.getenv('SUDO_USER')}]: ").strip()
                if prompt_user:
                    run_as_user = prompt_user
                    break
                print("Username cannot be empty.")

        # Prompt for MQTT Broker Host
        while True:
            mqtt_broker = input("Enter MQTT Broker host (e.g., localhost or mqtt.example.com): ").strip()
            if mqtt_broker:
                break
            print("MQTT Broker host cannot be empty.")

        # Prompt for Device MAC Addresses
        while True:
            devices_str = input("Enter device MAC addresses (space-separated, e.g., AA:BB:CC:11:22:33): ").strip()
            if devices_str:
                device_addresses = devices_str.split()
                break
            print("Device MAC addresses cannot be empty.")

        # Prompt for Optional Arguments
        mqtt_port = input(f"Enter MQTT Port [default: 1883]: ").strip() or "1883"
        mqtt_username = input(f"Enter MQTT Username [optional, press Enter to skip]: ").strip()

        mqtt_password = ""
        if mqtt_username:
            mqtt_password = getpass.getpass(f"Enter MQTT Password for '{mqtt_username}' [optional, press Enter to skip, hidden]: ")

        poll_interval = input(f"Enter Polling Interval (seconds) [default: 0, for fastest polling]: ").strip() or "0"

        loglevel = input(f"Enter Log Level (DEBUG, INFO, WARNING, ERROR) [default: INFO]: ").strip().upper() or "INFO"
        valid_loglevels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
        if loglevel not in valid_loglevels:
            print(f"Invalid log level '{loglevel}'. Defaulting to INFO.")
            loglevel = "INFO"

        ha_config = input(f"Home Assistant Config (normal, none, advanced) [default: normal]: ").strip().lower() or "normal"
        valid_ha_configs = ['normal', 'none', 'advanced']
        if ha_config not in valid_ha_configs:
            print(f"Invalid Home Assistant Config '{ha_config}'. Defaulting to normal.")
            ha_config = "normal"

        ha_discovery_prefix = input(f"Home Assistant Discovery Prefix [default: homeassistant]: ").strip() or "homeassistant"

        self.service_config = {
            'executable_path': executable_path,
            'run_as_user': run_as_user,
            'mqtt_broker': mqtt_broker,
            'device_addresses': device_addresses,
            'mqtt_port': mqtt_port,
            'mqtt_username': mqtt_username,
            'mqtt_password': mqtt_password,
            'poll_interval': poll_interval,
            'loglevel': loglevel,
            'ha_config': ha_config,
            'ha_discovery_prefix': ha_discovery_prefix,
        }

        print("\n--- Service Configuration Collected ---")
        for key, value in self.service_config.items():
            if key == 'mqtt_password':
                print(f"{key}: {'******' if value else ''}")
            else:
                print(f"{key}: {value}")
        print("------------------------------------\n")

        # Generate systemd service file content
        service_template = f"""
[Unit]
Description=Bluetti MQTT Client for {self.service_config['run_as_user']}
After=network.target

[Service]
Type=simple
User={self.service_config['run_as_user']}
ExecStart={{exec_start_command}}
Restart=always
RestartSec=30
TimeoutStopSec=15
StandardOutput=journal
StandardError=journal
SyslogIdentifier=bluetti-mqtt

[Install]
WantedBy=multi-user.target
"""

        exec_parts = [self.service_config['executable_path']]
        exec_parts.append(f"--broker {self.service_config['mqtt_broker']}")
        exec_parts.append(f"--port {self.service_config['mqtt_port']}")

        if self.service_config['mqtt_username']:
            exec_parts.append(f"--username '{self.service_config['mqtt_username']}'")
        if self.service_config['mqtt_password']:
            exec_parts.append(f"--password '{self.service_config['mqtt_password']}'")

        exec_parts.append(f"--interval {self.service_config['poll_interval']}")
        exec_parts.append(f"--loglevel {self.service_config['loglevel']}")
        exec_parts.append(f"--ha-config {self.service_config['ha_config']}")
        exec_parts.append(f"--ha-discovery-prefix '{self.service_config['ha_discovery_prefix']}'")

        exec_parts.extend(self.service_config['device_addresses'])
        exec_start_command = ' '.join(exec_parts)

        self.service_file_content = service_template.format(exec_start_command=exec_start_command).strip()

        print("\n--- Generated Service File Content ---")
        print(self.service_file_content)
        print("------------------------------------\n")

        service_file_path = "/etc/systemd/system/bluetti-mqtt.service"

        # Write the service file
        try:
            with open(service_file_path, "w") as f:
                f.write(self.service_file_content)
            print(f"Successfully wrote systemd service file to {service_file_path}")
        except IOError as e:
            print(f"Error: Failed to write systemd service file to {service_file_path}: {e}", file=sys.stderr)
            sys.exit(1)

        # Run systemctl daemon-reload
        print("Reloading systemd daemon...")
        try:
            result = subprocess.run(["systemctl", "daemon-reload"], check=True, capture_output=True, text=True)
            if result.stdout: print(f"daemon-reload stdout: {result.stdout.strip()}")
            if result.stderr: print(f"daemon-reload stderr: {result.stderr.strip()}")
            print("Systemd daemon reloaded successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error: Failed to reload systemd daemon: {e}", file=sys.stderr)
            if e.stdout: print(f"Stdout: {e.stdout.strip()}", file=sys.stderr)
            if e.stderr: print(f"Stderr: {e.stderr.strip()}", file=sys.stderr)
            print("Please check systemd status and try again.", file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError:
            print("Error: systemctl command not found. Please ensure systemd is installed and active.", file=sys.stderr)
            sys.exit(1)

        # Run systemctl enable bluetti-mqtt
        print("Enabling bluetti-mqtt service to start on boot...")
        try:
            result = subprocess.run(["systemctl", "enable", "bluetti-mqtt.service"], check=True, capture_output=True, text=True)
            # systemctl enable often prints to stderr on success (e.g., "Created symlink...")
            if result.stdout: print(f"enable stdout: {result.stdout.strip()}")
            if result.stderr: print(f"enable stderr: {result.stderr.strip()}")
            print("bluetti-mqtt service enabled successfully.")

            print("\nInstallation complete.")
            print("The bluetti-mqtt service is now enabled and will start on boot.")
            print("You can manually start it now, or check its status with:")
            print("  sudo systemctl start bluetti-mqtt.service")
            print("  sudo systemctl status bluetti-mqtt.service")
            print("  journalctl -u bluetti-mqtt.service -f (to follow logs)")

            while True:
                start_choice = input("\nDo you want to start the bluetti-mqtt service now? (y/n): ").strip().lower()
                if start_choice in ['y', 'n']:
                    break
                print("Invalid choice. Please enter 'y' or 'n'.")

            if start_choice == 'y':
                print("Starting bluetti-mqtt service...")
                try:
                    result = subprocess.run(["systemctl", "start", "bluetti-mqtt.service"], check=True, capture_output=True, text=True)
                    if result.stdout: print(f"start stdout: {result.stdout.strip()}")
                    if result.stderr: print(f"start stderr: {result.stderr.strip()}")
                    print("bluetti-mqtt service started successfully.")
                    print("You can check its status with: sudo systemctl status bluetti-mqtt.service")
                    print("Follow logs with: journalctl -u bluetti-mqtt.service -f")
                except subprocess.CalledProcessError as e_start:
                    print(f"Error: Failed to start bluetti-mqtt service: {e_start}", file=sys.stderr)
                    if e_start.stdout: print(f"Stdout: {e_start.stdout.strip()}", file=sys.stderr)
                    if e_start.stderr: print(f"Stderr: {e_start.stderr.strip()}", file=sys.stderr)
                    print("Please check systemd status and logs (journalctl -u bluetti-mqtt.service).", file=sys.stderr)
                except FileNotFoundError:
                    print("Error: systemctl command not found.", file=sys.stderr)
            else:
                print("Service not started. You can start it later with: sudo systemctl start bluetti-mqtt.service")
        except subprocess.CalledProcessError as e:
            print(f"Error: Failed to enable bluetti-mqtt service: {e}", file=sys.stderr)
            if e.stdout: print(f"Stdout: {e.stdout.strip()}", file=sys.stderr)
            if e.stderr: print(f"Stderr: {e.stderr.strip()}", file=sys.stderr)
            print("Please check systemd status and try again.", file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError: # Should have been caught by daemon-reload
            print("Error: systemctl command not found.", file=sys.stderr)
            sys.exit(1)

    def start(self, args: argparse.Namespace):
        loop = asyncio.get_event_loop()

        # Register signal handlers for safe shutdown
        if sys.platform != 'win32':
            signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
            for s in signals:
                loop.add_signal_handler(s, lambda: asyncio.create_task(shutdown(loop)))

        # Register a global exception handler so we don't hang
        loop.set_exception_handler(handle_global_exception)

        try:
            loop.create_task(self.run(args))
            loop.run_forever()
        finally:
            loop.close()
            logging.debug("Shut down completed")

    async def run(self, args: argparse.Namespace):
        loop = asyncio.get_running_loop()
        bus = EventBus()

        # Set up strong reference for tasks
        self.background_tasks = set()

        # Start event bus
        bus_task = loop.create_task(bus.run())
        self.background_tasks.add(bus_task)
        bus_task.add_done_callback(self.background_tasks.discard)

        # Start MQTT client
        mqtt_client = MQTTClient(
            bus=bus,
            hostname=args.hostname,
            home_assistant_mode=args.ha_config,
            port=args.port,
            username=args.username,
            password=args.password,
            discovery_prefix=args.ha_discovery_prefix,
        )
        mqtt_task = loop.create_task(mqtt_client.run())
        self.background_tasks.add(mqtt_task)
        mqtt_task.add_done_callback(self.background_tasks.discard)

        # Start bluetooth handler (manages connections)
        addresses: List[str] = list(set(args.addresses))
        handler = DeviceHandler(addresses, args.interval, bus)
        bluetooth_task = loop.create_task(handler.run())
        self.background_tasks.add(bluetooth_task)
        bluetooth_task.add_done_callback(self.background_tasks.discard)


def handle_global_exception(loop, context):
    if 'exception' in context:
        logging.error('Crashing with uncaught exception:', exc_info=context['exception'])
    else:
        logging.error(f'Crashing with uncaught exception: {context["message"]}')
    asyncio.create_task(shutdown(loop))


async def shutdown(loop: asyncio.AbstractEventLoop):
    logging.info('Shutting down...')
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()


def main(argv=None):
    cli = CommandLineHandler(argv)
    cli.execute()


if __name__ == "__main__":
    main(sys.argv)

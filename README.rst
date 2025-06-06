============
bluetti_mqtt
============

This tool provides an MQTT interface to Bluetti power stations. State will be
published to the ``bluetti/state/[DEVICE NAME]/[PROPERTY]`` topic, and commands
can be sent to the ``bluetti/command/[DEVICE NAME]/[PROPERTY]`` topic.



Supported Devices
-----------------
- AC2A (beta)
- AC60
- AC70
- AC180
- AC200L
- AC200M
- AC300
- AC500
- EB3A
- EP500
- EP500P
- EP600


Installation
------------

.. code-block:: bash

    $ pip install git+https://github.com/lemassykoi/bluetti_mqtt


Connection Problems
-------------------

Please make sure bluez is installed and working.



Usage
-----

.. code-block:: bash

    $ bluetti-mqtt --scan
    Found AC3001234567890123: address 00:11:22:33:44:55
    $ bluetti-mqtt --broker [MQTT_BROKER_HOST] 00:11:22:33:44:55

The MQTT broker port defaults to 1883. If your broker uses a different port,
you can specify it as part of the broker host (e.g., ``mybroker.com:1884``) or
by using the ``--port`` argument (e.g., ``--port 1884``).

If your MQTT broker has a username and password, you can pass those in.

.. code-block:: bash

    $ bluetti-mqtt --broker [MQTT_BROKER_HOST] --username username --password pass 00:11:22:33:44:55

By default the device is polled as quickly as possible, but if you'd like to
collect less data, the polling interval can be adjusted.

.. code-block:: bash

    # Poll every 60s
    $ bluetti-mqtt --broker [MQTT_BROKER_HOST] --interval 60 00:11:22:33:44:55

The logging verbosity can be controlled using the ``--loglevel`` option.
Available levels are DEBUG, INFO, WARNING, and ERROR. The default level is INFO.
For more detailed output, for example to debug issues:

.. code-block:: bash

    $ bluetti-mqtt --broker [MQTT_BROKER_HOST] --loglevel DEBUG 00:11:22:33:44:55

If you have multiple devices within bluetooth range, you can monitor all of
them with just a single command. We can only talk to one device at a time, so
you may notice some irregularity in the collected data, especially if you have
not set an interval.

.. code-block:: bash

    $ bluetti-mqtt --broker [MQTT_BROKER_HOST] 00:11:22:33:44:55 00:11:22:33:44:66

Background Service
------------------

Automated Installation (systemd)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For Linux systems using systemd (like Raspberry Pi), you can use the ``--install``
flag to automate the setup of `bluetti-mqtt` as a background service.
This command needs to be run with root privileges:

.. code-block:: bash

    sudo bluetti-mqtt --install

The installer will guide you through an interactive setup process, prompting for:

- The username under which the service should run.

- MQTT broker details (host, port, username, password).

- Device MAC addresses.

- Other operational parameters like polling interval and log level.


It will then:

1. Generate a systemd service file in ``/etc/systemd/system/bluetti-mqtt.service``.

2. Reload the systemd daemon.

3. Enable the service to start automatically on boot.

4. Offer to start the service immediately.


Once installed, you can manage the service using standard ``systemctl`` commands
(e.g., ``sudo systemctl status bluetti-mqtt``, ``sudo systemctl start bluetti-mqtt``,
``sudo systemctl stop bluetti-mqtt``). Logs can be viewed with
``journalctl -u bluetti-mqtt.service``.

Manual Setup (systemd)
~~~~~~~~~~~~~~~~~~~~~~

Alternatively, for manual setup or further customization, you can use the
following systemd service template. It should be placed in
``/etc/systemd/system/bluetti-mqtt.service``.
Once you've written the file, you'll need to run
``sudo systemctl daemon-reload``, then ``sudo systemctl enable bluetti-mqtt``
to have it start on boot, and finally ``sudo systemctl start bluetti-mqtt``
to run it.

.. code-block:: bash

    [Unit]
    Description=Bluetti MQTT
    After=network.target
    StartLimitIntervalSec=0

    [Service]
    Type=simple
    Restart=always
    RestartSec=30
    TimeoutStopSec=15
    User=your_username_here
    ExecStart=/home/your_username_here/.local/bin/bluetti-mqtt --broker [MQTT_BROKER_HOST] 00:11:22:33:44:55

    [Install]
    WantedBy=multi-user.target



Home Assistant Integration
--------------------------

If you have configured Home Assistant to use the same MQTT broker, then by
default most data and switches will be automatically configured there. This is
possible thanks to Home Assistant's support for automatic MQTT discovery.
By default, bluetti_mqtt uses ``homeassistant`` as the discovery prefix.

The level of detail for Home Assistant discovery can be controlled with the
``--ha-config`` flag, which defaults to
configuring most fields ("normal"). Home Assistant MQTT discovery can also be
disabled, or additional internal device fields can be configured with the
"advanced" option.


Domoticz Integration
--------------------------

If you have configured Domoticz to use MQTT Auto Discovery Client Gateway with LAN
Interface, you can use your custom auto discovery prefix when polling. This
can be customized using the ``--ha-discovery-prefix`` command-line option. For
example, to use ``domoticz`` as the prefix:

.. code-block:: bash

    $ bluetti-mqtt --broker 127.0.0.1 --ha-discovery-prefix domoticz 00:11:22:33:44:55


Reverse Engineering
-------------------

For research purposes you can also use the ``bluetti-logger`` command to poll
the device and log in a standardised format.

.. code-block:: bash

    $ bluetti-logger --log the-log-file.log 00:11:22:33:44:55

While the logger is running, change settings on the device and take note of the
time when you made the change, waiting ~ 1 minute between changes. Note that
not every setting that can be changed on the device can be changed over
bluetooth.

If you're looking to add support to control something that the app can change
but cannot be changed directly from the device screen, both iOS and Android
support collecting bluetooth logs from running apps. Additionally, with the
correct hardware Wireshark can be used to collect logs. With these logs and a
report of what commands were sent at what times, this data can be used to
reverse engineer support.

For supporting new devices, the ``bluetti-discovery`` command is provided. It
will scan from 0 to 12500 assuming MODBUS-over-Bluetooth. This will take a
while and requires that the scanned device be in close Bluetooth range for
optimal performance.

.. code-block:: bash

    $ bluetti-discovery --scan
    Found AC3001234567890123: address 00:11:22:33:44:55
    $ bluetti-discovery --log the-log-file.log 00:11:22:33:44:55
